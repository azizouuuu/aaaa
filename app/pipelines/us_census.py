"""US Census international-trade pipeline (HTS10 detail) — a P3 "quick win"
whose main job here is mirroring China: the US is one of the largest buyers
of Chinese UCO, and a `China -> USA` query can be answered from the US
import side at 10-digit HTS precision (e.g. 1518.00.4000, the UCO line).

Like eurostat_comext.py, this answers queries two ways:
  - direct:  reporter is USA (its own declarations).
  - mirror:  reporter is someone else but the partner is USA — flip
             reporter/partner and flow, fetch the US side, flip labels back.

API: https://api.census.gov/data/timeseries/intltrade/{imports|exports}/hs
Free; an optional key (CENSUS_API_KEY, free from census.gov) raises the
daily request allowance. Responses are JSON arrays-of-arrays with a header
row. Annual values come from the year-to-date field at time=YYYY-12 (one
call per code/flow/year instead of twelve monthly ones).

CAVEAT — UNVERIFIED AGAINST THE LIVE API: this sandbox cannot reach
api.census.gov, so field names (GEN_VAL_YR / ALL_VAL_YR), the CTY_CODE
country numbering, and whether I_COMMODITY accepts comma lists are written
from documented Census conventions but not exercised live. The parser is
header-driven, so drift should mean constant tweaks, not a rewrite. Net
weight is deliberately left None: Census quantity fields switch units per
HTS line, and a wrong-unit weight would silently corrupt the unit-value
signal — better absent than wrong.
"""

import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import dataclasses
import os

from .. import config
from ..db import Store
from ..models import FlowQuery, TradeRecord
from ..registry.commodities import CODE_TO_SLUG
from ..registry.countries import COUNTRIES
from ..registry.national_codes import lines_for
from .base import PipelineUnavailable

BASE = {
    "M": "https://api.census.gov/data/timeseries/intltrade/imports/hs",
    "X": "https://api.census.gov/data/timeseries/intltrade/exports/hs",
}
# imports use I_COMMODITY / GEN_VAL_YR (general imports, year-to-date);
# exports use E_COMMODITY / ALL_VAL_YR. UNVERIFIED — confirm on first live run.
COMMODITY_VAR = {"M": "I_COMMODITY", "X": "E_COMMODITY"}
VALUE_VAR = {"M": "GEN_VAL_YR", "X": "ALL_VAL_YR"}

# Census schedule C country codes. Only China is high-confidence from
# documentation; the rest are UNVERIFIED placeholders resolved lazily — an
# unknown code still yields a usable record via the CTY_NAME the API returns.
CENSUS_CTY: dict[str, str] = {
    "CHN": "5700",
}
_CTY_TO_ISO3 = {v: k for k, v in CENSUS_CTY.items()}
CODE_SYSTEM = "HTS10"
MIN_INTERVAL = 0.4


def hts_lines_for_query(codes: tuple[str, ...]) -> list[str]:
    slugs = {CODE_TO_SLUG[c] for c in codes if c in CODE_TO_SLUG}
    out: list[str] = []
    for slug in slugs:
        out.extend(line.code.replace(" ", "").replace(".", "")
                   for line in lines_for("USA", slug))
    return sorted(set(out))


def build_requests(q: FlowQuery, hts_codes: list[str], api_key: str | None = None) -> list[dict]:
    """One request per (year, code): the API is documented as single-valued
    for the commodity predicate, so codes are not comma-joined."""
    requests = []
    for year in q.years:
        for code in hts_codes:
            params = {
                "get": f"CTY_CODE,CTY_NAME,{VALUE_VAR[q.flow]}",
                COMMODITY_VAR[q.flow]: code,
                "COMM_LVL": "HS10",
                "time": f"{year}-12",
            }
            if q.partners is not None and q.partners != ("WLD",):
                cty = [CENSUS_CTY.get(p) for p in q.partners]
                if any(c is None for c in cty):
                    # partner without a known Census code: fetch all partners
                    # and filter after parsing instead of guessing a code
                    pass
                else:
                    params["CTY_CODE"] = ",".join(cty)
            if api_key:
                params["key"] = api_key
            requests.append(params)
    return requests


def parse_response(payload: list, flow: str, year: int, code: str) -> list[TradeRecord]:
    """Census responses are arrays-of-arrays with a header row."""
    if not payload or len(payload) < 2:
        return []
    header = payload[0]
    idx = {name: i for i, name in enumerate(header)}
    value_var = VALUE_VAR[flow]
    if "CTY_CODE" not in idx or value_var not in idx:
        raise PipelineUnavailable(f"unexpected Census columns: {header}")

    records = []
    for row in payload[1:]:
        cty_code = row[idx["CTY_CODE"]]
        cty_name = row[idx.get("CTY_NAME", idx["CTY_CODE"])]
        raw_value = row[idx[value_var]]
        if raw_value in (None, "", "null"):
            continue
        # "-" is Census's total-across-countries row; treat as world
        if cty_code == "-" or (cty_name or "").upper().startswith("TOTAL"):
            partner = "WLD"
        else:
            partner = _CTY_TO_ISO3.get(cty_code)
            if partner is None:
                partner = f"CTY:{cty_code}"
                if cty_name:
                    COUNTRIES.setdefault(partner, (0, cty_name.title()))
        records.append(TradeRecord(
            source="us_census", reporter="USA", partner=partner, flow=flow,
            code=code, code_system=CODE_SYSTEM, year=year,
            value_usd=float(raw_value), net_wgt_kg=None,
        ))
    return records


class UsCensusPipeline:
    source_id = "us_census"
    code_system = CODE_SYSTEM
    priority = 15  # above the Comtrade baseline, below Eurostat

    def __init__(self, store: Store, api_key: str | None = None, timeout: float = 20.0):
        self.store = store
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last_call = 0.0

    def covers(self, q: FlowQuery) -> bool:
        if not hts_lines_for_query(q.codes):
            return False
        if q.reporters == ("USA",):
            return True
        if q.partners == ("USA",) and q.reporters is not None:
            return True
        return False

    def fetch(self, q: FlowQuery) -> list[TradeRecord]:
        if q.reporters == ("USA",):
            records = self._fetch_us_oriented(q)
        else:
            flipped_flow = "M" if q.flow == "X" else "X"
            flipped = FlowQuery(q.codes, flipped_flow, q.years, ("USA",), q.reporters)
            us_records = self._fetch_us_oriented(flipped)
            wanted = set(q.reporters or ())
            records = [
                dataclasses.replace(r, reporter=r.partner, partner="USA", flow=q.flow)
                for r in us_records
                if r.partner in wanted
            ]
        self.store.upsert_flows(records)
        return records

    def _fetch_us_oriented(self, q: FlowQuery) -> list[TradeRecord]:
        hts = hts_lines_for_query(q.codes)
        records: list[TradeRecord] = []
        for params in build_requests(q, hts, self.api_key):
            year = int(params["time"].split("-")[0])
            code = params.get(COMMODITY_VAR[q.flow], "")
            rows = self._fetch_one(params, q.flow, year, code)
            # partner filter for codes we couldn't express upstream
            if q.partners is not None and q.partners != ("WLD",) and "CTY_CODE" not in params:
                rows = [r for r in rows if r.partner in q.partners]
            elif q.partners == ("WLD",):
                rows = [r for r in rows if r.partner == "WLD"]
            records.extend(rows)
        return records

    def _fetch_one(self, params: dict, flow: str, year: int, code: str) -> list[TradeRecord]:
        qs = urllib.parse.urlencode(sorted(params.items()))
        url = f"{BASE[flow]}?{qs}"
        key = "census|" + hashlib.sha256(url.encode()).hexdigest()

        cached = self.store.cache_get(key, config.CACHE_TTL_SECONDS)
        if cached is not None:
            return [TradeRecord(**r) for r in cached]

        payload = self._http_get(url)
        records = parse_response(payload, flow, year, code)
        self.store.cache_put(key, self.source_id, [r.__dict__ for r in records])
        return records

    def _http_get(self, url: str, retries: int = 2):
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        for attempt in range(retries + 1):
            with self._lock:
                wait = MIN_INTERVAL - (time.time() - self._last_call)
                if wait > 0:
                    time.sleep(wait)
                self._last_call = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < retries:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise PipelineUnavailable(f"HTTP {exc.code}") from exc
            except (urllib.error.URLError, OSError, ValueError) as exc:
                raise PipelineUnavailable(str(exc)) from exc
        raise PipelineUnavailable("rate-limited after retries")

"""Eurostat Comext pipeline — the P1 "EU mirror" source (CN8 detail).

Comext (dataset DS-045409, "EU trade since 1988 by CN8") reports the EU's own
customs declarations at 8-digit CN detail. Two things make it valuable here:

1. CN8 splits several of our shared HS6 headings into distinct lines (POME
   vs soapstock in 1522, PFAD vs acid oils in 3823.19, UCO vs modified oils
   in 1518) — see app/signals/national_override.py.
2. It reports EU imports FROM non-EU origins (Indonesia, Malaysia, ...), so
   even though those countries aren't reporters here, their exports TO the
   EU show up at CN8 precision as EU import mirror data.

Because of (2), this pipeline answers queries in two ways:
  - direct:  the app asked for an EU country's own reported flow.
  - mirror:  the app asked for flow(reporter=X, partner=EU_COUNTRY); X is
             not EU, but EU_COUNTRY's own import/export declaration IS the
             mirror of exactly that corridor. We flip flow direction and
             reporter/partner, fetch the EU side, then flip the resulting
             records' labels back so callers never need to know the data
             came from the partner's side.

CAVEAT — UNVERIFIED AGAINST THE LIVE API: this environment's outbound
network is sandboxed (only pypi/npm/github reachable), so the request shape
below (dataset id, dimension names, flow codes, world-partner code) is built
from Eurostat/Comext's documented conventions but has not been exercised
against a real response. Before relying on P1 output, run
scripts/refresh_cache.py-style a smoke call against
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/DS-045409
and fix any field-name drift here — the parsing logic (parse_jsonstat) is
deliberately generic JSON-stat 2.0 so it should only need constant tweaks,
not a rewrite.
"""

import dataclasses
import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from ..db import Store
from ..models import FlowQuery, TradeRecord
from ..registry.commodities import CODE_TO_SLUG
from ..registry.countries import EU_MEMBERS, ISO3_TO_EUROSTAT, ISO3_TO_ISO2, to_eurostat
from ..registry.national_codes import lines_for
from .base import PipelineUnavailable

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/DS-045409"
CODE_SYSTEM = "CN8"

# UNVERIFIED — Comext's classic convention is 1=import, 2=export; some newer
# Eurostat REST datasets use literal "IMP"/"EXP" instead. Confirm live.
FLOW_CODE = {"X": "2", "M": "1"}
# UNVERIFIED — the aggregate-partner code for "rest of world" in this
# dataset. Confirm live; likely candidates are "WORLD" or "EXT_EU27_2020"
# depending on whether it's a world total or extra-EU total.
PARTNER_WORLD = "WORLD"

# Reverse map covers every country we know (not just EU members) since
# Comext partner codes include non-EU origins like Indonesia ("ID") too.
_EUROSTAT_TO_ISO3 = {to_eurostat(iso3): iso3 for iso3 in ISO3_TO_ISO2}
MIN_INTERVAL = 0.5

# Comext reports VALUE_IN_EUROS; every other pipeline (and the unit-value
# bands in signals/candidates.py) assumes USD. A fixed indicative rate is a
# stopgap — the correct fix is a per-year ECB annual-average EUR/USD rate,
# which needs a live data source this sandbox can't reach. Revisit before
# trusting P1 unit values in a currency-sensitive comparison.
EUR_TO_USD = 1.08


def cn8_lines_for_query(codes: tuple[str, ...]) -> list[str]:
    """HS6 codes in the query -> the CN8 lines Comext should be asked for."""
    slugs = {CODE_TO_SLUG[c] for c in codes if c in CODE_TO_SLUG}
    out: list[str] = []
    for slug in slugs:
        out.extend(line.code.replace(" ", "") for line in lines_for("EU", slug))
    return sorted(set(out))


def build_requests(q: FlowQuery, cn8_codes: list[str]) -> list[dict]:
    """Build Comext param dicts for an EU-oriented query (q.reporters are the
    EU declarant(s)). One request per year — keeps payloads small and cache
    entries reusable across queries that only differ by year range."""
    if not cn8_codes:
        return []
    reporters = [ISO3_TO_EUROSTAT[r] for r in q.reporters if r in ISO3_TO_EUROSTAT]
    if not reporters:
        return []
    if q.partners is None:
        partner = None  # omit dimension -> all partners
    elif q.partners == ("WLD",):
        partner = PARTNER_WORLD
    else:
        partner = "+".join(to_eurostat(p) for p in q.partners)

    requests = []
    for year in q.years:
        params = {
            "format": "JSON",
            "lang": "EN",
            "freq": "A",
            "reporter": "+".join(reporters),
            "product": "+".join(cn8_codes),
            "flow": FLOW_CODE[q.flow],
            "indicators": "VALUE_IN_EUROS+QUANTITY_IN_100KG",
            "time": str(year),
        }
        if partner is not None:
            params["partner"] = partner
        requests.append(params)
    return requests


def parse_jsonstat(payload: dict) -> list[dict]:
    """Generic JSON-stat 2.0 decoder: every non-null value cell becomes a row
    of {dimension_id: category_code, ..., "value": float}."""
    dim_ids: list[str] = payload.get("id", [])
    sizes: list[int] = payload.get("size", [])
    dims = payload.get("dimension", {})
    raw_value = payload.get("value", {})
    if not dim_ids or not sizes:
        return []

    categories: list[list[str]] = []
    for dim_id in dim_ids:
        index = dims.get(dim_id, {}).get("category", {}).get("index", {})
        ordered = sorted(index.items(), key=lambda kv: kv[1])
        categories.append([code for code, _ in ordered])

    # strides for row-major flattening (last dimension varies fastest)
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    values = raw_value if isinstance(raw_value, dict) else {
        str(i): v for i, v in enumerate(raw_value) if v is not None
    }

    rows = []
    for flat_key, v in values.items():
        if v is None:
            continue
        idx = int(flat_key)
        row = {}
        for dim_i, dim_id in enumerate(dim_ids):
            cat_idx = (idx // strides[dim_i]) % sizes[dim_i]
            cats = categories[dim_i]
            row[dim_id] = cats[cat_idx] if cat_idx < len(cats) else None
        row["value"] = float(v)
        rows.append(row)
    return rows


def _to_records(rows: list[dict]) -> list[TradeRecord]:
    """Group generic JSON-stat rows (one per indicator) into TradeRecords."""
    groups: dict[tuple, dict] = {}
    for row in rows:
        key = (row.get("reporter"), row.get("partner"), row.get("flow"),
               row.get("product"), row.get("time"))
        g = groups.setdefault(key, {"value_usd": None, "net_wgt_kg": None})
        indicator = row.get("indicators")
        if indicator == "VALUE_IN_EUROS":
            g["value_usd"] = row["value"] * EUR_TO_USD
        elif indicator == "QUANTITY_IN_100KG":
            g["net_wgt_kg"] = row["value"] * 100.0

    records = []
    for (reporter, partner, flow, product, year), g in groups.items():
        if g["value_usd"] is None or not reporter or not partner or not year:
            continue
        reporter_iso3 = _EUROSTAT_TO_ISO3.get(reporter, reporter)
        partner_iso3 = "WLD" if partner == PARTNER_WORLD else _EUROSTAT_TO_ISO3.get(partner, partner)
        flow_code = "X" if flow == FLOW_CODE["X"] else "M"
        records.append(TradeRecord(
            source="eurostat_comext", reporter=reporter_iso3, partner=partner_iso3,
            flow=flow_code, code=product, code_system=CODE_SYSTEM,
            year=int(year), value_usd=g["value_usd"], net_wgt_kg=g["net_wgt_kg"],
        ))
    return records


class EurostatComextPipeline:
    source_id = "eurostat_comext"
    code_system = CODE_SYSTEM
    priority = 20  # tried before the Comtrade global baseline

    def __init__(self, store: Store, timeout: float = 20.0):
        self.store = store
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last_call = 0.0

    def covers(self, q: FlowQuery) -> bool:
        if not cn8_lines_for_query(q.codes):
            return False
        if q.reporters is not None and all(r in EU_MEMBERS for r in q.reporters):
            return True
        if q.partners is not None and q.partners != ("WLD",) and all(
            p in EU_MEMBERS for p in q.partners
        ):
            return True
        return False

    def fetch(self, q: FlowQuery) -> list[TradeRecord]:
        direct = q.reporters is not None and all(r in EU_MEMBERS for r in q.reporters)
        if direct:
            records = self._fetch_eu_oriented(q)
        else:
            flipped_flow = "M" if q.flow == "X" else "X"
            flipped = FlowQuery(q.codes, flipped_flow, q.years, q.partners, q.reporters)
            eu_records = self._fetch_eu_oriented(flipped)
            records = [
                dataclasses.replace(r, reporter=r.partner, partner=r.reporter, flow=q.flow)
                for r in eu_records
            ]
        self.store.upsert_flows(records)
        return records

    def _fetch_eu_oriented(self, q: FlowQuery) -> list[TradeRecord]:
        cn8 = cn8_lines_for_query(q.codes)
        records: list[TradeRecord] = []
        for params in build_requests(q, cn8):
            records.extend(self._fetch_one(params))
        return records

    def _fetch_one(self, params: dict) -> list[TradeRecord]:
        qs = urllib.parse.urlencode(sorted(params.items()))
        url = f"{BASE_URL}?{qs}"
        key = "eurostat|" + hashlib.sha256(url.encode()).hexdigest()

        cached = self.store.cache_get(key, config.CACHE_TTL_SECONDS)
        if cached is not None:
            return [TradeRecord(**r) for r in cached]

        payload = self._http_get(url)
        rows = parse_jsonstat(payload)
        records = _to_records(rows)
        self.store.cache_put(key, self.source_id, [r.__dict__ for r in records])
        return records

    def _http_get(self, url: str, retries: int = 2) -> dict:
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

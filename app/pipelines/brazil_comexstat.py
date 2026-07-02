"""Brazil Comex Stat pipeline (NCM8 detail) — the "quick win" P3+ source.

Comex Stat (https://comexstat.mdic.gov.br) is Brazil's own foreign-trade
statistics service, with a documented, genuinely open public API — no key,
no registration required, unlike Indonesia/Malaysia (see national_csv.py)
and unlike GACC's registration-gated portal (see china_gacc.py). Brazil is
always the implicit reporter — there's no "choose a country," this IS
Brazil's own data — so queries only vary by flow, NCM code, partner country,
and period.

CAVEAT — UNVERIFIED AGAINST THE LIVE API: this sandbox cannot reach
api-comexstat.mdic.gov.br, so the endpoint path and the JSON request/response
shape below (flow/period/filters/details/metrics; a `data.list` array of
flat row dicts) are built from documented Comex Stat conventions but not
exercised live. parse_response() is written defensively (tries a couple of
plausible key spellings per field) so a live field-name mismatch should mean
a constant tweak here, not a rewrite.

Country resolution is NAME-based, not numeric-code-based: Comex Stat rows
carry a descriptive Portuguese country name, and this module resolves it
against PT_COUNTRY_NAMES rather than hardcoded SISCOMEX country codes, which
this build has no way to verify and would fail silently-wrong if guessed.
Unresolved names are skipped with a warning, exactly like national_csv.py.

Scope note: NOT wired into the main PipelineRegistry (services.py) as a
Comtrade replacement. The catalogued NCM8 lines in
app/registry/national_codes.py (tallow, soy) aren't confirmed to fully
partition their HS6 heading, so using them as a drop-in total for
rankings/partners risks silently understating Brazil's trade — the same
caution applied to Indonesia/Malaysia. Instead this feeds
app/signals/origin_confirmation.py through the same available()/location/
load(slug, year) interface as NationalCsvSource — the concrete improvement
over Indonesia/Malaysia being that it's a LIVE call, no manual file needed.
"""

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request

from .. import config
from ..db import Store
from ..models import FlowQuery, TradeRecord
from ..registry.countries import COUNTRIES
from ..registry.national_codes import lines_for
from .base import PipelineUnavailable

BASE_URL = "https://api-comexstat.mdic.gov.br/general"
CODE_SYSTEM = "NCM8"
FLOW_PARAM = {"X": "export", "M": "import"}
MIN_INTERVAL = 0.5

# UNVERIFIED — Comex Stat's Portuguese country-name spellings for the
# partners this app cares about. Confirm on first live call; any name not
# listed here is skipped with a warning rather than guessed.
PT_COUNTRY_NAMES = {
    "PAISES BAIXOS (HOLANDA)": "NLD", "HOLANDA": "NLD",
    "ESTADOS UNIDOS": "USA", "CHINA": "CHN", "SINGAPURA": "SGP",
    "ALEMANHA": "DEU", "ESPANHA": "ESP", "ITALIA": "ITA", "BELGICA": "BEL",
    "FRANCA": "FRA", "REINO UNIDO": "GBR", "ARGENTINA": "ARG",
    "URUGUAI": "URY", "PARAGUAI": "PRY", "INDONESIA": "IDN",
    "MALASIA": "MYS", "COREIA DO SUL": "KOR", "JAPAO": "JPN",
    "INDIA": "IND", "CANADA": "CAN", "MEXICO": "MEX",
}


def _resolve_partner(raw_name: str) -> str | None:
    key = raw_name.strip().upper()
    if key in PT_COUNTRY_NAMES:
        return PT_COUNTRY_NAMES[key]
    by_english_name = {name.upper(): iso for iso, (_, name) in COUNTRIES.items()}
    return by_english_name.get(key)


def build_request(flow: str, ncm_codes: list[str], years: tuple[int, ...],
                  partners: tuple[str, ...] | None = None) -> dict:
    """One request covers the whole query — Comex Stat aggregates a period
    range server-side, unlike Comtrade's tight per-call record cap."""
    years = sorted(years)
    filters = [{"filter": "ncm", "values": ncm_codes}]
    if partners is not None and partners != ("WLD",):
        filters.append({"filter": "country", "values": list(partners)})
    return {
        "flow": FLOW_PARAM[flow],
        "monthDetail": False,
        "period": {"from": f"{years[0]}-01", "to": f"{years[-1]}-12"},
        "filters": filters,
        "details": ["country", "ncm", "year"],
        "metrics": ["metricFOB", "metricKG"],
    }


def parse_response(payload) -> list[dict]:
    """Defensive parse: tolerate {"data": {"list": [...]}} or a bare list."""
    if isinstance(payload, dict):
        rows = payload.get("data", {}).get("list")
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = None
    return rows or []


def _to_records(rows: list[dict], flow: str) -> tuple[list[TradeRecord], list[str]]:
    records: list[TradeRecord] = []
    warnings: list[str] = []
    for i, row in enumerate(rows):
        name = row.get("country") or row.get("noPais") or row.get("nomeCountry")
        ncm = str(row.get("ncm") or row.get("coNcm") or "").strip()
        year = row.get("year") or row.get("coAno")
        value = row.get("metricFOB") or row.get("vlFob")
        wgt = row.get("metricKG") or row.get("kgLiquido")
        if not name or not ncm or not year or value is None:
            warnings.append(f"row {i}: missing required field(s), skipped")
            continue
        partner = _resolve_partner(str(name))
        if partner is None:
            warnings.append(f"row {i}: unrecognized country {name!r}, skipped")
            continue
        records.append(TradeRecord(
            source="brazil_comexstat", reporter="BRA", partner=partner, flow=flow,
            code=ncm, code_system=CODE_SYSTEM, year=int(year),
            value_usd=float(value), net_wgt_kg=float(wgt) if wgt else None,
        ))
    return records, warnings


class BrazilComexStatPipeline:
    source_id = "brazil_comexstat"
    code_system = CODE_SYSTEM
    location = "Brazil Comex Stat is a live API — unavailable in sample/offline mode"

    def __init__(self, store: Store | None = None, timeout: float = 20.0):
        self.store = store
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last_call = 0.0

    def available(self) -> bool:
        return config.DATA_MODE != "sample"

    def load(self, slug: str, year: int) -> tuple[list[TradeRecord], list[str]]:
        """Fetches one slug's export flow for one year — the shape
        origin_confirmation.confirm() needs. Direct callers wanting imports
        or a year range can use fetch_corridor() instead."""
        return self.fetch_corridor(slug, "X", (year,))

    def fetch_corridor(self, slug: str, flow: str, years: tuple[int, ...],
                       partners: tuple[str, ...] | None = None
                       ) -> tuple[list[TradeRecord], list[str]]:
        ncm = [line.code.replace(" ", "").replace(".", "") for line in lines_for("BRA", slug)]
        if not ncm:
            return [], [f"no catalogued NCM8 lines for slug={slug!r} (see national_codes.py)"]
        body = build_request(flow, ncm, years, partners)
        payload = self._post_cached(body)
        rows = parse_response(payload)
        records, warnings = _to_records(rows, flow)
        if self.store is not None:
            self.store.upsert_flows(records)
        return records, warnings

    def _post_cached(self, body: dict):
        key = "comexstat|" + hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()
        ).hexdigest()
        if self.store is not None:
            cached = self.store.cache_get(key, config.CACHE_TTL_SECONDS)
            if cached is not None:
                return cached
        payload = self._http_post(body)
        if self.store is not None:
            self.store.cache_put(key, self.source_id, payload)
        return payload

    def _http_post(self, body: dict, retries: int = 2):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            BASE_URL, data=data, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
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


def build(store: Store | None = None) -> BrazilComexStatPipeline:
    return BrazilComexStatPipeline(store)

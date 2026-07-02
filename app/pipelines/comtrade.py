"""UN Comtrade baseline pipeline (annual goods, HS6, global coverage).

Free public preview endpoint (no key, hard ~500-record cap per call) or the
keyed endpoint when COMTRADE_API_KEY is set. The critical, offline-testable
piece is `build_requests()`: it splits any FlowQuery into HTTP calls whose
expected record count stays under the cap.
"""

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
from ..registry.countries import COUNTRIES, M49_TO_ISO3, m49_of
from .base import PipelineUnavailable

PUBLIC_BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
KEYED_BASE = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

RECORD_BUDGET = 450  # keep expected records safely under the 500 cap
N_ALL_REPORTERS = 200  # planning estimates for budget math
N_ALL_PARTNERS = 230
MIN_INTERVAL = 1.1  # seconds between live calls (public tier ~1 req/s)


def _expected_records(n_reporters: int, n_partners: int, n_codes: int, n_years: int) -> int:
    return n_reporters * n_partners * n_codes * n_years


def build_requests(q: FlowQuery) -> list[dict]:
    """Split a FlowQuery into Comtrade param dicts, each under RECORD_BUDGET.

    Splitting order: years first (annual data caches perfectly per year),
    then codes. Reporter/partner dimensions are never split — queries in this
    app are either "all reporters x world" or "one reporter x all partners",
    both of which fit once years/codes are unbundled.
    """
    n_rep = len(q.reporters) if q.reporters is not None else N_ALL_REPORTERS
    n_par = len(q.partners) if q.partners is not None else N_ALL_PARTNERS

    year_chunks: list[tuple[int, ...]] = [q.years]
    code_chunks: list[tuple[str, ...]] = [q.codes]

    def over_budget() -> bool:
        return _expected_records(
            n_rep, n_par, max(len(c) for c in code_chunks), max(len(y) for y in year_chunks)
        ) > RECORD_BUDGET

    while over_budget() and max(len(y) for y in year_chunks) > 1:
        year_chunks = [(y,) for chunk in year_chunks for y in chunk]
    while over_budget() and max(len(c) for c in code_chunks) > 1:
        code_chunks = [(c,) for chunk in code_chunks for c in chunk]

    requests = []
    for years in year_chunks:
        for codes in code_chunks:
            params = {
                "cmdCode": ",".join(codes),
                "flowCode": q.flow,
                "period": ",".join(str(y) for y in years),
                "maxRecords": 500,
                "includeDesc": "true",
            }
            if q.reporters is not None:
                params["reporterCode"] = ",".join(str(m49_of(r)) for r in q.reporters)
            if q.partners is not None:
                params["partnerCode"] = ",".join(str(m49_of(p)) for p in q.partners)
            requests.append(params)
    return requests


class ComtradePipeline:
    source_id = "comtrade"
    code_system = "HS6"
    priority = 10

    def __init__(self, store: Store, api_key: str | None = None, timeout: float = 20.0):
        self.store = store
        self.api_key = api_key
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last_call = 0.0

    def covers(self, q: FlowQuery) -> bool:
        return True  # global baseline

    # -- fetching --------------------------------------------------------
    def fetch(self, q: FlowQuery) -> list[TradeRecord]:
        records: list[TradeRecord] = []
        for params in build_requests(q):
            records.extend(self._fetch_one(params))
        self.store.upsert_flows(records)
        return records

    def _fetch_one(self, params: dict) -> list[TradeRecord]:
        base = KEYED_BASE if self.api_key else PUBLIC_BASE
        qs = urllib.parse.urlencode(sorted(params.items()))
        url = f"{base}?{qs}"
        key = "comtrade|" + hashlib.sha256(url.encode()).hexdigest()

        cached = self.store.cache_get(key, config.CACHE_TTL_SECONDS)
        if cached is not None:
            return [TradeRecord(**r) for r in cached]

        payload = self._http_get(url)
        data = payload.get("data")
        if data is None:
            raise PipelineUnavailable(f"unexpected Comtrade response: {str(payload)[:200]}")
        records = [r for r in (self._normalize(row) for row in data) if r is not None]
        self.store.cache_put(key, self.source_id, [r.__dict__ for r in records])
        return records

    def _http_get(self, url: str, retries: int = 2) -> dict:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        if self.api_key:
            req.add_header("Ocp-Apim-Subscription-Key", self.api_key)
        for attempt in range(retries + 1):
            with self._lock:  # rate-limit live calls across threads
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

    def _normalize(self, row: dict) -> TradeRecord | None:
        rep_m49 = row.get("reporterCode")
        par_m49 = row.get("partnerCode")
        year = row.get("refYear") or row.get("period")
        if rep_m49 is None or par_m49 is None or year is None:
            return None
        reporter = M49_TO_ISO3.get(int(rep_m49))
        partner = "WLD" if int(par_m49) == 0 else M49_TO_ISO3.get(int(par_m49))
        if reporter is None:
            reporter = f"M49:{rep_m49}"
            desc = row.get("reporterDesc")
            if desc:
                COUNTRIES.setdefault(reporter, (int(rep_m49), desc))
        if partner is None:
            partner = f"M49:{par_m49}"
            desc = row.get("partnerDesc")
            if desc:
                COUNTRIES.setdefault(partner, (int(par_m49), desc))
        net_wgt = row.get("netWgt")
        return TradeRecord(
            source=self.source_id,
            reporter=reporter,
            partner=partner,
            flow=row.get("flowCode", ""),
            code=str(row.get("cmdCode", "")),
            code_system=self.code_system,
            year=int(year),
            value_usd=float(row.get("primaryValue") or 0.0),
            net_wgt_kg=float(net_wgt) if net_wgt else None,
        )

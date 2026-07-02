"""Bundled synthetic dataset pipeline — the offline fallback.

Loads data/sample/sample_trade.json into the trade_flows table once (under
source="sample", estimated=True) and answers queries from there.
"""

import json
from pathlib import Path

from ..db import Store
from ..models import FlowQuery, TradeRecord


class SamplePipeline:
    source_id = "sample"
    code_system = "HS6"
    priority = 0

    def __init__(self, store: Store, path: Path):
        self.store = store
        self.disclaimer = ""
        self._load(path)

    def _load(self, path: Path) -> None:
        payload = json.loads(path.read_text())
        self.disclaimer = payload.get("disclaimer", "")
        records = [
            TradeRecord(
                source=self.source_id,
                reporter=rep, partner=par, flow=flow, code=code,
                code_system=self.code_system, year=year,
                value_usd=float(value), net_wgt_kg=float(wgt) if wgt else None,
                estimated=True,
            )
            for rep, par, flow, code, year, value, wgt in payload["records"]
        ]
        self.store.upsert_flows(records)

    def covers(self, q: FlowQuery) -> bool:
        return True

    def fetch(self, q: FlowQuery) -> list[TradeRecord]:
        return self.store.query_flows(
            self.source_id, q.codes, q.flow, q.years, q.reporters, q.partners
        )

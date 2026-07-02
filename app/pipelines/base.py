"""Pipeline abstraction: every data source implements the same tiny protocol,
and the registry resolves queries to the best available source with an
automatic live -> sample fallback.

Progressive rollout plan (one pipeline per source, added incrementally):
P0 comtrade (global HS6 baseline)   -> app/pipelines/comtrade.py   [live]
P1 eurostat_comext (EU mirror, CN8) -> planned
P2 indonesia_bps + malaysia (AHTN8) -> planned
P3 china mirrors / GACC             -> planned
quick wins: brazil_comexstat (NCM8), us_census (HTS10) -> planned
Paid slots (deferred by decision): ImportGenius / Kpler-style vessel data.
"""

import threading
import time
from typing import Protocol

from ..models import FlowQuery, TradeRecord


class PipelineUnavailable(Exception):
    """Source unreachable / rate-limited / returned garbage."""


class TradeDataPipeline(Protocol):
    source_id: str
    code_system: str
    priority: int  # higher wins when coverage overlaps

    def covers(self, q: FlowQuery) -> bool: ...
    def fetch(self, q: FlowQuery) -> list[TradeRecord]: ...


# When live fetch fails in auto mode we pin sample mode for a while instead of
# re-timing-out on every request (the sandbox blocks all external hosts).
_LIVE_RETRY_AFTER = 300.0


class PipelineRegistry:
    def __init__(self, pipelines: list, sample_pipeline, mode: str = "auto"):
        self.pipelines = sorted(pipelines, key=lambda p: -p.priority)
        self.sample = sample_pipeline
        self.mode = mode  # auto | live | sample
        self._lock = threading.Lock()
        self._live_blocked_until = 0.0

    def _live_allowed(self) -> bool:
        if self.mode == "sample":
            return False
        if self.mode == "live":
            return True
        return time.time() >= self._live_blocked_until

    def fetch(self, q: FlowQuery) -> tuple[list[TradeRecord], str]:
        """Returns (records, source_id_used)."""
        if self._live_allowed():
            for p in self.pipelines:
                if not p.covers(q):
                    continue
                try:
                    return p.fetch(q), p.source_id
                except PipelineUnavailable:
                    if self.mode == "live":
                        raise
                    with self._lock:
                        self._live_blocked_until = time.time() + _LIVE_RETRY_AFTER
                    break
        return self.sample.fetch(q), self.sample.source_id

    @property
    def data_mode(self) -> str:
        if self.mode == "sample" or not self._live_allowed():
            return "sample"
        return self.mode

"""SQLite storage: a raw request cache plus a normalized trade_flows store.

Every pipeline upserts normalized records into trade_flows; all API reads go
through this table so endpoints are source-agnostic.
"""

import json
import sqlite3
import threading
import time

from .models import TradeRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_cache (
    cache_key   TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    payload     TEXT NOT NULL,
    fetched_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS trade_flows (
    source      TEXT NOT NULL,
    reporter    TEXT NOT NULL,
    partner     TEXT NOT NULL,
    flow        TEXT NOT NULL,
    code        TEXT NOT NULL,
    code_system TEXT NOT NULL,
    year        INTEGER NOT NULL,
    value_usd   REAL NOT NULL,
    net_wgt_kg  REAL,
    estimated   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, reporter, partner, flow, code, year)
);
"""


class Store:
    def __init__(self, path):
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True) if hasattr(path, "parent") else None
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._db.commit()

    # ---- raw cache -----------------------------------------------------
    def cache_get(self, key: str, ttl: float):
        row = self._db.execute(
            "SELECT payload, fetched_at FROM raw_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row and time.time() - row[1] < ttl:
            return json.loads(row[0])
        return None

    def cache_put(self, key: str, source: str, payload) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO raw_cache VALUES (?, ?, ?, ?)",
                (key, source, json.dumps(payload), time.time()),
            )
            self._db.commit()

    # ---- normalized flows ----------------------------------------------
    def upsert_flows(self, records: list[TradeRecord]) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT OR REPLACE INTO trade_flows VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        r.source, r.reporter, r.partner, r.flow, r.code,
                        r.code_system, r.year, r.value_usd, r.net_wgt_kg,
                        int(r.estimated),
                    )
                    for r in records
                ],
            )
            self._db.commit()

    def query_flows(
        self,
        source: str,
        codes: tuple[str, ...],
        flow: str,
        years: tuple[int, ...],
        reporters: tuple[str, ...] | None = None,
        partners: tuple[str, ...] | None = None,
    ) -> list[TradeRecord]:
        sql = (
            "SELECT source, reporter, partner, flow, code, code_system, year,"
            " value_usd, net_wgt_kg, estimated FROM trade_flows"
            " WHERE source = ? AND flow = ?"
        )
        params: list = [source, flow]
        sql += f" AND code IN ({','.join('?' * len(codes))})"
        params += list(codes)
        sql += f" AND year IN ({','.join('?' * len(years))})"
        params += list(years)
        if reporters is not None:
            sql += f" AND reporter IN ({','.join('?' * len(reporters))})"
            params += list(reporters)
        if partners is not None:
            sql += f" AND partner IN ({','.join('?' * len(partners))})"
            params += list(partners)
        rows = self._db.execute(sql, params).fetchall()
        return [
            TradeRecord(
                source=a, reporter=b, partner=c, flow=d, code=e, code_system=f,
                year=g, value_usd=h, net_wgt_kg=i, estimated=bool(j),
            )
            for a, b, c, d, e, f, g, h, i, j in rows
        ]

    def count_flows(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM trade_flows").fetchone()[0]

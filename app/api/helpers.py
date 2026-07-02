"""Shared helpers for API routers."""

from fastapi import HTTPException

from ..models import TradeRecord
from ..registry.commodities import BY_SLUG, Commodity
from ..services import get_registry


def envelope(data, source: str) -> dict:
    return {
        "data": data,
        "meta": {"data_mode": get_registry().data_mode, "source": source},
    }


def commodity_or_404(slug: str) -> Commodity:
    c = BY_SLUG.get(slug)
    if c is None:
        raise HTTPException(404, f"unknown commodity '{slug}'")
    return c


def flow_or_400(flow: str) -> str:
    if flow not in ("X", "M"):
        raise HTTPException(400, "flow must be X or M")
    return flow


def metric_or_400(metric: str) -> str:
    if metric not in ("usd", "wgt"):
        raise HTTPException(400, "metric must be usd or wgt")
    return metric


def aggregate_by(records: list[TradeRecord], key: str) -> dict[str, dict]:
    """Sum value/weight by reporter or partner (codes and sub-rows collapse).
    `has_wgt` is True only if EVERY contributing record reported a weight —
    a partial sum is worse than no sum for tonnage-based ranking/sorting."""
    out: dict[str, dict] = {}
    for r in records:
        k = getattr(r, key)
        agg = out.setdefault(k, {"value_usd": 0.0, "net_wgt_kg": 0.0, "has_wgt": True})
        agg["value_usd"] += r.value_usd
        if r.net_wgt_kg:
            agg["net_wgt_kg"] += r.net_wgt_kg
        else:
            agg["has_wgt"] = False
    return out


def row_from_agg(iso3: str, agg: dict, name: str) -> dict:
    wgt_t = agg["net_wgt_kg"] / 1000.0 if (agg["net_wgt_kg"] and agg["has_wgt"]) else None
    return {
        "iso3": iso3,
        "name": name,
        "value_usd": agg["value_usd"],
        "net_wgt_t": wgt_t,
        "unit_value": (agg["value_usd"] / wgt_t) if wgt_t else None,
    }


def rank_rows(rows: list[dict], metric: str) -> tuple[list[dict], int]:
    """Sort by the chosen metric, dropping rows with no reliable weight when
    metric="wgt" (a missing-weight row can't be ranked by tonnage — showing
    it as zero would misrepresent it as negligible). Returns (rows, excluded_count)."""
    if metric == "usd":
        rows.sort(key=lambda r: -r["value_usd"])
        return rows, 0
    usable = [r for r in rows if r["net_wgt_t"] is not None]
    usable.sort(key=lambda r: -r["net_wgt_t"])
    return usable, len(rows) - len(usable)


def share_total(rows: list[dict], metric: str) -> float:
    key = "value_usd" if metric == "usd" else "net_wgt_t"
    return sum(r[key] for r in rows if r[key] is not None) or 1.0

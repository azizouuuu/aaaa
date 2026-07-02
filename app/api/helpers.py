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


def aggregate_by(records: list[TradeRecord], key: str) -> dict[str, dict]:
    """Sum value/weight by reporter or partner (codes and sub-rows collapse)."""
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
    wgt_t = agg["net_wgt_kg"] / 1000.0 if agg["net_wgt_kg"] else None
    return {
        "iso3": iso3,
        "name": name,
        "value_usd": agg["value_usd"],
        "net_wgt_t": wgt_t,
        "unit_value": (agg["value_usd"] / wgt_t) if wgt_t else None,
    }

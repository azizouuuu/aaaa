"""Destination-corridor signal: how much of a flow lands in renewable-diesel /
SAF demand hubs. A waste/residue flow overwhelmingly bound for hub countries is
very likely fuel feedstock rather than the food/oleochemical cohabitant."""

from ..models import TradeRecord
from ..registry.countries import RD_SAF_HUBS, name_of


def hub_share(partner_rows: list[TradeRecord]) -> dict:
    """Value-weighted share of a reporter's partner-level flows going to hubs."""
    total = sum(r.value_usd for r in partner_rows if r.partner != "WLD")
    if total <= 0:
        return {"share": None, "top_hubs": [], "total_usd": 0.0}
    hubs: dict[str, float] = {}
    for r in partner_rows:
        if r.partner in RD_SAF_HUBS:
            hubs[r.partner] = hubs.get(r.partner, 0.0) + r.value_usd
    top = sorted(hubs.items(), key=lambda kv: -kv[1])[:5]
    return {
        "share": sum(hubs.values()) / total,
        "top_hubs": [
            {"iso3": iso, "name": name_of(iso), "value_usd": v, "why": RD_SAF_HUBS[iso]}
            for iso, v in top
        ],
        "total_usd": total,
    }

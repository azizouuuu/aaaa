"""Core trade endpoints: rankings, trends, partners, watchlist."""

from fastapi import APIRouter, HTTPException

from .. import config
from ..models import FlowQuery
from ..registry.commodities import BY_SLUG, FEEDSTOCK_SLUGS
from ..registry.countries import COUNTRIES, RD_SAF_HUBS, WATCHLISTS, name_of
from ..services import get_registry
from .helpers import aggregate_by, commodity_or_404, envelope, flow_or_400, row_from_agg

router = APIRouter(prefix="/api")


@router.get("/rankings")
def rankings(cmd: str, flow: str = "X", year: int = 2024, top: int = 15):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    records, source = get_registry().fetch(
        FlowQuery(c.codes, flow, (year,), reporters=None, partners=("WLD",))
    )
    by_reporter = aggregate_by(records, "reporter")
    total = sum(a["value_usd"] for a in by_reporter.values()) or 1.0
    rows = [
        row_from_agg(iso, agg, name_of(iso)) | {"share": agg["value_usd"] / total}
        for iso, agg in by_reporter.items()
    ]
    rows.sort(key=lambda r: -r["value_usd"])
    return envelope(
        {"rows": rows[:top], "world_total_usd": total, "year": year, "flow": flow},
        source,
    )


@router.get("/trend/world")
def world_trend(cmd: str):
    c = commodity_or_404(cmd)
    registry = get_registry()
    out = {}
    source = "sample"
    for flow in ("X", "M"):
        records, source = registry.fetch(
            FlowQuery(c.codes, flow, tuple(config.YEARS), None, ("WLD",))
        )
        by_year: dict[int, float] = {}
        wgt_by_year: dict[int, float] = {}
        for r in records:
            by_year[r.year] = by_year.get(r.year, 0.0) + r.value_usd
            if r.net_wgt_kg:
                wgt_by_year[r.year] = wgt_by_year.get(r.year, 0.0) + r.net_wgt_kg
        out[flow] = [
            {
                "year": y,
                "value_usd": by_year.get(y, 0.0),
                "net_wgt_t": (wgt_by_year[y] / 1000.0) if wgt_by_year.get(y) else None,
            }
            for y in config.YEARS
        ]
    return envelope({"years": config.YEARS, "exports": out["X"], "imports": out["M"]}, source)


@router.get("/partners")
def partners(cmd: str, reporter: str, flow: str = "X", year: int = 2024, top: int = 12):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    if reporter not in COUNTRIES:
        raise HTTPException(404, f"unknown reporter '{reporter}'")
    records, source = get_registry().fetch(
        FlowQuery(c.codes, flow, (year,), (reporter,), partners=None)
    )
    by_partner = aggregate_by([r for r in records if r.partner != "WLD"], "partner")
    total = sum(a["value_usd"] for a in by_partner.values()) or 1.0
    rows = [
        row_from_agg(iso, agg, name_of(iso))
        | {"share": agg["value_usd"] / total, "is_hub": iso in RD_SAF_HUBS}
        for iso, agg in by_partner.items()
    ]
    rows.sort(key=lambda r: -r["value_usd"])
    return envelope(
        {
            "rows": rows[:top],
            "reporter": {"iso3": reporter, "name": name_of(reporter)},
            "total_usd": total,
            "year": year,
            "flow": flow,
        },
        source,
    )


@router.get("/partners/trend")
def partner_trend(cmd: str, reporter: str, flow: str = "X"):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    if reporter not in COUNTRIES:
        raise HTTPException(404, f"unknown reporter '{reporter}'")
    records, source = get_registry().fetch(
        FlowQuery(c.codes, flow, tuple(config.YEARS), (reporter,), ("WLD",))
    )
    by_year: dict[int, float] = {}
    for r in records:
        by_year[r.year] = by_year.get(r.year, 0.0) + r.value_usd
    return envelope(
        {
            "reporter": {"iso3": reporter, "name": name_of(reporter)},
            "rows": [{"year": y, "value_usd": by_year.get(y, 0.0)} for y in config.YEARS],
        },
        source,
    )


@router.get("/watchlist")
def watchlist(region: str = "asia", year: int = 2024):
    w = WATCHLISTS.get(region)
    if w is None:
        raise HTTPException(404, f"unknown region '{region}' (use: {list(WATCHLISTS)})")
    registry = get_registry()
    countries = tuple(w["countries"])
    # per-country totals across all waste/residue + crop feedstocks (exports)
    totals: dict[str, dict[int, float]] = {iso: {} for iso in countries}
    top_cmd: dict[str, dict[str, float]] = {iso: {} for iso in countries}
    source = "sample"
    for slug in FEEDSTOCK_SLUGS:
        c = BY_SLUG[slug]
        records, source = registry.fetch(
            FlowQuery(c.codes, "X", tuple(config.YEARS), countries, ("WLD",))
        )
        for r in records:
            totals[r.reporter][r.year] = totals[r.reporter].get(r.year, 0.0) + r.value_usd
            if r.year == year:
                top_cmd[r.reporter][slug] = top_cmd[r.reporter].get(slug, 0.0) + r.value_usd
    rows = []
    for iso in countries:
        now = totals[iso].get(year, 0.0)
        prev = totals[iso].get(year - 1, 0.0)
        top3 = sorted(top_cmd[iso].items(), key=lambda kv: -kv[1])[:3]
        rows.append(
            {
                "iso3": iso,
                "name": name_of(iso),
                "value_usd": now,
                "prev_usd": prev,
                "yoy": ((now - prev) / prev) if prev > 0 else None,
                "by_year": [
                    {"year": y, "value_usd": totals[iso].get(y, 0.0)}
                    for y in config.YEARS
                ],
                "top_commodities": [
                    {"slug": slug, "name": BY_SLUG[slug].name, "value_usd": v}
                    for slug, v in top3
                ],
            }
        )
    rows.sort(key=lambda r: -r["value_usd"])
    return envelope(
        {"region": w["name"], "rows": rows, "year": year, "scope": "feedstock exports"},
        source,
    )

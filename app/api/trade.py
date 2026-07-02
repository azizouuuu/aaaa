"""Core trade endpoints: rankings, trends, partners, watchlist."""

from fastapi import APIRouter, HTTPException

from .. import config
from ..models import FlowQuery
from ..registry.commodities import BY_SLUG, FEEDSTOCK_SLUGS
from ..registry.countries import COUNTRIES, EU_BLOC_ISO, EU_MEMBERS, RD_SAF_HUBS, WATCHLISTS, name_of
from ..services import get_registry
from ..signals.eu_bloc import correct_world_total, eu_bloc_totals
from .helpers import (
    aggregate_by, commodity_or_404, envelope, flow_or_400, metric_or_400,
    rank_rows, row_from_agg, share_total,
)

router = APIRouter(prefix="/api")


@router.get("/rankings")
def rankings(cmd: str, flow: str = "X", year: int = 2024, top: int = 15, metric: str = "wgt",
            eu_as_bloc: bool = False):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    metric_or_400(metric)
    registry = get_registry()
    records, source = registry.fetch(
        FlowQuery(c.codes, flow, (year,), reporters=None, partners=("WLD",))
    )
    by_reporter = aggregate_by(records, "reporter")

    # World totals always exclude intra-EU trade (the Rotterdam effect) —
    # even when EU members are listed individually below, an inflated
    # denominator would understate every country's true share of world trade.
    naive_world = {year: {
        "value_usd": sum(a["value_usd"] for a in by_reporter.values()),
        "net_wgt_kg": sum(a["net_wgt_kg"] for a in by_reporter.values() if a["has_wgt"]),
    }}
    corrected = correct_world_total(naive_world, registry, c.codes, flow, (year,))[year]
    world_total_usd = corrected["value_usd"]
    world_total_wgt_t = corrected["net_wgt_kg"] / 1000.0

    if eu_as_bloc:
        # collapse individual EU27 members into one consolidated row —
        # eu_bloc_totals() already excludes intra-EU legs from this figure.
        for iso in EU_MEMBERS:
            by_reporter.pop(iso, None)
        bloc = eu_bloc_totals(registry, c.codes, flow, (year,))[year]
        if bloc["value_usd"] > 0 or bloc["net_wgt_kg"] > 0:
            by_reporter[EU_BLOC_ISO] = {
                "value_usd": bloc["value_usd"], "net_wgt_kg": bloc["net_wgt_kg"],
                "has_wgt": bloc["net_wgt_kg"] > 0,
            }

    rows = [
        row_from_agg(iso, agg, name_of(iso))
        | {"is_eu_member": iso in EU_MEMBERS, "is_bloc": iso == EU_BLOC_ISO}
        for iso, agg in by_reporter.items()
    ]
    for r in rows:
        denom = world_total_usd if metric == "usd" else world_total_wgt_t
        value = r["value_usd"] if metric == "usd" else (r["net_wgt_t"] or 0)
        r["share"] = (value / denom) if denom else 0.0
    ranked, excluded = rank_rows(rows, metric)

    return envelope(
        {
            "rows": ranked[:top], "world_total_usd": world_total_usd,
            "world_total_wgt_t": world_total_wgt_t,
            "year": year, "flow": flow, "metric": metric,
            "excluded_no_weight": excluded, "eu_as_bloc": eu_as_bloc,
            "note": (
                "World totals exclude intra-EU27 trade to avoid double-counting "
                "re-exports (the Rotterdam effect). Individual EU member rows "
                "below still show their own full reported total, which can "
                "include intra-EU legs — use eu_as_bloc=true to see the EU27 "
                "as one consolidated, non-double-counted entity instead."
            ),
        },
        source,
    )


@router.get("/trend/world")
def world_trend(cmd: str):
    c = commodity_or_404(cmd)
    registry = get_registry()
    years = tuple(config.YEARS)
    out = {}
    source = "sample"
    for flow in ("X", "M"):
        records, source = registry.fetch(FlowQuery(c.codes, flow, years, None, ("WLD",)))
        naive: dict[int, dict] = {y: {"value_usd": 0.0, "net_wgt_kg": 0.0} for y in years}
        for r in records:
            naive[r.year]["value_usd"] += r.value_usd
            naive[r.year]["net_wgt_kg"] += r.net_wgt_kg or 0.0
        # exclude intra-EU27 trade (the Rotterdam effect) — see
        # app/signals/eu_bloc.py. Without this, a shipment re-exported
        # within the EU is counted once on entry and again on re-export.
        corrected = correct_world_total(naive, registry, c.codes, flow, years)
        out[flow] = [
            {
                "year": y,
                "value_usd": corrected[y]["value_usd"],
                "net_wgt_t": (corrected[y]["net_wgt_kg"] / 1000.0) if corrected[y]["net_wgt_kg"] else None,
            }
            for y in years
        ]
    return envelope(
        {
            "years": config.YEARS, "exports": out["X"], "imports": out["M"],
            "note": "Excludes intra-EU27 trade to avoid double-counting re-exports "
                    "(the Rotterdam effect) — see Methodology.",
        },
        source,
    )


def _eu_bloc_partner_breakdown(registry, codes: tuple[str, ...], flow: str, year: int):
    """Sum each EU27 member's own partner-level breakdown, keeping only
    NON-EU partners (dropping intra-EU legs and each member's own WLD
    aggregate row) — who the bloc actually trades with, as one consolidated
    view. No intra-EU subtraction math needed here (unlike eu_bloc.py): each
    kept row is already a distinct, real, non-EU corridor, so summing them
    across members is correct as-is."""
    combined: dict[str, dict] = {}
    sources_used: set[str] = set()
    for member in EU_MEMBERS:
        records, src = registry.fetch(FlowQuery(codes, flow, (year,), (member,), None))
        sources_used.add(src)
        for r in records:
            if r.partner == "WLD" or r.partner in EU_MEMBERS:
                continue
            agg = combined.setdefault(
                r.partner, {"value_usd": 0.0, "net_wgt_kg": 0.0, "has_wgt": True}
            )
            agg["value_usd"] += r.value_usd
            if r.net_wgt_kg:
                agg["net_wgt_kg"] += r.net_wgt_kg
            else:
                agg["has_wgt"] = False
    source = "+".join(sorted(sources_used)) if sources_used else "sample"
    return combined, source


@router.get("/partners")
def partners(cmd: str, reporter: str, flow: str = "X", year: int = 2024, top: int = 12,
            metric: str = "wgt"):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    metric_or_400(metric)
    registry = get_registry()
    if reporter == EU_BLOC_ISO:
        by_partner, source = _eu_bloc_partner_breakdown(registry, c.codes, flow, year)
    else:
        if reporter not in COUNTRIES:
            raise HTTPException(404, f"unknown reporter '{reporter}'")
        records, source = registry.fetch(
            FlowQuery(c.codes, flow, (year,), (reporter,), partners=None)
        )
        by_partner = aggregate_by([r for r in records if r.partner != "WLD"], "partner")

    rows = [
        row_from_agg(iso, agg, name_of(iso)) | {"is_hub": iso in RD_SAF_HUBS}
        for iso, agg in by_partner.items()
    ]
    total = share_total(rows, metric)
    for r in rows:
        r["share"] = (r["value_usd"] if metric == "usd" else r["net_wgt_t"] or 0) / total
    ranked, excluded = rank_rows(rows, metric)
    payload = {
        "rows": ranked[:top],
        "reporter": {"iso3": reporter, "name": name_of(reporter)},
        "total_usd": share_total(rows, "usd"),
        "total_wgt_t": share_total(rows, "wgt"),
        "year": year,
        "flow": flow,
        "metric": metric,
        "excluded_no_weight": excluded,
    }
    if reporter == EU_BLOC_ISO:
        payload["note"] = (
            "EU27 bloc view: each member's trade with fellow EU countries is "
            "excluded, showing only extra-EU partners — see Methodology."
        )
    return envelope(payload, source)


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
    wgt_by_year: dict[int, float] = {}
    for r in records:
        by_year[r.year] = by_year.get(r.year, 0.0) + r.value_usd
        if r.net_wgt_kg:
            wgt_by_year[r.year] = wgt_by_year.get(r.year, 0.0) + r.net_wgt_kg
    return envelope(
        {
            "reporter": {"iso3": reporter, "name": name_of(reporter)},
            "rows": [
                {
                    "year": y, "value_usd": by_year.get(y, 0.0),
                    "net_wgt_t": (wgt_by_year[y] / 1000.0) if wgt_by_year.get(y) else None,
                }
                for y in config.YEARS
            ],
        },
        source,
    )


@router.get("/watchlist")
def watchlist(region: str = "asia", year: int = 2024, metric: str = "wgt"):
    w = WATCHLISTS.get(region)
    if w is None:
        raise HTTPException(404, f"unknown region '{region}' (use: {list(WATCHLISTS)})")
    metric_or_400(metric)
    registry = get_registry()
    countries = tuple(w["countries"])
    # per-country totals across all waste/residue + crop feedstocks (exports)
    totals: dict[str, dict[int, float]] = {iso: {} for iso in countries}
    wgt_totals: dict[str, dict[int, float]] = {iso: {} for iso in countries}
    top_cmd: dict[str, dict[str, float]] = {iso: {} for iso in countries}
    top_cmd_wgt: dict[str, dict[str, float]] = {iso: {} for iso in countries}
    source = "sample"
    for slug in FEEDSTOCK_SLUGS:
        c = BY_SLUG[slug]
        records, source = registry.fetch(
            FlowQuery(c.codes, "X", tuple(config.YEARS), countries, ("WLD",))
        )
        for r in records:
            totals[r.reporter][r.year] = totals[r.reporter].get(r.year, 0.0) + r.value_usd
            if r.net_wgt_kg:
                wgt_totals[r.reporter][r.year] = (
                    wgt_totals[r.reporter].get(r.year, 0.0) + r.net_wgt_kg / 1000.0
                )
            if r.year == year:
                top_cmd[r.reporter][slug] = top_cmd[r.reporter].get(slug, 0.0) + r.value_usd
                if r.net_wgt_kg:
                    top_cmd_wgt[r.reporter][slug] = (
                        top_cmd_wgt[r.reporter].get(slug, 0.0) + r.net_wgt_kg / 1000.0
                    )
    rows = []
    for iso in countries:
        now_usd, prev_usd = totals[iso].get(year, 0.0), totals[iso].get(year - 1, 0.0)
        now_wgt, prev_wgt = wgt_totals[iso].get(year), wgt_totals[iso].get(year - 1)
        now = now_usd if metric == "usd" else now_wgt
        prev = prev_usd if metric == "usd" else prev_wgt
        cmd_source = top_cmd if metric == "usd" else top_cmd_wgt
        top3 = sorted(cmd_source[iso].items(), key=lambda kv: -kv[1])[:3]
        rows.append(
            {
                "iso3": iso,
                "name": name_of(iso),
                "value_usd": now_usd,
                "net_wgt_t": now_wgt,
                "metric_value": now,
                "prev_metric_value": prev,
                "yoy": ((now - prev) / prev) if (prev and now is not None) else None,
                "by_year": [
                    {
                        "year": y, "value_usd": totals[iso].get(y, 0.0),
                        "net_wgt_t": wgt_totals[iso].get(y),
                    }
                    for y in config.YEARS
                ],
                "top_commodities": [
                    {"slug": slug, "name": BY_SLUG[slug].name, "value": v}
                    for slug, v in top3
                ],
            }
        )
    rows.sort(key=lambda r: -(r["metric_value"] or 0))
    return envelope(
        {"region": w["name"], "rows": rows, "year": year, "metric": metric,
         "scope": "feedstock exports"},
        source,
    )

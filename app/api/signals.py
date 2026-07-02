"""Signals endpoints: disaggregation, corridor summaries, origination intel,
mirror checks."""

from fastapi import APIRouter, HTTPException

from ..models import FlowQuery
from ..pipelines import china_gacc, indonesia_bps, malaysia_dosm
from ..registry.countries import COUNTRIES, name_of
from ..services import get_registry
from ..signals.candidates import candidates_for
from ..signals.china_mirror import triangulate
from ..signals.corridors import hub_share
from ..signals.engine import disaggregate_flow
from ..signals.mirror import mirror_check
from ..signals.origin_confirmation import confirm as confirm_origin
from ..signals.origination import corridor_flags, country_flags
from .helpers import aggregate_by, commodity_or_404, envelope, flow_or_400

router = APIRouter(prefix="/api")

# P2/P3 local-file sources, keyed by the reporter they cover — see
# app/pipelines/national_csv.py for why these read a local file.
_ORIGIN_SOURCES = {
    "IDN": indonesia_bps.build,
    "MYS": malaysia_dosm.build,
    "CHN": china_gacc.build,
}


def _serialize_signal(result, slug: str) -> dict:
    labels = {c.key: {"label": c.label, "fuel_bound": c.fuel_bound,
                      "band_usd_per_t": [c.band_lo, c.band_hi]}
              for c in candidates_for(slug)}
    return {
        "reporter": {"iso3": result.reporter, "name": name_of(result.reporter)},
        "partner": {"iso3": result.partner, "name": name_of(result.partner)},
        "code": result.code,
        "year": result.year,
        "flow": result.flow,
        "unit_value": result.unit_value,
        "candidates": [
            {"key": k, "prob": p} | labels.get(k, {}) for k, p in result.candidates
        ],
        "explanations": result.explanations,
        "confidence": result.confidence,
        "basis": result.basis,
    }


@router.get("/signals/flow")
def signal_flow(cmd: str, reporter: str, partner: str, year: int = 2024, flow: str = "X"):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    for iso in (reporter, partner):
        if iso not in COUNTRIES:
            raise HTTPException(404, f"unknown country '{iso}'")
    registry = get_registry()
    rows, source = registry.fetch(FlowQuery(c.codes, flow, (year,), (reporter,), (partner,)))
    if not rows:
        raise HTTPException(404, "no recorded flow for this corridor/year")
    exporter, importer = (reporter, partner) if flow == "X" else (partner, reporter)
    mirror = mirror_check(registry, c.codes, exporter, importer, year)
    result = disaggregate_flow(c.slug, reporter, partner, year, flow, rows, mirror)
    payload = _serialize_signal(result, c.slug)
    payload["value_usd"] = sum(r.value_usd for r in rows)
    payload["mirror"] = mirror
    return envelope(payload, source)


@router.get("/signals/summary")
def signal_summary(cmd: str, flow: str = "X", year: int = 2024, top: int = 12):
    """Disaggregate the biggest corridors of a shared-heading commodity."""
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    if not candidates_for(c.slug):
        return envelope({"rows": [], "note": "heading not shared — no signals needed"},
                        "registry")
    registry = get_registry()
    ranked, source = registry.fetch(
        FlowQuery(c.codes, flow, (year,), None, ("WLD",))
    )
    by_reporter = aggregate_by(ranked, "reporter")
    top_reporters = sorted(by_reporter, key=lambda i: -by_reporter[i]["value_usd"])[:6]
    corridors = []
    for rep in top_reporters:
        rows, source = registry.fetch(FlowQuery(c.codes, flow, (year,), (rep,), None))
        partner_rows = [r for r in rows if r.partner != "WLD"]
        hubs = hub_share(partner_rows)
        by_partner = aggregate_by(partner_rows, "partner")
        for partner in sorted(by_partner, key=lambda i: -by_partner[i]["value_usd"])[:2]:
            corridor = [r for r in partner_rows if r.partner == partner]
            result = disaggregate_flow(c.slug, rep, partner, year, flow, corridor)
            corridors.append(
                _serialize_signal(result, c.slug)
                | {"value_usd": sum(r.value_usd for r in corridor),
                   "reporter_hub_share": hubs["share"]}
            )
    corridors.sort(key=lambda r: -r["value_usd"])
    return envelope({"rows": corridors[:top], "year": year, "flow": flow}, source)


@router.get("/origination")
def origination(cmd: str, flow: str = "X", year: int = 2024, reporter: str | None = None):
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    registry = get_registry()
    records, source = registry.fetch(
        FlowQuery(c.codes, flow, (year - 1, year), None, ("WLD",))
    )
    values_by_year: dict[int, dict[str, float]] = {year - 1: {}, year: {}}
    for r in records:
        values_by_year[r.year][r.reporter] = (
            values_by_year[r.year].get(r.reporter, 0.0) + r.value_usd
        )
    flags = [
        f | {"name": name_of(f["iso3"])} for f in country_flags(values_by_year, year)
    ]
    payload = {"country_flags": flags, "year": year, "flow": flow}
    if reporter:
        if reporter not in COUNTRIES:
            raise HTTPException(404, f"unknown reporter '{reporter}'")
        p_now, source = registry.fetch(FlowQuery(c.codes, flow, (year,), (reporter,), None))
        p_prev, source = registry.fetch(
            FlowQuery(c.codes, flow, (year - 1,), (reporter,), None)
        )
        now: dict[str, float] = {}
        for r in p_now:
            if r.partner != "WLD":
                now[r.partner] = now.get(r.partner, 0.0) + r.value_usd
        prev: dict[str, float] = {}
        for r in p_prev:
            if r.partner != "WLD":
                prev[r.partner] = prev.get(r.partner, 0.0) + r.value_usd
        payload["corridor_flags"] = [
            f | {"partner_name": name_of(f["partner"])}
            for f in corridor_flags(now, prev)
        ]
        payload["reporter"] = {"iso3": reporter, "name": name_of(reporter)}
    return envelope(payload, source)


@router.get("/mirror")
def mirror(cmd: str, exporter: str, importer: str, year: int = 2024):
    c = commodity_or_404(cmd)
    for iso in (exporter, importer):
        if iso not in COUNTRIES:
            raise HTTPException(404, f"unknown country '{iso}'")
    result = mirror_check(get_registry(), c.codes, exporter, importer, year)
    return envelope(
        result
        | {"exporter": {"iso3": exporter, "name": name_of(exporter)},
           "importer": {"iso3": importer, "name": name_of(importer)},
           "year": year},
        get_registry().data_mode,
    )


@router.get("/origin-check")
def origin_check(cmd: str, reporter: str, year: int = 2024):
    """P2: compare a country's own declared export value (local file, see
    app/pipelines/national_csv.py) against the global mirror. `available:
    false` is the expected result until a user provides that file — this is
    not an error."""
    c = commodity_or_404(cmd)
    build_source = _ORIGIN_SOURCES.get(reporter)
    if build_source is None:
        raise HTTPException(
            404, f"no local-file source configured for '{reporter}' "
                 f"(available: {list(_ORIGIN_SOURCES)})"
        )
    result = confirm_origin(c.slug, reporter, year, build_source(), get_registry())
    return envelope(
        {
            "slug": result.slug,
            "reporter": {"iso3": result.reporter, "name": name_of(result.reporter)},
            "year": result.year,
            "available": result.available,
            "global_value_usd": result.global_value_usd,
            "national_value_usd": result.national_value_usd,
            "ratio": result.ratio,
            "note": result.note,
            "warnings": result.warnings or [],
        },
        get_registry().data_mode,
    )


@router.get("/china-mirror")
def china_mirror(cmd: str, year: int = 2024, flow: str = "X"):
    """P3: triangulate China's trade in a commodity from the demand side —
    what the mirror panel of major buyers reports trading WITH China —
    since GACC data is not freely automatable (see app/pipelines/china_gacc.py)."""
    c = commodity_or_404(cmd)
    flow_or_400(flow)
    result = triangulate(c.slug, year, get_registry(), flow)
    return envelope(
        {
            "slug": result.slug,
            "commodity": c.name,
            "year": result.year,
            "flow": result.flow,
            "mirror_total_usd": result.mirror_total_usd,
            "own_declared_usd": result.own_declared_usd,
            "ratio": result.ratio,
            "breakdown": result.breakdown,
            "notes": result.notes,
        },
        get_registry().data_mode,
    )

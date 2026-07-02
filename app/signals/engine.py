"""Composite disaggregation scorer.

For a corridor (reporter → partner, shared HS heading, year) combine:
  unit-value band membership   weight 0.45   (strongest tell)
  origin prior                 weight 0.25
  destination-hub fit          weight 0.20
  mirror consistency           weight 0.10   (uniform across candidates —
                                              it shifts confidence, not the split)

Outputs are heuristic estimates with plain-language explanations UNLESS a
national tariff-line source (e.g. Eurostat Comext CN8, see
app/pipelines/eurostat_comext.py) reported the corridor at finer detail — in
that case `_national_line_split()` computes a measured split directly from
the national lines and short-circuits the heuristic entirely
(basis="national_tariff_line", confidence "high"/"medium" depending on how
much of the corridor's value fell on ambiguous residual lines).
"""

from ..models import SignalResult, TradeRecord
from ..registry.countries import RD_SAF_HUBS, name_of
from .candidates import candidates_for
from .mirror import consistency_score
from .national_override import override_for
from .unit_value import BAND_VINTAGE, band_membership

WEIGHTS = {"unit_value": 0.45, "origin": 0.25, "destination": 0.20, "mirror": 0.10}
UNCERTAIN_SHARE_FOR_HIGH_CONFIDENCE = 0.15


def _dest_fit(fuel_bound: bool, dest_is_hub: bool) -> float:
    if fuel_bound:
        return 0.9 if dest_is_hub else 0.35
    return 0.2 if dest_is_hub else 0.7


def _national_line_split(slug: str, corridor_rows: list[TradeRecord]) -> SignalResult | None:
    """Measured split from national tariff lines, when any corridor row was
    reported at a finer code system than HS6. Returns None if no row maps to
    a known override (falls back to the heuristic in that case)."""
    national_rows = [r for r in corridor_rows if r.code_system != "HS6"]
    if not national_rows:
        return None
    labels = {c.key: c.label for c in candidates_for(slug)}
    by_candidate: dict[str, float] = {}
    uncertain = 0.0
    total = 0.0
    for r in national_rows:
        total += r.value_usd
        ov = override_for(r.code_system, r.code)
        if ov is None:
            uncertain += r.value_usd
            continue
        by_candidate[ov.candidate] = by_candidate.get(ov.candidate, 0.0) + r.value_usd
        if not ov.certain:
            uncertain += r.value_usd * 0.5  # residual "other" line — partly ambiguous
    if total <= 0 or not by_candidate:
        return None

    candidates = sorted(
        ((key, v / total) for key, v in by_candidate.items()), key=lambda kv: -kv[1]
    )
    uncertain_share = uncertain / total
    explanation_parts = ", ".join(
        f"{labels.get(k, k)} {v:.0%}" for k, v in candidates
    )
    return SignalResult(
        reporter="", partner="", code="", year=0, flow="",  # filled by caller
        candidates=candidates,
        explanations=[
            f"Confirmed via national tariff-line data (CN8): {explanation_parts}.",
            f"{uncertain_share:.0%} of corridor value fell on a residual/ambiguous "
            f"line." if uncertain_share > 0 else "All corridor value mapped to a "
            "specific national line.",
        ],
        confidence="high" if uncertain_share < UNCERTAIN_SHARE_FOR_HIGH_CONFIDENCE else "medium",
        basis="national_tariff_line",
    )


def disaggregate_flow(slug: str, reporter: str, partner: str, year: int, flow: str,
                      corridor_rows: list[TradeRecord],
                      mirror: dict | None = None) -> SignalResult:
    result = SignalResult(reporter=reporter, partner=partner,
                          code=",".join(sorted({r.code for r in corridor_rows})) or slug,
                          year=year, flow=flow)
    cands = candidates_for(slug)
    if not cands:
        result.explanations.append(
            "This heading is not materially shared — no disaggregation needed."
        )
        result.confidence = "high"
        return result

    national = _national_line_split(slug, corridor_rows)
    if national is not None:
        national.reporter, national.partner = reporter, partner
        national.code, national.year, national.flow = result.code, year, flow
        wgt = sum(r.net_wgt_kg or 0.0 for r in corridor_rows)
        value = sum(r.value_usd for r in corridor_rows)
        national.unit_value = (value / (wgt / 1000.0)) if wgt > 0 else None
        return national

    origin = reporter if flow == "X" else partner
    dest = partner if flow == "X" else reporter
    dest_is_hub = dest in RD_SAF_HUBS

    value = sum(r.value_usd for r in corridor_rows)
    wgt = sum(r.net_wgt_kg or 0.0 for r in corridor_rows)
    uv = (value / (wgt / 1000.0)) if wgt > 0 else None
    result.unit_value = uv

    mirror_s = consistency_score(mirror) if mirror else None

    scores: list[tuple[str, str, float, float]] = []  # key, label, score, uv_m
    for c in cands:
        uv_m = band_membership(uv, c.band_lo, c.band_hi) if uv is not None else None
        origin_p = c.origin_priors.get(origin, c.default_prior)
        dest_p = _dest_fit(c.fuel_bound, dest_is_hub)
        w = dict(WEIGHTS)
        if uv_m is None:
            w["unit_value"] = 0.0
        if mirror_s is None:
            w["mirror"] = 0.0
        total_w = sum(w.values()) or 1.0
        score = (
            w["unit_value"] * (uv_m or 0.0)
            + w["origin"] * origin_p
            + w["destination"] * dest_p
            + w["mirror"] * (mirror_s or 0.0)
        ) / total_w
        scores.append((c.key, c.label, score, uv_m if uv_m is not None else -1))

    total = sum(s for _, _, s, _ in scores) or 1.0
    result.candidates = [(key, round(s / total, 3)) for key, _, s, _ in scores]
    result.candidates.sort(key=lambda kv: -kv[1])

    # ---- explanations ----------------------------------------------------
    labels = {c.key: c.label for c in cands}
    if uv is not None:
        best_uv = max(cands, key=lambda c: band_membership(uv, c.band_lo, c.band_hi))
        result.explanations.append(
            f"Unit value ${uv:,.0f}/t vs {best_uv.label} band "
            f"${best_uv.band_lo:,.0f}–{best_uv.band_hi:,.0f}/t ({BAND_VINTAGE})."
        )
    else:
        result.explanations.append(
            "No net weight reported — unit-value check unavailable, "
            "confidence reduced."
        )
    top_prior = max(cands, key=lambda c: c.origin_priors.get(origin, c.default_prior))
    result.explanations.append(
        f"Origin prior: {name_of(origin)} → {top_prior.label} "
        f"{top_prior.origin_priors.get(origin, top_prior.default_prior):.0%}."
    )
    if dest_is_hub:
        result.explanations.append(
            f"Destination {name_of(dest)} is an RD/SAF hub ({RD_SAF_HUBS[dest]}) — "
            "favours fuel-bound candidates."
        )
    else:
        result.explanations.append(
            f"Destination {name_of(dest)} is not a known RD/SAF hub."
        )
    if mirror and mirror.get("available"):
        result.explanations.append(f"Mirror check: {mirror.get('note', '')}")

    # ---- confidence ------------------------------------------------------
    top_prob = result.candidates[0][1] if result.candidates else 0.0
    if uv is not None and top_prob >= 0.60:
        result.confidence = "medium" if (mirror_s is not None and mirror_s < 0.7) else "high"
    elif top_prob >= 0.45:
        result.confidence = "medium"
    else:
        result.confidence = "low"
    result.explanations.append(
        f"Heuristic estimate — most likely {labels[result.candidates[0][0]]} "
        f"at {result.candidates[0][1]:.0%} ({result.confidence} confidence). "
        "National tariff-line data (pipeline roadmap) will replace this with "
        "measured splits."
    )
    return result

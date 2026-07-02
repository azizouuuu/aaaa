"""Mirror-data cross-check: compare what the exporter reports (FOB) with what
the importer reports (CIF). Ratios far from ~1.05–1.10 flag misclassification,
re-routing through hubs, or valuation games — a classic UCO-fraud tell."""

from ..models import FlowQuery, TradeRecord

# imports are CIF, exports FOB — a ~5–15% premium is normal
_NORMAL_LO, _NORMAL_HI = 0.85, 1.40


def mirror_check(registry, codes: tuple[str, ...], exporter: str, importer: str,
                 year: int) -> dict:
    x_rows, _ = registry.fetch(FlowQuery(codes, "X", (year,), (exporter,), (importer,)))
    m_rows, _ = registry.fetch(FlowQuery(codes, "M", (year,), (importer,), (exporter,)))
    reported_x = sum(r.value_usd for r in x_rows)
    mirrored_m = sum(r.value_usd for r in m_rows)
    if reported_x <= 0 and mirrored_m <= 0:
        return {"available": False}
    if reported_x <= 0 or mirrored_m <= 0:
        return {
            "available": True, "reported_x": reported_x, "mirrored_m": mirrored_m,
            "ratio": None, "flag": "one_sided",
            "note": "Only one side reports this corridor — weak data or misclassification.",
        }
    ratio = mirrored_m / reported_x
    if ratio < _NORMAL_LO:
        flag, note = "under_reported_imports", (
            "Importer sees much less than exporter claims — possible re-routing "
            "or partner misattribution."
        )
    elif ratio > _NORMAL_HI:
        flag, note = "over_reported_imports", (
            "Importer sees much more than exporter claims — possible origin "
            "laundering into this corridor or exporter under-declaration."
        )
    else:
        flag, note = "consistent", "Both sides broadly agree (CIF/FOB gap is normal)."
    return {
        "available": True, "reported_x": reported_x, "mirrored_m": mirrored_m,
        "ratio": ratio, "flag": flag, "note": note,
    }


def consistency_score(mirror: dict) -> float | None:
    """Map a mirror result to 0..1 (1 = clean two-sided agreement)."""
    if not mirror.get("available") or mirror.get("ratio") is None:
        return None
    ratio = mirror["ratio"]
    if _NORMAL_LO <= ratio <= _NORMAL_HI:
        return 1.0
    dist = (_NORMAL_LO - ratio) if ratio < _NORMAL_LO else (ratio - _NORMAL_HI)
    return max(0.0, 1.0 - dist)

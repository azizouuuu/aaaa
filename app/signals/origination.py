"""Origination / sourcing intel: growth anomalies, new exporters, corridor
shifts — computed from data already fetched for rankings and partner views."""

MIN_FLAG_VALUE = 15e6  # ignore noise below $15M
SURGE_YOY = 0.5
COLLAPSE_YOY = -0.4
NEW_RATIO = 0.10  # prior year < 10% of current = effectively new


def country_flags(values_by_year: dict[int, dict[str, float]], year: int) -> list[dict]:
    """values_by_year: {year: {iso3: value_usd}} for one commodity+flow."""
    now = values_by_year.get(year, {})
    prev = values_by_year.get(year - 1, {})
    flags = []
    for iso, value in now.items():
        if value < MIN_FLAG_VALUE:
            continue
        before = prev.get(iso, 0.0)
        if before < value * NEW_RATIO:
            flags.append({
                "iso3": iso, "type": "new_exporter", "value_usd": value,
                "prev_usd": before,
                "detail": f"Effectively new flow: ${value/1e6:,.0f}M vs "
                          f"${before/1e6:,.0f}M the year before.",
            })
            continue
        yoy = (value - before) / before
        if yoy >= SURGE_YOY:
            flags.append({
                "iso3": iso, "type": "surge", "value_usd": value, "prev_usd": before,
                "yoy": yoy,
                "detail": f"+{yoy:.0%} YoY (${before/1e6:,.0f}M → ${value/1e6:,.0f}M).",
            })
        elif yoy <= COLLAPSE_YOY:
            flags.append({
                "iso3": iso, "type": "collapse", "value_usd": value, "prev_usd": before,
                "yoy": yoy,
                "detail": f"{yoy:.0%} YoY (${before/1e6:,.0f}M → ${value/1e6:,.0f}M).",
            })
    order = {"new_exporter": 0, "surge": 1, "collapse": 2}
    flags.sort(key=lambda f: (order[f["type"]], -f["value_usd"]))
    return flags


def corridor_flags(partners_now: dict[str, float], partners_prev: dict[str, float]) -> list[dict]:
    """Partner-level equivalents for one reporter (new corridors & shifts)."""
    flags = []
    for partner, value in partners_now.items():
        if value < MIN_FLAG_VALUE / 3:  # corridors are smaller than countries
            continue
        before = partners_prev.get(partner, 0.0)
        if before < value * NEW_RATIO:
            flags.append({
                "partner": partner, "type": "new_corridor", "value_usd": value,
                "detail": f"New destination: ${value/1e6:,.0f}M "
                          f"(≈${before/1e6:,.0f}M prior year).",
            })
        else:
            yoy = (value - before) / before
            if yoy >= SURGE_YOY:
                flags.append({
                    "partner": partner, "type": "corridor_surge", "value_usd": value,
                    "yoy": yoy, "detail": f"+{yoy:.0%} YoY into this destination.",
                })
    flags.sort(key=lambda f: -f["value_usd"])
    return flags

"""Unit-value band membership — the strongest single heuristic for splitting
feedstocks that share an HS heading.

Bands are indicative of 2022–2024 price levels (USD/tonne) and are meant to be
reviewed by a domain expert. Membership uses a trapezoid: 1.0 inside the band,
linear fall-off over a 15% margin outside, 0 beyond — so overlapping bands
produce soft, honest scores instead of hard classifications.
"""

BAND_VINTAGE = "indicative 2022–2024 levels"
_MARGIN = 0.15


def band_membership(usd_per_t: float, lo: float, hi: float) -> float:
    if usd_per_t <= 0:
        return 0.0
    if lo <= usd_per_t <= hi:
        return 1.0
    if usd_per_t < lo:
        floor = lo * (1 - _MARGIN)
        return max(0.0, (usd_per_t - floor) / (lo - floor))
    ceil = hi * (1 + _MARGIN)
    return max(0.0, (ceil - usd_per_t) / (ceil - hi))

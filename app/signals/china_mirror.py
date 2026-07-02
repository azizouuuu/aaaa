"""China mirror triangulation (P3).

China's own customs data is effectively unreachable for automated free use
(see app/pipelines/china_gacc.py), and its direct reporting to UN Comtrade
has been sparse in recent years. So China's exports of a commodity are
triangulated from the DEMAND side: sum what the major buyer countries
report importing FROM China. For renewable feedstocks this works unusually
well — the destinations are concentrated in exactly the RD/SAF hub
countries this app already tracks, so a modest mirror panel captures most
of the flow.

Two honest caveats carried into every result:
  - Mirror imports are CIF (include freight/insurance) vs China's FOB
    exports — expect the mirror sum to run ~5-10% high on covered corridors.
  - The panel only covers listed mirrors; exports to destinations outside
    the panel are invisible. The own-vs-mirror ratio therefore mixes both
    effects and is a coverage indicator, not a fraud verdict on its own.
"""

from dataclasses import dataclass, field

from ..models import FlowQuery
from ..registry.commodities import BY_SLUG
from ..registry.countries import name_of

# Value-weighted panel of the destinations that matter for renewable
# feedstocks & fuels: RD/SAF hubs + the big Asian buyers. Comtrade budget:
# len(panel) reporters x 1 partner x <=2 codes x 1 year << 450 per call.
MIRROR_REPORTERS = (
    "USA", "NLD", "ESP", "DEU", "ITA", "GBR", "BEL", "FRA", "FIN", "PRT",
    "IRL", "SWE", "SGP", "KOR", "JPN", "MYS", "THA", "IND", "CAN", "AUS",
)


@dataclass
class ChinaMirrorResult:
    slug: str
    year: int
    flow: str
    mirror_total_usd: float = 0.0
    own_declared_usd: float | None = None
    ratio: float | None = None  # own / mirror
    breakdown: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def triangulate(slug: str, year: int, registry, flow: str = "X") -> ChinaMirrorResult:
    """flow="X": China's exports seen through partners' imports from China.
    flow="M": China's imports seen through partners' exports to China."""
    commodity = BY_SLUG[slug]
    result = ChinaMirrorResult(slug=slug, year=year, flow=flow)
    mirror_flow = "M" if flow == "X" else "X"

    rows, _ = registry.fetch(
        FlowQuery(commodity.codes, mirror_flow, (year,), MIRROR_REPORTERS, ("CHN",))
    )
    by_reporter: dict[str, float] = {}
    for r in rows:
        by_reporter[r.reporter] = by_reporter.get(r.reporter, 0.0) + r.value_usd
    result.mirror_total_usd = sum(by_reporter.values())
    result.breakdown = sorted(
        (
            {"iso3": iso, "name": name_of(iso), "value_usd": v}
            for iso, v in by_reporter.items()
        ),
        key=lambda d: -d["value_usd"],
    )

    own_rows, _ = registry.fetch(
        FlowQuery(commodity.codes, flow, (year,), ("CHN",), ("WLD",))
    )
    own = sum(r.value_usd for r in own_rows)
    result.own_declared_usd = own if own > 0 else None

    if result.own_declared_usd and result.mirror_total_usd > 0:
        result.ratio = result.own_declared_usd / result.mirror_total_usd
        if result.ratio < 0.75:
            result.notes.append(
                f"China's own declaration is only {result.ratio:.0%} of what the "
                f"mirror panel reports buying from it — classic pattern for "
                f"under-declared or re-routed flows, but check the CIF/FOB gap "
                f"and panel coverage before concluding."
            )
        elif result.ratio > 1.25:
            result.notes.append(
                f"China declares {result.ratio:.0%} of the mirror sum — exports "
                f"are going to destinations outside the {len(MIRROR_REPORTERS)}-"
                f"country mirror panel; consider widening it."
            )
        else:
            result.notes.append(
                f"China's declaration and the mirror panel broadly agree "
                f"({result.ratio:.0%}, CIF/FOB gap considered)."
            )
    elif result.mirror_total_usd > 0:
        result.notes.append(
            "China's own declaration is unavailable for this commodity/year — "
            "the mirror sum is the only estimate."
        )
    else:
        result.notes.append("No mirror data found for this commodity/year.")

    result.notes.append(
        f"Mirror panel: {len(MIRROR_REPORTERS)} reporters (imports are CIF, "
        f"~5-10% above FOB). Flows to unlisted destinations are not counted."
    )
    return result

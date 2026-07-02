"""Cross-checks a country's own declared export value (from a local national
CSV — see app/pipelines/national_csv.py) against what the global mirror
(UN Comtrade, or Eurostat where it applies) shows for the same reporter and
year. This does not replace either source or pick a winner — it surfaces the
gap, which is itself informative: a large shortfall usually means the
catalogued national line doesn't cover the whole HS6 heading yet (see
app/registry/national_codes.py), not that the data is wrong.
"""

from dataclasses import dataclass

from ..models import FlowQuery
from ..registry.commodities import BY_SLUG
from ..registry.countries import name_of

AGREEMENT_LO, AGREEMENT_HI = 0.85, 1.15


@dataclass
class OriginConfirmation:
    slug: str
    reporter: str
    year: int
    available: bool
    global_value_usd: float | None = None
    national_value_usd: float | None = None
    ratio: float | None = None
    note: str = ""
    warnings: list[str] | None = None


def confirm(slug: str, reporter: str, year: int, source, registry) -> OriginConfirmation:
    """`source` is any object with `.available() -> bool`, `.location` (a
    string describing where to look/what's missing), and
    `.load(slug, year) -> (records, warnings)` — NationalCsvSource
    (Indonesia/Malaysia/China) or a live pipeline like
    brazil_comexstat.BrazilComexStatPipeline. `registry` is the app's
    PipelineRegistry (for the global-mirror side)."""
    if not source.available():
        return OriginConfirmation(
            slug, reporter, year, available=False,
            note=f"{source.location} — see app/pipelines/national_csv.py or "
                 f"the source-specific module for how to provide data.",
        )

    records, warnings = source.load(slug, year)
    national_value = sum(r.value_usd for r in records if r.year == year and r.flow == "X")

    commodity = BY_SLUG[slug]
    global_rows, _ = registry.fetch(
        FlowQuery(commodity.codes, "X", (year,), (reporter,), ("WLD",))
    )
    global_value = sum(r.value_usd for r in global_rows)

    if national_value <= 0 or global_value <= 0:
        return OriginConfirmation(
            slug, reporter, year, available=True,
            global_value_usd=global_value or None,
            national_value_usd=national_value or None,
            note="Insufficient data on one or both sides for this reporter/year.",
            warnings=warnings,
        )

    ratio = national_value / global_value
    if AGREEMENT_LO <= ratio <= AGREEMENT_HI:
        note = (f"{name_of(reporter)}'s own declaration and the global HS6 "
                f"total broadly agree ({ratio:.0%}).")
    elif ratio < AGREEMENT_LO:
        note = (
            f"{name_of(reporter)}'s catalogued national line covers only "
            f"{ratio:.0%} of the global HS6 total — likely other AHTN8 "
            f"sub-lines exist that aren't catalogued yet (see "
            f"app/registry/national_codes.py), not necessarily under-reporting."
        )
    else:
        note = (
            f"{name_of(reporter)}'s national declaration is {ratio:.0%} of "
            f"the global HS6 total — check for a broader catch-all line or "
            f"double-counting across AHTN8 codes."
        )
    return OriginConfirmation(
        slug, reporter, year, available=True,
        global_value_usd=global_value, national_value_usd=national_value,
        ratio=ratio, note=note, warnings=warnings,
    )

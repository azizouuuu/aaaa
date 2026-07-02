"""EU27-as-a-bloc correction: avoids double-counting intra-EU trade (the
"Rotterdam effect") in any total that sums across multiple reporters.

Concretely: if Indonesia ships POME to the Netherlands, and the Netherlands
re-ships part of it to Germany, that is ONE physical shipment. Naively
summing every reporting country's own "exports to world" figure counts it
TWICE — once as Indonesia -> Netherlands, again as Netherlands -> Germany —
because each EU member state's own reported total legitimately includes its
intra-EU trade. Eurostat itself publishes separate "intra-EU" and "extra-EU"
series for exactly this reason; this module is the same idea applied to our
Comtrade-sourced totals.

EU_MEMBERS (app/registry/countries.py) is EU27, not EU28 — the UK is
correctly excluded (it left the customs union in 2021), so UK<->EU flows
count in full as real international trade rather than being netted out as
if they were internal. This is slightly wrong for 2018-2020 data (the UK
genuinely was in the bloc then, so those years' UK<->EU legs were truly
intra-bloc) — a far smaller, more academic gap than the alternative error
of still treating the UK as part of the bloc after Brexit.

Every query here excludes the Eurostat pipeline (exclude_sources) so a
correction's inputs are always consistently sourced — mixing a
Comtrade-sourced naive total with a partially Eurostat-CN8-sourced
subtraction would introduce its own inconsistency (different code systems,
the EUR->USD approximation) into the very number meant to be more correct.
"""

from ..models import FlowQuery
from ..registry.countries import EU_MEMBERS

_EU_TUPLE = tuple(sorted(EU_MEMBERS))
_EXCLUDE_EUROSTAT = frozenset({"eurostat_comext"})


def _empty_by_year(years: tuple[int, ...]) -> dict[int, dict]:
    return {y: {"value_usd": 0.0, "net_wgt_kg": 0.0} for y in years}


def _sum_records(records, years: tuple[int, ...], skip_same_country: bool = False) -> dict[int, dict]:
    out = _empty_by_year(years)
    for r in records:
        if skip_same_country and r.reporter == r.partner:
            continue
        if r.year in out:
            out[r.year]["value_usd"] += r.value_usd
            out[r.year]["net_wgt_kg"] += r.net_wgt_kg or 0.0
    return out


def intra_eu_totals(registry, codes: tuple[str, ...], flow: str,
                    years: tuple[int, ...]) -> dict[int, dict]:
    """The double-counted internal leg: EU member -> EU member trade, summed
    per year. Subtract this from any multi-reporter total that includes EU
    member states to correct for the Rotterdam effect."""
    records, _ = registry.fetch(
        FlowQuery(codes, flow, years, _EU_TUPLE, _EU_TUPLE), exclude_sources=_EXCLUDE_EUROSTAT
    )
    return _sum_records(records, years, skip_same_country=True)


def eu_members_naive_totals(registry, codes: tuple[str, ...], flow: str,
                            years: tuple[int, ...]) -> dict[int, dict]:
    """EU27 members' own combined exports-to-world, BEFORE removing the
    intra-EU leg (i.e. still double-counted) — combine with
    intra_eu_totals() to get the bloc's genuine extra-EU total."""
    records, _ = registry.fetch(
        FlowQuery(codes, flow, years, _EU_TUPLE, ("WLD",)), exclude_sources=_EXCLUDE_EUROSTAT
    )
    return _sum_records(records, years)


def _subtract(a: dict[int, dict], b: dict[int, dict], years: tuple[int, ...]) -> dict[int, dict]:
    return {
        y: {
            "value_usd": max(0.0, a[y]["value_usd"] - b[y]["value_usd"]),
            "net_wgt_kg": max(0.0, a[y]["net_wgt_kg"] - b[y]["net_wgt_kg"]),
        }
        for y in years
    }


def eu_bloc_totals(registry, codes: tuple[str, ...], flow: str,
                   years: tuple[int, ...]) -> dict[int, dict]:
    """The EU27 bloc's own consolidated trade with the REST OF THE WORLD —
    a figure directly comparable to any individual country's total."""
    naive = eu_members_naive_totals(registry, codes, flow, years)
    intra = intra_eu_totals(registry, codes, flow, years)
    return _subtract(naive, intra, years)


def correct_world_total(naive_world: dict[int, dict], registry, codes: tuple[str, ...],
                        flow: str, years: tuple[int, ...]) -> dict[int, dict]:
    """Given an already-fetched naive "sum of ALL reporters' exports to
    world" total (keyed by year), subtract the intra-EU double-counted leg."""
    intra = intra_eu_totals(registry, codes, flow, years)
    return _subtract(naive_world, intra, years)

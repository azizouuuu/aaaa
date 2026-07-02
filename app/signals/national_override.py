"""National tariff-line -> candidate mapping.

When a pipeline reports data at a national code system finer than HS6 (e.g.
Eurostat Comext CN8), a single national line can pin down the shared-heading
split directly instead of guessing from unit value/origin/destination. This
is still a judgment call (mapping a customs line to "this is the fuel-bound
candidate") and should be reviewed alongside the unit-value bands in
signals/candidates.py — it is a large upgrade in confidence, not a
guarantee.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LineOverride:
    candidate: str
    certain: bool  # False when the line still bundles more than one candidate


# (code_system, code) -> LineOverride. Codes are digits-only (no punctuation).
NATIONAL_OVERRIDES: dict[tuple[str, str], LineOverride] = {
    # ---- EU Comext CN8 ----
    ("CN8", "15220039"): LineOverride("pome", True),
    ("CN8", "15220031"): LineOverride("soapstock_degras", True),
    ("CN8", "15220099"): LineOverride("soapstock_degras", False),  # residual "other"
    ("CN8", "38231910"): LineOverride("pfad", True),
    ("CN8", "38231930"): LineOverride("pfad", False),  # fatty acid distillate ~ PFAD-like
    ("CN8", "38231990"): LineOverride("acid_oil", False),  # residual "other, incl acid oils"
    ("CN8", "15180095"): LineOverride("uco", True),
    ("CN8", "15180099"): LineOverride("modified_oils", True),
    ("CN8", "15021090"): LineOverride("inedible_tallow", True),
}


def override_for(code_system: str, code: str) -> LineOverride | None:
    return NATIONAL_OVERRIDES.get((code_system, code.replace(" ", "").replace(".", "")))

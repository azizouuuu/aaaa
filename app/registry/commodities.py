"""Commodity registry: the HS codes this app monitors and why.

`codes` is what gets queried (tuple → Comtrade comma-list). `shared_heading`
flags headings where multiple products cohabit at HS6 — those get the
disaggregation signals treatment. Ethanol is queried at subheading level so
undenatured (2207.10, Brazil-style fuel ethanol) and denatured (2207.20,
US-style) can be told apart.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Commodity:
    slug: str
    name: str
    group: str  # "waste_residue" | "crop_oil" | "fuel"
    codes: tuple[str, ...]
    hs_label: str
    shared_heading: bool
    cohabitants: tuple[str, ...]
    caveat: str


COMMODITIES: list[Commodity] = [
    # ---- Waste & residue feedstocks ----
    Commodity(
        "uco", "Used cooking oil (UCO)", "waste_residue", ("1518",), "HS 1518",
        True, ("chemically modified oils", "epoxidised/blown oils", "inedible fat mixtures"),
        "UCO ships under HS 1518; the heading also carries modified oils, so "
        "treat totals as an upper bound and lean on the signals panel.",
    ),
    Commodity(
        "tallow", "Tallow & animal fats", "waste_residue", ("1502",), "HS 1502",
        True, ("edible tallow for food & oleochemicals",),
        "Fuel-bound and food/oleo-bound tallow share the heading; grade split "
        "only visible at national tariff lines.",
    ),
    Commodity(
        "pome", "POME & fatty residues", "waste_residue", ("1522",), "HS 1522",
        True, ("soapstock", "degras", "other fatty residues"),
        "POME oil is declared under HS 1522 alongside soapstock and degras. "
        "Origin (ID/MY) + unit value separate them reasonably well.",
    ),
    Commodity(
        "pfad_acid", "PFAD, acid oils & soapstock acid oil", "waste_residue",
        ("382319",), "HS 3823.19",
        True, ("PFAD", "soy/sun acid oils", "mixed industrial fatty acids"),
        "PFAD (ID/MY origin) and crush-origin acid oils (ARG/BRA/EU) share "
        "3823.19; origin priors + unit value drive the split.",
    ),
    Commodity(
        "tall_oil", "Tall oil (CTO)", "waste_residue", ("380300",), "HS 3803",
        False, (),
        "Kraft-pulping by-product; crude vs refined split needs national lines.",
    ),
    Commodity(
        "tofa", "Tall oil fatty acids (TOFA)", "waste_residue", ("382313",),
        "HS 3823.13", False, (),
        "Competes between oleochemicals and renewable fuels.",
    ),
    Commodity(
        "tco", "Technical / distillers corn oil", "waste_residue",
        ("151521", "151529"), "HS 1515.21/.29",
        True, ("food-grade corn oil",),
        "Distillers corn oil (US ethanol-plant by-product) is declared with "
        "food corn oil; US origin + discount unit value are the tells.",
    ),
    # ---- Crop-based feedstocks ----
    Commodity(
        "palm", "Palm oil", "crop_oil", ("1511",), "HS 1511",
        False, ("food-grade palm oil (dominant share)",),
        "All end uses; food demand dominates the flow.",
    ),
    Commodity(
        "soy", "Soybean oil", "crop_oil", ("1507",), "HS 1507",
        False, ("food-grade soybean oil",),
        "The Americas' biodiesel feedstock; food demand dominates trade.",
    ),
    Commodity(
        "rapeseed", "Rapeseed / canola oil", "crop_oil", ("1514",), "HS 1514",
        False, ("food-grade rapeseed oil",),
        "The dominant European FAME feedstock.",
    ),
    Commodity(
        "sunflower", "Sunflower oil", "crop_oil", ("1512",), "HS 1512",
        False, ("food-grade sunflower oil (dominant share)",),
        "Minor biofuel use; included for feedstock-market context.",
    ),
    # ---- Renewable fuels ----
    Commodity(
        "biodiesel", "Biodiesel & blends (FAME)", "fuel", ("3826",), "HS 3826",
        False, ("HVO blends in some jurisdictions",),
        "Biodiesel and mixtures <70% petroleum. The closest global proxy for "
        "renewable fuel trade; pure HVO may clear under 2710 instead.",
    ),
    Commodity(
        "ethanol", "Ethanol (fuel & industrial)", "fuel", ("220710", "220720"),
        "HS 2207.10/.20", True, ("beverage & industrial alcohol",),
        "Undenatured 2207.10 (Brazilian fuel ethanol trades here) vs denatured "
        "2207.20 (US fuel ethanol's usual line). Includes non-fuel alcohol.",
    ),
]

BY_SLUG = {c.slug: c for c in COMMODITIES}
FEEDSTOCK_SLUGS = tuple(c.slug for c in COMMODITIES if c.group != "fuel")

GROUPS = {
    "waste_residue": "Waste & residue feedstocks",
    "crop_oil": "Crop-based feedstocks",
    "fuel": "Renewable fuels",
}

HVO_SAF_NOTE = (
    "HVO (renewable diesel) and SAF have no dedicated 6-digit HS code: as pure "
    "hydrocarbons they clear customs inside HS 2710, mixed with fossil diesel "
    "and jet fuel, so they cannot be isolated in UN Comtrade. HS 3826 catches "
    "blends below 70% petroleum content and is the closest global proxy. "
    "National tariff lines (e.g. Eurostat Comext CN8) are the planned route to "
    "a real HVO/SAF series — see the pipeline roadmap."
)

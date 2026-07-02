"""Candidate feedstocks per shared HS heading, with their unit-value bands and
origin priors. This is THE table a domain expert should review — bands are
USD/tonne at indicative 2022–2024 levels, priors are subjective probabilities
that a given origin exports that candidate under the shared code.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candidate:
    key: str
    label: str
    fuel_bound: bool  # does RD/SAF demand pull this candidate?
    band_lo: float  # USD/t
    band_hi: float
    band_note: str
    origin_priors: dict = field(default_factory=dict)  # iso3 -> prior
    default_prior: float = 0.2


CANDIDATES: dict[str, list[Candidate]] = {
    "pome": [
        Candidate(
            "pome", "POME oil", True, 450, 750,
            "deep discount to CPO; freight-adjusted",
            {"IDN": 0.75, "MYS": 0.70, "THA": 0.35, "COL": 0.30, "GTM": 0.30, "HND": 0.30},
            0.05,
        ),
        Candidate(
            "soapstock_degras", "Soapstock / degras", False, 250, 450,
            "lowest-grade residues",
            {"ARG": 0.5, "BRA": 0.4, "USA": 0.35, "UKR": 0.35, "ESP": 0.45,
             "ITA": 0.45, "DEU": 0.4, "NLD": 0.35},
            0.25,
        ),
    ],
    "pfad_acid": [
        Candidate(
            "pfad", "PFAD", True, 650, 950,
            "~80–90% of CPO price",
            {"IDN": 0.75, "MYS": 0.70, "THA": 0.35, "PNG": 0.35},
            0.10,
        ),
        Candidate(
            "acid_oil", "Acid oils (soapstock-derived)", True, 450, 700,
            "crush-origin acid oils; also fuel-bound but different origins",
            {"ARG": 0.6, "BRA": 0.5, "USA": 0.35, "UKR": 0.35, "ESP": 0.35, "NLD": 0.3},
            0.20,
        ),
        Candidate(
            "oleo_fatty_acids", "Industrial fatty acids (oleochemical)", False, 900, 1600,
            "distilled/specialty fatty acids for oleochemistry",
            {"DEU": 0.5, "NLD": 0.4, "USA": 0.4, "MYS": 0.35, "IDN": 0.3},
            0.25,
        ),
    ],
    "tco": [
        Candidate(
            "tco", "Technical / distillers corn oil", True, 800, 1150,
            "discount to food-grade corn oil",
            {"USA": 0.8, "BRA": 0.35, "CAN": 0.3},
            0.10,
        ),
        Candidate(
            "food_corn_oil", "Food-grade corn oil", False, 1150, 1800,
            "refined edible corn oil",
            {"TUR": 0.6, "UKR": 0.5, "HUN": 0.5, "FRA": 0.5, "ITA": 0.5, "ESP": 0.5,
             "ARG": 0.4, "DEU": 0.4},
            0.30,
        ),
    ],
    "uco": [
        Candidate(
            "uco", "Used cooking oil", True, 750, 1150,
            "tracks CPO/gasoil spread; China FOB reference",
            {"CHN": 0.85, "GBR": 0.55, "JPN": 0.55, "KOR": 0.55, "ARE": 0.55,
             "MYS": 0.5, "IDN": 0.5, "THA": 0.5, "NLD": 0.45, "USA": 0.4},
            0.30,
        ),
        Candidate(
            "modified_oils", "Chemically modified / specialty oils", False, 1250, 2500,
            "epoxidised, blown, hydrogenated specialty oils",
            {"DEU": 0.5, "USA": 0.4, "NLD": 0.35, "FRA": 0.35},
            0.20,
        ),
    ],
    "tallow": [
        Candidate(
            "inedible_tallow", "Inedible tallow (fuel-bound)", True, 850, 1150,
            "renewable-diesel grade",
            {"AUS": 0.6, "NZL": 0.6, "USA": 0.55, "BRA": 0.5, "URY": 0.5,
             "PRY": 0.5, "ARG": 0.5, "CAN": 0.5},
            0.35,
        ),
        Candidate(
            "edible_tallow", "Edible tallow (food/oleo)", False, 1150, 1600,
            "food & oleochemical grades",
            {"IRL": 0.45, "FRA": 0.4, "NZL": 0.4, "AUS": 0.4},
            0.30,
        ),
    ],
}


def candidates_for(slug: str) -> list[Candidate]:
    return CANDIDATES.get(slug, [])

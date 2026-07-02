"""Indicative national tariff lines (8–10 digit) per (jurisdiction, feedstock).

These are the drill-down targets for the progressive per-country pipelines
(Eurostat Comext CN8, Indonesia/Malaysia AHTN8, US Census HTS10, Brazil NCM8).
They are DOCUMENTATION-GRADE in v1 — always verify against the current
national schedule before using operationally; lines shift between editions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NatLine:
    code: str
    system: str  # CN8 | AHTN8 | HTS10 | NCM8 | GACC10
    label: str


NATIONAL_LINES: dict[tuple[str, str], list[NatLine]] = {
    # ---- EU (Eurostat Comext, CN8) — the P1 mirror pipeline ----
    ("EU", "uco"): [
        NatLine("15180095", "CN8", "Inedible mixtures of animal / animal+veg fats & oils — UCO's usual line"),
        NatLine("15180099", "CN8", "Other inedible mixtures"),
    ],
    ("EU", "pome"): [
        NatLine("15220031", "CN8", "Soapstocks containing oil with olive-oil characteristics"),
        NatLine("15220039", "CN8", "Other residues from fatty substances (POME import line)"),
        NatLine("15220099", "CN8", "Other fatty residues"),
    ],
    ("EU", "pfad_acid"): [
        NatLine("38231910", "CN8", "Distilled fatty acids (PFAD lands here)"),
        NatLine("38231930", "CN8", "Fatty acid distillate"),
        NatLine("38231990", "CN8", "Other industrial fatty acids incl. acid oils"),
    ],
    ("EU", "biodiesel"): [
        NatLine("38260010", "CN8", "FAME"),
        NatLine("38260090", "CN8", "Other biodiesel mixtures"),
    ],
    ("EU", "tallow"): [
        NatLine("15021090", "CN8", "Inedible tallow"),
    ],
    ("EU", "tall_oil"): [
        NatLine("38030010", "CN8", "Crude tall oil"),
        NatLine("38030090", "CN8", "Other tall oil"),
    ],
    # ---- Indonesia (BPS, AHTN8) ----
    ("IDN", "pome"): [
        NatLine("15220090", "AHTN8", "Other fatty residues — POME's usual export line"),
    ],
    ("IDN", "pfad_acid"): [
        NatLine("38231990", "AHTN8", "Other industrial fatty acids — PFAD's usual line"),
    ],
    ("IDN", "uco"): [
        NatLine("15180060", "AHTN8", "Inedible mixtures/preparations of fats & oils"),
    ],
    # ---- Malaysia (DOSM, AHTN8) ----
    ("MYS", "pome"): [
        NatLine("15220090", "AHTN8", "Other fatty residues — incl. sludge palm oil"),
    ],
    ("MYS", "pfad_acid"): [
        NatLine("38231990", "AHTN8", "Other industrial fatty acids — PFAD's usual line"),
    ],
    # ---- USA (Census, HTS10) ----
    ("USA", "uco"): [
        NatLine("1518004000", "HTS10", "Inedible animal/vegetable fat & oil mixtures — UCO import line"),
    ],
    ("USA", "tco"): [
        NatLine("1515290040", "HTS10", "Corn oil, other — technical/distillers corn oil exports"),
    ],
    ("USA", "tall_oil"): [
        NatLine("3803000000", "HTS10", "Tall oil"),
    ],
    # ---- Brazil (Comex Stat, NCM8) ----
    ("BRA", "tallow"): [
        NatLine("15021011", "NCM8", "Bovine tallow, raw"),
        NatLine("15021019", "NCM8", "Bovine tallow, other"),
    ],
    ("BRA", "soy"): [
        NatLine("15071000", "NCM8", "Crude soybean oil"),
        NatLine("15079011", "NCM8", "Refined soybean oil"),
    ],
    # ---- China (GACC, 10-digit; no open API — mirror data is the v1 route) ----
    ("CHN", "uco"): [
        NatLine("15180000", "GACC10", "No national UCO split — track via EU/US/SGP mirror imports"),
    ],
}


def lines_for(jurisdiction: str, slug: str) -> list[NatLine]:
    return NATIONAL_LINES.get((jurisdiction, slug), [])


def slug_for_national_code(jurisdiction: str, code: str) -> str | None:
    """National tariff code (any punctuation/spacing) -> the slug it belongs
    to, scoped to one jurisdiction. Used by ingestion pipelines to interpret
    a national code without needing the caller to already know the slug."""
    normalized = code.replace(" ", "").replace(".", "")
    for (jur, slug), lines in NATIONAL_LINES.items():
        if jur == jurisdiction and any(line.code == normalized for line in lines):
            return slug
    return None

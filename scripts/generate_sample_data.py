"""Generate the bundled synthetic sample dataset (deterministic).

SYNTHETIC DATA: magnitudes and shares are hand-curated to realistic 2024
orders of magnitude with plausible trends and corridors, then jittered with a
hash-based deterministic noise function (no RNG state, no wall clock — the
output is byte-stable). Unit values are engineered per corridor so the
feedstock-disaggregation signals demo meaningfully offline (e.g. Indonesia →
Rotterdam flows under HS 1522 price like POME, intra-EU flows like soapstock).

Run:  python scripts/generate_sample_data.py
Writes: data/sample/sample_trade.json  (committed to the repo)
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.registry.countries import RD_SAF_HUBS  # noqa: E402

YEARS = list(range(2018, 2025))
OUT = ROOT / "data" / "sample" / "sample_trade.json"

# world_x: world export value 2024 (USD). trend: per-year multiplier on world_x.
# exporters/importers: (iso3, share of world). usd_per_t: base unit value.
# codes: (hs_code, share_of_value) — sub-heading split where relevant.
ANCHORS = {
    "uco": dict(
        codes=[("1518", 1.0)], world_x=6.0e9, usd_per_t=950,
        trend={2018: .40, 2019: .45, 2020: .50, 2021: .70, 2022: .95, 2023: 1.0, 2024: 1.0},
        exporters=[("CHN", .38), ("NLD", .08), ("GBR", .06), ("DEU", .06), ("MYS", .05),
                   ("IDN", .05), ("ARE", .03), ("JPN", .03), ("KOR", .025), ("THA", .025)],
        importers=[("USA", .28), ("NLD", .22), ("SGP", .07), ("ESP", .06), ("DEU", .05),
                   ("GBR", .05), ("ITA", .04), ("FIN", .03), ("BEL", .03), ("PRT", .02)],
    ),
    "tallow": dict(
        codes=[("1502", 1.0)], world_x=4.2e9, usd_per_t=1050,
        trend={2018: .75, 2019: .78, 2020: .72, 2021: .85, 2022: 1.05, 2023: 1.10, 2024: 1.0},
        exporters=[("AUS", .27), ("USA", .13), ("NZL", .11), ("BRA", .10), ("CAN", .07),
                   ("ARG", .05), ("URY", .04), ("PRY", .03), ("IRL", .03), ("FRA", .03)],
        importers=[("USA", .34), ("SGP", .13), ("NLD", .08), ("CHN", .06), ("MEX", .05),
                   ("BEL", .04), ("GBR", .04), ("ITA", .03), ("KOR", .03), ("JPN", .02)],
    ),
    "pome": dict(
        codes=[("1522", 1.0)], world_x=1.3e9, usd_per_t=500,
        trend={2018: .30, 2019: .35, 2020: .45, 2021: .65, 2022: .95, 2023: 1.05, 2024: 1.0},
        exporters=[("IDN", .42), ("MYS", .30), ("THA", .05), ("ESP", .04), ("ITA", .03),
                   ("DEU", .03), ("NLD", .03), ("GTM", .02), ("HND", .02), ("COL", .02)],
        importers=[("NLD", .30), ("SGP", .15), ("ESP", .12), ("ITA", .10), ("FIN", .08),
                   ("GBR", .05), ("PRT", .04), ("DEU", .04), ("KOR", .03), ("JPN", .02)],
    ),
    "pfad_acid": dict(
        codes=[("382319", 1.0)], world_x=3.2e9, usd_per_t=700,
        trend={2018: .70, 2019: .72, 2020: .68, 2021: .90, 2022: 1.15, 2023: 1.05, 2024: 1.0},
        exporters=[("IDN", .34), ("MYS", .27), ("THA", .05), ("NLD", .05), ("ARG", .05),
                   ("BRA", .04), ("DEU", .04), ("ESP", .03), ("USA", .03), ("PNG", .02)],
        importers=[("NLD", .18), ("SGP", .12), ("IND", .11), ("ESP", .08), ("ITA", .07),
                   ("CHN", .07), ("DEU", .06), ("FIN", .05), ("USA", .04), ("MYS", .03)],
    ),
    "tall_oil": dict(
        codes=[("380300", 1.0)], world_x=0.65e9, usd_per_t=700,
        trend={2018: .85, 2019: .85, 2020: .80, 2021: .90, 2022: 1.10, 2023: 1.05, 2024: 1.0},
        exporters=[("USA", .30), ("SWE", .16), ("FIN", .14), ("BRA", .07), ("CAN", .06),
                   ("RUS", .06), ("POL", .04), ("DEU", .04), ("NOR", .03), ("CHL", .03)],
        importers=[("DEU", .15), ("NLD", .13), ("FIN", .12), ("USA", .10), ("SWE", .08),
                   ("GBR", .06), ("IND", .06), ("CHN", .06), ("JPN", .04), ("BEL", .04)],
    ),
    "tofa": dict(
        codes=[("382313", 1.0)], world_x=0.9e9, usd_per_t=1150,
        trend={2018: .85, 2019: .85, 2020: .82, 2021: .95, 2022: 1.10, 2023: 1.05, 2024: 1.0},
        exporters=[("USA", .28), ("SWE", .18), ("FIN", .15), ("NLD", .07), ("DEU", .05),
                   ("AUT", .04), ("GBR", .04), ("POL", .03), ("CAN", .03), ("JPN", .02)],
        importers=[("DEU", .16), ("NLD", .12), ("CHN", .10), ("USA", .09), ("GBR", .07),
                   ("IND", .06), ("JPN", .06), ("BEL", .05), ("FRA", .05), ("KOR", .04)],
    ),
    "tco": dict(
        codes=[("151521", 0.25), ("151529", 0.75)], world_x=2.2e9, usd_per_t=1250,
        trend={2018: .70, 2019: .72, 2020: .75, 2021: .95, 2022: 1.20, 2023: 1.05, 2024: 1.0},
        exporters=[("USA", .28), ("TUR", .09), ("UKR", .08), ("ARG", .07), ("HUN", .06),
                   ("FRA", .06), ("BRA", .05), ("ITA", .04), ("ESP", .04), ("DEU", .03)],
        importers=[("NLD", .13), ("CAN", .12), ("GBR", .09), ("DEU", .08), ("ESP", .07),
                   ("USA", .07), ("MEX", .06), ("BEL", .05), ("ITA", .04), ("FRA", .04)],
    ),
    "palm": dict(
        codes=[("1511", 1.0)], world_x=36e9, usd_per_t=900,
        trend={2018: .75, 2019: .70, 2020: .85, 2021: 1.30, 2022: 1.55, 2023: 1.05, 2024: 1.0},
        exporters=[("IDN", .50), ("MYS", .26), ("THA", .04), ("GTM", .03), ("COL", .03),
                   ("NLD", .03), ("PNG", .02), ("HND", .02), ("ECU", .01), ("DEU", .01)],
        importers=[("IND", .22), ("CHN", .14), ("NLD", .07), ("PAK", .07), ("ESP", .05),
                   ("USA", .04), ("ITA", .04), ("EGY", .03), ("KEN", .03), ("TUR", .03)],
    ),
    "soy": dict(
        codes=[("1507", 1.0)], world_x=13e9, usd_per_t=1050,
        trend={2018: .65, 2019: .60, 2020: .75, 2021: 1.25, 2022: 1.45, 2023: 1.05, 2024: 1.0},
        exporters=[("ARG", .38), ("BRA", .17), ("USA", .08), ("NLD", .05), ("PRY", .05),
                   ("ESP", .04), ("RUS", .04), ("UKR", .03), ("BOL", .03), ("DEU", .02)],
        importers=[("IND", .30), ("CHN", .08), ("PER", .04), ("MAR", .04), ("EGY", .04),
                   ("COL", .04), ("KOR", .03), ("VNM", .03), ("POL", .03), ("DEU", .03)],
    ),
    "rapeseed": dict(
        codes=[("1514", 1.0)], world_x=11e9, usd_per_t=1050,
        trend={2018: .60, 2019: .62, 2020: .72, 2021: 1.10, 2022: 1.45, 2023: 1.05, 2024: 1.0},
        exporters=[("CAN", .34), ("DEU", .13), ("NLD", .09), ("BEL", .06), ("AUS", .05),
                   ("FRA", .05), ("RUS", .04), ("POL", .04), ("CZE", .03), ("HUN", .03)],
        importers=[("USA", .30), ("CHN", .12), ("DEU", .08), ("NLD", .07), ("FRA", .05),
                   ("BEL", .04), ("NOR", .03), ("POL", .03), ("KOR", .02), ("JPN", .02)],
    ),
    "sunflower": dict(
        codes=[("1512", 1.0)], world_x=14e9, usd_per_t=950,
        trend={2018: .55, 2019: .60, 2020: .70, 2021: 1.15, 2022: 1.35, 2023: 1.0, 2024: 1.0},
        exporters=[("UKR", .38), ("RUS", .25), ("ARG", .06), ("TUR", .05), ("HUN", .04),
                   ("BGR", .04), ("NLD", .03), ("ROU", .03), ("ESP", .02), ("FRA", .02)],
        importers=[("IND", .25), ("CHN", .12), ("TUR", .09), ("EGY", .06), ("ITA", .05),
                   ("ESP", .05), ("NLD", .05), ("GBR", .03), ("DEU", .03), ("POL", .02)],
    ),
    "biodiesel": dict(
        codes=[("3826", 1.0)], world_x=14e9, usd_per_t=1250,
        trend={2018: .65, 2019: .70, 2020: .75, 2021: 1.00, 2022: 1.35, 2023: 1.05, 2024: 1.0},
        exporters=[("DEU", .16), ("NLD", .14), ("BEL", .09), ("CHN", .09), ("MYS", .06),
                   ("SGP", .06), ("USA", .05), ("AUT", .04), ("ESP", .04), ("IDN", .03)],
        importers=[("NLD", .18), ("USA", .12), ("GBR", .11), ("DEU", .10), ("BEL", .07),
                   ("FRA", .06), ("ESP", .05), ("ITA", .05), ("CAN", .04), ("CHE", .03)],
    ),
    "ethanol": dict(
        codes=[("220710", 0.45), ("220720", 0.55)], world_x=12e9, usd_per_t=700,
        trend={2018: .75, 2019: .78, 2020: .80, 2021: .95, 2022: 1.15, 2023: 1.05, 2024: 1.0},
        exporters=[("USA", .30), ("BRA", .13), ("NLD", .07), ("FRA", .06), ("GBR", .05),
                   ("CHN", .05), ("PAK", .04), ("BEL", .04), ("DEU", .03), ("HUN", .03)],
        importers=[("CAN", .12), ("GBR", .09), ("NLD", .09), ("DEU", .08), ("JPN", .07),
                   ("KOR", .07), ("IND", .05), ("PHL", .04), ("COL", .04), ("MEX", .04)],
    ),
}

PALM_BELT = {"IDN", "MYS", "THA", "PNG"}


def jitter(key: str, lo: float, hi: float) -> float:
    """Deterministic pseudo-noise in [lo, hi] from a string key."""
    h = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    return lo + (h % 100_000) / 100_000 * (hi - lo)


def corridor_usd_per_t(slug: str, base: float, origin: str, dest: str) -> float:
    """Engineer unit values so shared-heading corridors are separable — this is
    what makes the signals layer demonstrable on sample data.

    origin == "WLD" happens on import world-aggregate rows; infer from the
    destination (hub importers of these residues buy the fuel-bound grade).
    """
    hub = dest in RD_SAF_HUBS
    palm_origin = origin in PALM_BELT or (origin == "WLD" and hub)
    if slug == "pome":
        return 620 if (palm_origin and hub) else 380
    if slug == "pfad_acid":
        return 780 if palm_origin else 640
    if slug == "tco":
        return 1000 if (origin == "USA" or (origin == "WLD" and hub)) else 1350
    if slug == "uco":
        return 950 if (origin in ("CHN", "WLD") or hub) else 1500
    return base


def emit(records: list, slug: str, spec: dict, reporter: str, partner: str,
         flow: str, year: int, value: float) -> None:
    for code, code_share in spec["codes"]:
        v = value * code_share
        origin = reporter if flow == "X" else partner
        dest = partner if flow == "X" else reporter
        price = corridor_usd_per_t(slug, spec["usd_per_t"], origin, dest)
        price *= jitter(f"p|{slug}|{code}|{reporter}|{partner}|{flow}|{year}", 0.92, 1.08)
        records.append([reporter, partner, flow, code, year,
                        round(v), round(v / price * 1000)])


def build() -> dict:
    records: list = []
    for slug in sorted(ANCHORS):
        spec = ANCHORS[slug]
        for flow, side, counter_side in (("X", "exporters", "importers"),
                                         ("M", "importers", "exporters")):
            for iso, share in spec[side]:
                for year in YEARS:
                    total = (spec["world_x"] * spec["trend"][year] * share
                             * jitter(f"t|{slug}|{flow}|{iso}|{year}", 0.85, 1.15))
                    emit(records, slug, spec, iso, "WLD", flow, year, total)
                    # partner split over the opposite side's top countries
                    partners = [(p, s) for p, s in spec[counter_side] if p != iso][:6]
                    weights = [s * jitter(f"w|{slug}|{flow}|{iso}|{p}|{year}", 0.6, 1.4)
                               for p, s in partners]
                    wsum = sum(weights) or 1.0
                    for (p, _), w in zip(partners, weights):
                        emit(records, slug, spec, iso, p, flow, year,
                             total * 0.97 * w / wsum)
    return {
        "disclaimer": (
            "SYNTHETIC SAMPLE DATA — hand-curated magnitudes with deterministic "
            "noise, for offline demo/testing only. Not real customs statistics."
        ),
        "columns": ["reporter", "partner", "flow", "code", "year", "value_usd", "net_wgt_kg"],
        "records": records,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build()
    OUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"wrote {OUT} ({len(payload['records'])} records)")


if __name__ == "__main__":
    main()

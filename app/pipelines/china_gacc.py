"""China GACC ingestion slot — local file only, by necessity.

GACC's query portal (stats.customs.gov.cn) sits behind registration that
requires mainland-China real-name verification, and direct fetches from
abroad are blocked (verified: HTTP 403 from this build environment). There
is no free automated route to China's own declarations today; the roadmap
note in the README lists the paid/manual options being considered.

Until one of those is chosen, China's flows are triangulated from MIRROR
data (see app/signals/china_mirror.py). This module exists so that the
moment Chinese data is obtained — bought from a reseller, exported manually
by someone with portal access, etc. — it drops straight into the app via
the shared CSV schema (app/pipelines/national_csv.py) and
GET /api/origin-check?reporter=CHN starts working.
"""

import os
from pathlib import Path

from .national_csv import NationalCsvSource

JURISDICTION = "CHN"
CODE_SYSTEM = "GACC10"
DEFAULT_PATH = Path("data/local/china_gacc.csv")


def build(csv_path: Path | None = None) -> NationalCsvSource:
    path = csv_path or Path(os.environ.get("CHINA_GACC_CSV", str(DEFAULT_PATH)))
    return NationalCsvSource(JURISDICTION, CODE_SYSTEM, path)

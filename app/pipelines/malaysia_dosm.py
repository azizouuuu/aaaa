"""Malaysia DOSM external-trade ingestion.

See app/pipelines/national_csv.py for the schema and why this reads a local
file: OpenDOSM (https://open.dosm.gov.my/data-catalogue) publishes external
trade series, but this build could not verify a stable public API for
bilateral AHTN8-level trade at the confidence level of Comtrade/Eurostat.
Download the relevant table, normalize it to the CSV schema documented in
national_csv.py, and point MALAYSIA_DOSM_CSV at it.
"""

import os
from pathlib import Path

from .national_csv import NationalCsvSource

JURISDICTION = "MYS"
CODE_SYSTEM = "AHTN8"
DEFAULT_PATH = Path("data/local/malaysia_dosm.csv")


def build(csv_path: Path | None = None) -> NationalCsvSource:
    path = csv_path or Path(os.environ.get("MALAYSIA_DOSM_CSV", str(DEFAULT_PATH)))
    return NationalCsvSource(JURISDICTION, CODE_SYSTEM, path)

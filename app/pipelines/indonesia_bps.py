"""Indonesia BPS export/import ingestion.

See app/pipelines/national_csv.py for the schema and why this reads a local
file: https://www.bps.go.id/exim/ publishes "Ekspor/Impor Menurut Kode HS
dan Negara Tujuan/Asal" tables for download, but there is no stable public
API for bilateral AHTN8 trade this build could verify. Download the table
for the codes/years you need, normalize it to the CSV schema documented in
national_csv.py, and point INDONESIA_BPS_CSV at it.
"""

import os
from pathlib import Path

from .national_csv import NationalCsvSource

JURISDICTION = "IDN"
CODE_SYSTEM = "AHTN8"
DEFAULT_PATH = Path("data/local/indonesia_bps.csv")


def build(csv_path: Path | None = None) -> NationalCsvSource:
    path = csv_path or Path(os.environ.get("INDONESIA_BPS_CSV", str(DEFAULT_PATH)))
    return NationalCsvSource(JURISDICTION, CODE_SYSTEM, path)

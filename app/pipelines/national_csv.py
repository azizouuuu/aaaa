"""Shared local-file ingestion for national statistics offices without a
verified public API in this build (Indonesia BPS, Malaysia DOSM).

Unlike UN Comtrade and Eurostat Comext — both long-standing services with
documented, stable APIs — neither Indonesia's BPS nor Malaysia's DOSM
publishes (to this author's confident knowledge) a stable public API for
granular bilateral HS-code trade data. Rather than write a "live pipeline"
against endpoint details that would be guessed, not documented, these
sources read from a LOCAL CSV file that a user downloads from the office's
own portal and normalizes to one stable schema:

    hs_code,partner,flow,year,value_usd,net_wgt_kg

  hs_code     national tariff code (e.g. AHTN8 "15220090"), any punctuation
  partner     ISO3, ISO2, or the country's common English name — resolved
              against app/registry/countries.py; unresolvable rows are
              skipped and reported as a warning, not silently dropped
  flow        "X" (export) or "M" (import)
  year        4-digit year
  value_usd   FOB/CIF value already in USD (BPS's own exim tables already
              publish USD; if a source reports local currency, convert
              before loading — this loader does not do currency conversion)
  net_wgt_kg  optional; leave blank if unknown

Source pointers (for producing the normalized CSV):
  Indonesia BPS   https://www.bps.go.id/exim/  ("Ekspor/Impor Menurut Kode
                  HS dan Negara Tujuan/Asal")
  Malaysia DOSM   https://open.dosm.gov.my/data-catalogue (external trade)

This is deliberately NOT wired into the main PipelineRegistry (services.py)
as a drop-in replacement for Comtrade rankings/partners/trend: the AHTN8
lines catalogued in app/registry/national_codes.py for Indonesia and
Malaysia are single "other/residual" lines, and whether they fully partition
the corresponding HS6 heading is unverified — using them in place of
Comtrade's totals risks silently understating a country's trade if other
AHTN8 sub-lines exist that aren't catalogued yet. Instead, this feeds
app/signals/origin_confirmation.py, which surfaces the gap between a
country's own declaration and the global mirror rather than picking one.
"""

import csv
from pathlib import Path

from ..models import TradeRecord
from ..registry.countries import COUNTRIES
from ..registry.national_codes import slug_for_national_code
from .base import PipelineUnavailable

REQUIRED_COLUMNS = ("hs_code", "partner", "flow", "year", "value_usd")


def _resolve_partner(raw: str) -> str | None:
    raw = raw.strip()
    if raw.upper() in COUNTRIES:
        return raw.upper()
    by_name = {name.upper(): iso for iso, (_, name) in COUNTRIES.items()}
    return by_name.get(raw.upper())


def load_csv(path: Path, jurisdiction: str, reporter_iso3: str,
            code_system: str) -> tuple[list[TradeRecord], list[str]]:
    """Parse a normalized trade CSV for one reporter. Returns (records,
    warnings) — unresolvable rows are skipped and explained, never silently
    dropped without a trace."""
    if not path.exists():
        raise PipelineUnavailable(f"no local file at {path}")

    records: list[TradeRecord] = []
    warnings: list[str] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise PipelineUnavailable(f"{path}: missing required columns {missing}")

        for line_no, row in enumerate(reader, start=2):
            code = row["hs_code"].strip().replace(" ", "").replace(".", "")
            slug = slug_for_national_code(jurisdiction, code)
            if slug is None:
                warnings.append(f"line {line_no}: unrecognized code {code!r}, skipped")
                continue
            partner = _resolve_partner(row["partner"])
            if partner is None:
                warnings.append(f"line {line_no}: unrecognized partner {row['partner']!r}, skipped")
                continue
            flow = row["flow"].strip().upper()
            if flow not in ("X", "M"):
                warnings.append(f"line {line_no}: invalid flow {row['flow']!r}, skipped")
                continue
            try:
                year = int(row["year"])
                value_usd = float(row["value_usd"])
                net_wgt_kg = float(row["net_wgt_kg"]) if row.get("net_wgt_kg") else None
            except (ValueError, TypeError):
                warnings.append(f"line {line_no}: non-numeric year/value, skipped")
                continue
            records.append(TradeRecord(
                source=f"national_csv_{jurisdiction.lower()}", reporter=reporter_iso3,
                partner=partner, flow=flow, code=code, code_system=code_system,
                year=year, value_usd=value_usd, net_wgt_kg=net_wgt_kg,
            ))
    return records, warnings


class NationalCsvSource:
    """Thin, jurisdiction-specific wrapper — see indonesia_bps.py and
    malaysia_dosm.py for the two instances of this shape."""

    def __init__(self, jurisdiction: str, code_system: str, csv_path: Path):
        self.jurisdiction = jurisdiction
        self.code_system = code_system
        self.csv_path = csv_path

    def available(self) -> bool:
        return self.csv_path.exists()

    def load(self) -> tuple[list[TradeRecord], list[str]]:
        return load_csv(self.csv_path, self.jurisdiction, self.jurisdiction, self.code_system)

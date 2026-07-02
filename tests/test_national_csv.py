import pytest

from app.pipelines import indonesia_bps, malaysia_dosm
from app.pipelines.base import PipelineUnavailable
from app.pipelines.national_csv import load_csv
from app.signals.origin_confirmation import confirm


def _write_csv(path, rows, columns=("hs_code", "partner", "flow", "year", "value_usd", "net_wgt_kg")):
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row.get(c, "")) for c in columns))
    path.write_text("\n".join(lines) + "\n")


def test_load_csv_parses_valid_rows(tmp_path):
    path = tmp_path / "idn.csv"
    _write_csv(path, [
        {"hs_code": "15220090", "partner": "NLD", "flow": "X", "year": 2024,
         "value_usd": 1_000_000, "net_wgt_kg": 500_000},
        {"hs_code": "15220090", "partner": "Netherlands", "flow": "X", "year": 2023,
         "value_usd": 800_000, "net_wgt_kg": 400_000},
    ])
    records, warnings = load_csv(path, "IDN", "IDN", "AHTN8")
    assert warnings == []
    assert len(records) == 2
    assert records[0].reporter == "IDN"
    assert records[0].partner == "NLD"
    assert records[1].partner == "NLD"  # resolved from the English name
    assert records[0].code == "15220090"


def test_load_csv_skips_unrecognized_code_with_warning(tmp_path):
    path = tmp_path / "idn.csv"
    _write_csv(path, [{"hs_code": "99999999", "partner": "NLD", "flow": "X",
                       "year": 2024, "value_usd": 1000, "net_wgt_kg": ""}])
    records, warnings = load_csv(path, "IDN", "IDN", "AHTN8")
    assert records == []
    assert "unrecognized code" in warnings[0]


def test_load_csv_skips_unrecognized_partner_with_warning(tmp_path):
    path = tmp_path / "idn.csv"
    _write_csv(path, [{"hs_code": "15220090", "partner": "Narnia", "flow": "X",
                       "year": 2024, "value_usd": 1000, "net_wgt_kg": ""}])
    records, warnings = load_csv(path, "IDN", "IDN", "AHTN8")
    assert records == []
    assert "unrecognized partner" in warnings[0]


def test_load_csv_skips_invalid_flow(tmp_path):
    path = tmp_path / "idn.csv"
    _write_csv(path, [{"hs_code": "15220090", "partner": "NLD", "flow": "Q",
                       "year": 2024, "value_usd": 1000, "net_wgt_kg": ""}])
    records, warnings = load_csv(path, "IDN", "IDN", "AHTN8")
    assert records == []
    assert "invalid flow" in warnings[0]


def test_load_csv_missing_file_raises_unavailable(tmp_path):
    with pytest.raises(PipelineUnavailable):
        load_csv(tmp_path / "does_not_exist.csv", "IDN", "IDN", "AHTN8")


def test_load_csv_missing_columns_raises_unavailable(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("hs_code,partner\n15220090,NLD\n")
    with pytest.raises(PipelineUnavailable):
        load_csv(path, "IDN", "IDN", "AHTN8")


def test_indonesia_bps_build_reads_env_var(monkeypatch, tmp_path):
    custom = tmp_path / "custom.csv"
    monkeypatch.setenv("INDONESIA_BPS_CSV", str(custom))
    source = indonesia_bps.build()
    assert source.csv_path == custom
    assert source.available() is False


def test_malaysia_dosm_build_default_path():
    source = malaysia_dosm.build()
    assert source.jurisdiction == "MYS"
    assert source.code_system == "AHTN8"


def test_origin_confirmation_unavailable_when_no_file(tmp_path):
    source = indonesia_bps.build(csv_path=tmp_path / "missing.csv")

    class FakeRegistry:
        def fetch(self, q):
            return [], "sample"

    result = confirm("pome", "IDN", 2024, source, FakeRegistry())
    assert result.available is False
    assert "No local file" in result.note


def test_origin_confirmation_flags_agreement(tmp_path):
    path = tmp_path / "idn.csv"
    _write_csv(path, [{"hs_code": "15220090", "partner": "NLD", "flow": "X",
                       "year": 2024, "value_usd": 1_000_000, "net_wgt_kg": ""}])
    source = indonesia_bps.build(csv_path=path)

    class FakeRegistry:
        def fetch(self, q):
            from app.models import TradeRecord
            return [TradeRecord(source="sample", reporter="IDN", partner="WLD",
                                flow="X", code="1522", code_system="HS6", year=2024,
                                value_usd=1_050_000, net_wgt_kg=None)], "sample"

    result = confirm("pome", "IDN", 2024, source, FakeRegistry())
    assert result.available is True
    assert 0.9 < result.ratio < 1.0
    assert "broadly agree" in result.note


def test_origin_confirmation_flags_shortfall(tmp_path):
    path = tmp_path / "idn.csv"
    _write_csv(path, [{"hs_code": "15220090", "partner": "NLD", "flow": "X",
                       "year": 2024, "value_usd": 100_000, "net_wgt_kg": ""}])
    source = indonesia_bps.build(csv_path=path)

    class FakeRegistry:
        def fetch(self, q):
            from app.models import TradeRecord
            return [TradeRecord(source="sample", reporter="IDN", partner="WLD",
                                flow="X", code="1522", code_system="HS6", year=2024,
                                value_usd=1_000_000, net_wgt_kg=None)], "sample"

    result = confirm("pome", "IDN", 2024, source, FakeRegistry())
    assert result.ratio < 0.85
    assert "other AHTN8 sub-lines" in result.note

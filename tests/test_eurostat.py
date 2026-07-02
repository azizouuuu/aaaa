from app.models import FlowQuery
from app.pipelines.eurostat_comext import (
    EurostatComextPipeline,
    _to_records,
    build_requests,
    cn8_lines_for_query,
    parse_jsonstat,
)
from app.signals.engine import disaggregate_flow
from app.signals.national_override import override_for


def _jsonstat_fixture():
    """NL reporter, partners ID (Indonesia) & MY (Malaysia), two CN8 lines
    under HS 1522 (POME's own line + a soapstock/degras line), flow=export
    side of Comext (code "2"), one year. Values are dense so every flat
    index 0..7 is populated."""
    return {
        "id": ["reporter", "partner", "product", "flow", "indicators", "time"],
        "size": [1, 2, 2, 1, 2, 1],
        "dimension": {
            "reporter": {"category": {"index": {"NL": 0}}},
            "partner": {"category": {"index": {"ID": 0, "MY": 1}}},
            "product": {"category": {"index": {"15220039": 0, "15220031": 1}}},
            "flow": {"category": {"index": {"2": 0}}},
            "indicators": {"category": {"index": {"VALUE_IN_EUROS": 0, "QUANTITY_IN_100KG": 1}}},
            "time": {"category": {"index": {"2024": 0}}},
        },
        "value": {
            "0": 2_000_000, "1": 20_000,   # ID, 15220039 (POME line)
            "2": 500_000, "3": 5_000,      # ID, 15220031 (soapstock line)
            "4": 1_000_000, "5": 10_000,   # MY, 15220039
            "6": 300_000, "7": 3_000,      # MY, 15220031
        },
    }


def test_cn8_lines_for_query_resolves_pome():
    lines = cn8_lines_for_query(("1522",))
    assert set(lines) == {"15220031", "15220039", "15220099"}


def test_cn8_lines_for_query_unknown_code_returns_empty():
    assert cn8_lines_for_query(("9999",)) == []


def test_build_requests_omits_partner_when_none():
    q = FlowQuery(("1522",), "X", (2024,), ("NLD",), None)
    reqs = build_requests(q, ["15220039"])
    assert len(reqs) == 1
    assert "partner" not in reqs[0]
    assert reqs[0]["reporter"] == "NL"
    assert reqs[0]["flow"] == "2"


def test_build_requests_uses_world_partner_code():
    q = FlowQuery(("1522",), "X", (2024,), ("NLD",), ("WLD",))
    reqs = build_requests(q, ["15220039"])
    assert reqs[0]["partner"] == "WORLD"


def test_build_requests_non_eu_partner_uses_iso2():
    q = FlowQuery(("1522",), "M", (2024,), ("NLD",), ("IDN",))
    reqs = build_requests(q, ["15220039"])
    assert reqs[0]["partner"] == "ID"
    assert reqs[0]["flow"] == "1"


def test_build_requests_splits_by_year():
    q = FlowQuery(("1522",), "X", (2023, 2024), ("NLD",), ("WLD",))
    reqs = build_requests(q, ["15220039"])
    assert {r["time"] for r in reqs} == {"2023", "2024"}


def test_build_requests_empty_without_cn8_codes():
    q = FlowQuery(("1522",), "X", (2024,), ("NLD",), ("WLD",))
    assert build_requests(q, []) == []


def test_parse_jsonstat_decodes_all_cells():
    rows = parse_jsonstat(_jsonstat_fixture())
    assert len(rows) == 8
    first = next(r for r in rows if r["partner"] == "ID" and r["product"] == "15220039"
                and r["indicators"] == "VALUE_IN_EUROS")
    assert first["value"] == 2_000_000
    assert first["reporter"] == "NL"
    assert first["time"] == "2024"


def test_to_records_groups_indicators_and_converts_currency():
    rows = parse_jsonstat(_jsonstat_fixture())
    records = _to_records(rows)
    assert len(records) == 4  # 2 partners x 2 products
    idn_pome = next(r for r in records if r.partner == "IDN" and r.code == "15220039")
    assert idn_pome.reporter == "NLD"
    assert idn_pome.value_usd == 2_000_000 * 1.08
    assert idn_pome.net_wgt_kg == 20_000 * 100.0
    assert idn_pome.code_system == "CN8"
    assert idn_pome.flow == "X"

    mys_soap = next(r for r in records if r.partner == "MYS" and r.code == "15220031")
    assert mys_soap.value_usd == 300_000 * 1.08


def test_covers_direct_eu_reporter():
    p = EurostatComextPipeline.__new__(EurostatComextPipeline)  # no store needed for covers()
    q = FlowQuery(("1522",), "X", (2024,), ("NLD",), None)
    assert p.covers(q) is True


def test_covers_mirror_via_eu_partner():
    p = EurostatComextPipeline.__new__(EurostatComextPipeline)
    q = FlowQuery(("1522",), "X", (2024,), ("IDN",), ("NLD",))
    assert p.covers(q) is True


def test_covers_false_when_neither_side_is_eu():
    p = EurostatComextPipeline.__new__(EurostatComextPipeline)
    q = FlowQuery(("1522",), "X", (2024,), ("IDN",), ("MYS",))
    assert p.covers(q) is False


def test_covers_false_for_unshared_commodity_no_cn8_lines():
    p = EurostatComextPipeline.__new__(EurostatComextPipeline)
    q = FlowQuery(("1507",), "X", (2024,), ("NLD",), None)  # soy oil — no EU national lines
    assert p.covers(q) is False


def test_fetch_mirror_flips_reporter_partner_and_flow(monkeypatch):
    pipeline = EurostatComextPipeline.__new__(EurostatComextPipeline)
    pipeline.store = type("S", (), {"upsert_flows": lambda self, recs: None})()

    def fake_eu_oriented(self, q):
        assert q.reporters == ("NLD",)  # flipped: EU country is now "reporter"
        assert q.partners == ("IDN",)
        assert q.flow == "M"  # export from IDN's perspective = NL's import
        rows = parse_jsonstat(_jsonstat_fixture())
        return [r for r in _to_records(rows) if r.partner == "IDN"]

    monkeypatch.setattr(EurostatComextPipeline, "_fetch_eu_oriented", fake_eu_oriented)
    q = FlowQuery(("1522",), "X", (2024,), ("IDN",), ("NLD",))
    records = pipeline.fetch(q)
    assert all(r.reporter == "IDN" and r.partner == "NLD" and r.flow == "X" for r in records)


def test_national_override_confirms_pome_line():
    ov = override_for("CN8", "15220039")
    assert ov.candidate == "pome"
    assert ov.certain is True


def test_national_override_unknown_line_returns_none():
    assert override_for("CN8", "99999999") is None


def test_disaggregate_flow_uses_national_line_when_present():
    rows = parse_jsonstat(_jsonstat_fixture())
    corridor_rows = [r for r in _to_records(rows) if r.partner == "IDN"]  # pome + soapstock lines
    result = disaggregate_flow("pome", "IDN", "NLD", 2024, "X", corridor_rows)
    assert result.basis == "national_tariff_line"
    assert result.confidence == "high"
    by_key = dict(result.candidates)
    # value split: pome line 2,000,000 EUR vs soapstock line 500,000 EUR (pre-FX; ratio is FX-invariant)
    assert abs(by_key["pome"] - 2_000_000 / 2_500_000) < 1e-6
    assert abs(by_key["soapstock_degras"] - 500_000 / 2_500_000) < 1e-6


def test_disaggregate_flow_falls_back_to_heuristic_without_national_rows():
    from app.models import TradeRecord
    rows = [TradeRecord(source="comtrade", reporter="IDN", partner="NLD", flow="X",
                        code="1522", code_system="HS6", year=2024,
                        value_usd=650_000, net_wgt_kg=1_000_000)]
    result = disaggregate_flow("pome", "IDN", "NLD", 2024, "X", rows)
    assert result.basis == "heuristic"

from fastapi.testclient import TestClient

from app.main import app
from app.pipelines.brazil_comexstat import (
    BrazilComexStatPipeline,
    _to_records,
    build_request,
    parse_response,
)
from app.signals.origin_confirmation import confirm

client = TestClient(app)


def _payload_fixture():
    return {
        "data": {
            "list": [
                {"country": "Paises Baixos (Holanda)", "ncm": "15021011",
                 "year": "2024", "metricFOB": 12_000_000, "metricKG": 10_000_000},
                {"country": "China", "ncm": "15021019",
                 "year": "2024", "metricFOB": 3_000_000, "metricKG": 2_500_000},
                {"country": "Nárnia", "ncm": "15021011",
                 "year": "2024", "metricFOB": 500_000, "metricKG": 400_000},
            ]
        }
    }


def test_build_request_shape():
    body = build_request("X", ["15021011", "15021019"], (2023, 2024), ("NLD",))
    assert body["flow"] == "export"
    assert body["period"] == {"from": "2023-01", "to": "2024-12"}
    assert {"filter": "ncm", "values": ["15021011", "15021019"]} in body["filters"]
    assert {"filter": "country", "values": ["NLD"]} in body["filters"]


def test_build_request_omits_country_filter_for_world():
    body = build_request("X", ["15021011"], (2024,), ("WLD",))
    assert len(body["filters"]) == 1


def test_parse_response_handles_nested_list():
    rows = parse_response(_payload_fixture())
    assert len(rows) == 3


def test_parse_response_handles_bare_list():
    rows = parse_response([{"country": "China", "ncm": "1", "year": "2024", "metricFOB": 1}])
    assert len(rows) == 1


def test_parse_response_handles_garbage():
    assert parse_response(None) == []
    assert parse_response("oops") == []


def test_to_records_resolves_names_and_warns_on_unknown():
    rows = parse_response(_payload_fixture())
    records, warnings = _to_records(rows, "X")
    assert len(records) == 2
    assert len(warnings) == 1
    assert "Nárnia" in warnings[0]
    nld = next(r for r in records if r.partner == "NLD")
    assert nld.reporter == "BRA"
    assert nld.value_usd == 12_000_000
    assert nld.net_wgt_kg == 10_000_000
    assert nld.code_system == "NCM8"
    assert nld.flow == "X"


def test_pipeline_unavailable_in_sample_mode(monkeypatch):
    monkeypatch.setattr("app.pipelines.brazil_comexstat.config.DATA_MODE", "sample")
    pipeline = BrazilComexStatPipeline()
    assert pipeline.available() is False


def test_pipeline_available_in_auto_mode(monkeypatch):
    monkeypatch.setattr("app.pipelines.brazil_comexstat.config.DATA_MODE", "auto")
    pipeline = BrazilComexStatPipeline()
    assert pipeline.available() is True


def test_fetch_corridor_no_catalogued_lines_returns_warning():
    pipeline = BrazilComexStatPipeline()
    records, warnings = pipeline.fetch_corridor("uco", "X", (2024,))  # no BRA/uco line
    assert records == []
    assert "no catalogued NCM8 lines" in warnings[0]


def test_fetch_corridor_uses_live_call(monkeypatch):
    pipeline = BrazilComexStatPipeline()
    monkeypatch.setattr(pipeline, "_post_cached", lambda body: _payload_fixture())
    records, warnings = pipeline.fetch_corridor("tallow", "X", (2024,))
    assert len(records) == 2
    assert warnings  # the unrecognized-country warning survives


def test_origin_confirmation_uses_brazil_live_source(monkeypatch):
    pipeline = BrazilComexStatPipeline()
    monkeypatch.setattr("app.pipelines.brazil_comexstat.config.DATA_MODE", "auto")
    monkeypatch.setattr(pipeline, "_post_cached", lambda body: _payload_fixture())

    class FakeRegistry:
        def fetch(self, q):
            from app.models import TradeRecord
            return [TradeRecord(source="sample", reporter="BRA", partner="WLD",
                                flow="X", code="1502", code_system="HS6", year=2024,
                                value_usd=14_000_000, net_wgt_kg=None)], "sample"

    result = confirm("tallow", "BRA", 2024, pipeline, FakeRegistry())
    assert result.available is True
    assert result.national_value_usd == 15_000_000.0  # NLD + China rows
    assert result.ratio is not None


def test_origin_check_unavailable_for_brazil_in_sample_mode():
    r = client.get("/api/origin-check", params={"cmd": "tallow", "reporter": "BRA", "year": 2024})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["available"] is False
    assert "live API" in data["note"] or "unavailable" in data["note"]

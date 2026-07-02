from fastapi.testclient import TestClient

from app.main import app
from app.models import FlowQuery
from app.pipelines.china_gacc import build as build_china
from app.pipelines.us_census import (
    UsCensusPipeline,
    build_requests,
    hts_lines_for_query,
    parse_response,
)
from app.services import get_registry
from app.signals.china_mirror import MIRROR_REPORTERS, triangulate
from app.signals.engine import disaggregate_flow

client = TestClient(app)


# ---- US Census pipeline -------------------------------------------------

def _census_fixture():
    """Array-of-arrays response shape: header row + data rows, including the
    '-' total row Census emits for all-countries."""
    return [
        ["CTY_CODE", "CTY_NAME", "GEN_VAL_YR", "I_COMMODITY", "time"],
        ["5700", "CHINA", "2200000000", "1518004000", "2024-12"],
        ["-", "TOTAL FOR ALL COUNTRIES", "3100000000", "1518004000", "2024-12"],
        ["4899", "SOME COUNTRY", "150000000", "1518004000", "2024-12"],
        ["5880", "NULLVALUE", "", "1518004000", "2024-12"],
    ]


def test_hts_lines_resolved_for_uco():
    assert hts_lines_for_query(("1518",)) == ["1518004000"]


def test_hts_lines_empty_for_uncovered_commodity():
    assert hts_lines_for_query(("1511",)) == []


def test_build_requests_one_per_year_and_code():
    q = FlowQuery(("1518",), "M", (2023, 2024), ("USA",), None)
    reqs = build_requests(q, ["1518004000"])
    assert len(reqs) == 2
    assert reqs[0]["I_COMMODITY"] == "1518004000"
    assert reqs[0]["time"].endswith("-12")


def test_build_requests_known_partner_becomes_cty_code():
    q = FlowQuery(("1518",), "M", (2024,), ("USA",), ("CHN",))
    reqs = build_requests(q, ["1518004000"])
    assert reqs[0]["CTY_CODE"] == "5700"


def test_build_requests_exports_use_export_vars():
    q = FlowQuery(("1518",), "X", (2024,), ("USA",), ("WLD",))
    reqs = build_requests(q, ["1518004000"])
    assert "E_COMMODITY" in reqs[0]
    assert "ALL_VAL_YR" in reqs[0]["get"]


def test_parse_response_maps_china_total_and_skips_nulls():
    records = parse_response(_census_fixture(), "M", 2024, "1518004000")
    assert len(records) == 3  # null-value row skipped
    china = next(r for r in records if r.partner == "CHN")
    assert china.value_usd == 2_200_000_000.0
    assert china.reporter == "USA"
    assert china.code_system == "HTS10"
    world = next(r for r in records if r.partner == "WLD")
    assert world.value_usd == 3_100_000_000.0
    unknown = next(r for r in records if r.partner.startswith("CTY:"))
    assert unknown.partner == "CTY:4899"


def test_census_covers_usa_reporter_and_usa_partner_mirror():
    p = UsCensusPipeline.__new__(UsCensusPipeline)
    assert p.covers(FlowQuery(("1518",), "M", (2024,), ("USA",), None)) is True
    assert p.covers(FlowQuery(("1518",), "X", (2024,), ("CHN",), ("USA",))) is True
    assert p.covers(FlowQuery(("1518",), "X", (2024,), ("CHN",), ("NLD",))) is False
    assert p.covers(FlowQuery(("1511",), "M", (2024,), ("USA",), None)) is False


def test_census_mirror_flip(monkeypatch):
    pipeline = UsCensusPipeline.__new__(UsCensusPipeline)
    pipeline.store = type("S", (), {"upsert_flows": lambda self, recs: None})()

    def fake_us_oriented(self, q):
        assert q.reporters == ("USA",)
        assert q.partners == ("CHN",)
        assert q.flow == "M"
        return parse_response(_census_fixture(), "M", 2024, "1518004000")

    monkeypatch.setattr(UsCensusPipeline, "_fetch_us_oriented", fake_us_oriented)
    q = FlowQuery(("1518",), "X", (2024,), ("CHN",), ("USA",))
    records = pipeline.fetch(q)
    assert len(records) == 1  # only the CHN row survives the flip filter
    assert records[0].reporter == "CHN"
    assert records[0].partner == "USA"
    assert records[0].flow == "X"


def test_hts10_override_feeds_engine_as_measured():
    records = parse_response(_census_fixture(), "M", 2024, "1518004000")
    corridor = [r for r in records if r.partner == "CHN"]
    result = disaggregate_flow("uco", "USA", "CHN", 2024, "M", corridor)
    assert result.basis == "national_tariff_line"
    # 1518004000 is certain=False -> whole value ambiguous-weighted -> medium
    assert result.confidence == "medium"
    assert result.candidates[0][0] == "uco"


# ---- China mirror triangulation ----------------------------------------

def test_triangulate_sums_mirrors_and_compares_own():
    result = triangulate("uco", 2024, get_registry(), "X")
    assert result.mirror_total_usd > 0
    assert result.own_declared_usd is not None
    assert result.ratio is not None
    assert len(result.breakdown) > 3
    assert result.breakdown[0]["value_usd"] >= result.breakdown[-1]["value_usd"]
    assert any("Mirror panel" in n for n in result.notes)


def test_triangulate_mirror_panel_is_reasonable():
    assert "USA" in MIRROR_REPORTERS and "SGP" in MIRROR_REPORTERS
    assert "CHN" not in MIRROR_REPORTERS


def test_china_mirror_endpoint():
    r = client.get("/api/china-mirror", params={"cmd": "uco", "year": 2024})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["mirror_total_usd"] > 0
    assert len(data["breakdown"]) > 0
    assert data["notes"]


def test_china_mirror_unknown_commodity_404():
    r = client.get("/api/china-mirror", params={"cmd": "nope"})
    assert r.status_code == 404


def test_origin_check_supports_china_slot():
    r = client.get("/api/origin-check", params={"cmd": "uco", "reporter": "CHN", "year": 2024})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["available"] is False  # no local GACC file — expected state
    assert "No local file" in data["note"]


def test_china_gacc_source_shape():
    source = build_china()
    assert source.jurisdiction == "CHN"
    assert source.code_system == "GACC10"

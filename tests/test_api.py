import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_sample_mode():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["data_mode"] == "sample"
    assert body["flows_stored"] > 0


def test_meta_lists_commodities():
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["commodities"]) == 13
    assert "hvo_saf_note" in data
    assert "asia" in data["watchlists"]


def test_rankings_envelope_and_sample_labeling():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "year": 2024})
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["data_mode"] == "sample"
    assert len(body["data"]["rows"]) > 0
    assert body["data"]["rows"][0]["value_usd"] > 0


def test_rankings_unknown_commodity_404():
    r = client.get("/api/rankings", params={"cmd": "nope", "flow": "X"})
    assert r.status_code == 404


def test_rankings_bad_flow_400():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "Z"})
    assert r.status_code == 400


def test_trend_world_has_all_years():
    r = client.get("/api/trend/world", params={"cmd": "pome"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["years"] == list(range(2018, 2025))
    assert len(data["exports"]) == len(data["years"])


def test_partners_returns_hub_flag():
    r = client.get("/api/partners", params={"cmd": "pome", "reporter": "IDN", "flow": "X", "year": 2024})
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    assert any(row["is_hub"] for row in rows)  # Netherlands should show up


def test_partners_unknown_reporter_404():
    r = client.get("/api/partners", params={"cmd": "pome", "reporter": "ZZZ", "flow": "X"})
    assert r.status_code == 404


def test_watchlist_asia_region():
    r = client.get("/api/watchlist", params={"region": "asia", "year": 2024})
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    isos = {row["iso3"] for row in rows}
    assert {"IDN", "MYS", "CHN"}.issubset(isos)


def test_watchlist_unknown_region_404():
    r = client.get("/api/watchlist", params={"region": "europe"})
    assert r.status_code == 404


def test_signals_flow_disaggregates_pome_corridor():
    r = client.get(
        "/api/signals/flow",
        params={"cmd": "pome", "reporter": "IDN", "partner": "NLD", "year": 2024, "flow": "X"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["candidates"][0]["key"] == "pome"
    assert data["basis"] == "heuristic"
    assert len(data["explanations"]) > 0


def test_signals_summary_shared_heading():
    r = client.get("/api/signals/summary", params={"cmd": "pfad_acid", "flow": "X", "year": 2024})
    assert r.status_code == 200
    assert len(r.json()["data"]["rows"]) > 0


def test_signals_summary_unshared_heading_returns_empty():
    r = client.get("/api/signals/summary", params={"cmd": "soy", "flow": "X", "year": 2024})
    assert r.status_code == 200
    assert r.json()["data"]["rows"] == []


def test_origination_flags_reporter_corridors():
    r = client.get(
        "/api/origination",
        params={"cmd": "pome", "flow": "X", "year": 2021, "reporter": "IDN"},
    )
    assert r.status_code == 200
    assert "corridor_flags" in r.json()["data"]


def test_mirror_check_reports_ratio():
    r = client.get("/api/mirror", params={"cmd": "uco", "exporter": "CHN", "importer": "USA", "year": 2024})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["available"] is True
    assert data["ratio"] is not None


def test_methodology_documents_shared_headings():
    r = client.get("/api/methodology")
    assert r.status_code == 200
    slugs = {g["slug"] for g in r.json()["data"]["shared_headings"]}
    assert {"pome", "pfad_acid", "tco", "uco", "tallow"}.issubset(slugs)


def test_static_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "Renewable Trade Monitor" in r.text

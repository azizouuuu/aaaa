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


def test_rankings_defaults_to_weight_and_sorts_by_it():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "year": 2024})
    data = r.json()["data"]
    assert data["metric"] == "wgt"
    weights = [row["net_wgt_t"] for row in data["rows"]]
    assert all(w is not None for w in weights)
    assert weights == sorted(weights, reverse=True)
    assert "world_total_wgt_t" in data and "world_total_usd" in data


def test_rankings_usd_metric_sorts_by_value():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "year": 2024, "metric": "usd"})
    data = r.json()["data"]
    assert data["metric"] == "usd"
    values = [row["value_usd"] for row in data["rows"]]
    assert values == sorted(values, reverse=True)


def test_rankings_bad_metric_400():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "metric": "kg"})
    assert r.status_code == 400


def test_trend_world_has_all_years():
    r = client.get("/api/trend/world", params={"cmd": "pome"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["years"] == list(range(2018, 2025))
    assert len(data["exports"]) == len(data["years"])
    assert "net_wgt_t" in data["exports"][0]


def test_partners_returns_hub_flag():
    r = client.get("/api/partners", params={"cmd": "pome", "reporter": "IDN", "flow": "X", "year": 2024})
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    assert any(row["is_hub"] for row in rows)  # Netherlands should show up


def test_partners_defaults_to_weight_and_sorts_by_it():
    r = client.get("/api/partners", params={"cmd": "pome", "reporter": "IDN", "flow": "X", "year": 2024})
    data = r.json()["data"]
    assert data["metric"] == "wgt"
    weights = [row["net_wgt_t"] for row in data["rows"]]
    assert weights == sorted(weights, reverse=True)


def test_partners_unknown_reporter_404():
    r = client.get("/api/partners", params={"cmd": "pome", "reporter": "ZZZ", "flow": "X"})
    assert r.status_code == 404


def test_partners_bad_metric_400():
    r = client.get("/api/partners", params={"cmd": "pome", "reporter": "IDN", "metric": "kg"})
    assert r.status_code == 400


def test_partners_trend_includes_weight_series():
    r = client.get("/api/partners/trend", params={"cmd": "pome", "reporter": "IDN", "flow": "X"})
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    assert all("net_wgt_t" in row for row in rows)


def test_watchlist_asia_region():
    r = client.get("/api/watchlist", params={"region": "asia", "year": 2024})
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    isos = {row["iso3"] for row in rows}
    assert {"IDN", "MYS", "CHN"}.issubset(isos)


def test_watchlist_defaults_to_weight_and_sorts_by_it():
    r = client.get("/api/watchlist", params={"region": "asia", "year": 2024})
    data = r.json()["data"]
    assert data["metric"] == "wgt"
    values = [row["metric_value"] or 0 for row in data["rows"]]
    assert values == sorted(values, reverse=True)
    assert all("net_wgt_t" in row["by_year"][0] for row in data["rows"])


def test_watchlist_usd_metric():
    r = client.get("/api/watchlist", params={"region": "sam", "year": 2024, "metric": "usd"})
    data = r.json()["data"]
    assert data["metric"] == "usd"
    values = [row["metric_value"] or 0 for row in data["rows"]]
    assert values == sorted(values, reverse=True)


def test_watchlist_bad_metric_400():
    r = client.get("/api/watchlist", params={"region": "asia", "metric": "kg"})
    assert r.status_code == 400


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


def test_origin_check_unavailable_without_local_file():
    r = client.get("/api/origin-check", params={"cmd": "pome", "reporter": "IDN", "year": 2024})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["available"] is False
    assert "No local file" in data["note"]


def test_origin_check_unknown_commodity_404():
    r = client.get("/api/origin-check", params={"cmd": "nope", "reporter": "IDN"})
    assert r.status_code == 404


def test_origin_check_unsupported_reporter_404():
    r = client.get("/api/origin-check", params={"cmd": "pome", "reporter": "USA"})
    assert r.status_code == 404

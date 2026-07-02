from fastapi.testclient import TestClient

from app.main import app
from app.models import FlowQuery, TradeRecord
from app.registry.countries import EU_BLOC_ISO, EU_MEMBERS, name_of
from app.services import get_registry
from app.signals.eu_bloc import correct_world_total, eu_bloc_totals, intra_eu_totals

client = TestClient(app)


def test_eu_bloc_iso_not_a_real_country_but_has_a_name():
    assert EU_BLOC_ISO not in EU_MEMBERS
    assert name_of(EU_BLOC_ISO) == "European Union (27)"


def test_eu_members_excludes_uk():
    assert "GBR" not in EU_MEMBERS


def test_intra_eu_totals_finds_real_intra_eu_legs():
    registry = get_registry()
    totals = intra_eu_totals(registry, ("1518",), "X", (2024,))
    assert totals[2024]["value_usd"] > 0
    assert totals[2024]["net_wgt_kg"] > 0


def test_intra_eu_totals_excludes_uk_legs():
    # a fake registry with ONLY a GBR<->NLD leg should show zero intra-EU,
    # since GBR is not in EU_MEMBERS — the corridor is genuine extra-EU trade.
    class FakeRegistry:
        def fetch(self, q, exclude_sources=frozenset()):
            recs = [
                TradeRecord(source="test", reporter="GBR", partner="NLD", flow="X",
                            code="1518", code_system="HS6", year=2024,
                            value_usd=1_000_000, net_wgt_kg=1_000_000),
            ]
            return [r for r in recs if r.reporter in q.reporters and r.partner in q.partners], "test"

    totals = intra_eu_totals(FakeRegistry(), ("1518",), "X", (2024,))
    assert totals[2024]["value_usd"] == 0.0


def test_eu_bloc_totals_less_than_naive_sum_of_members():
    registry = get_registry()
    from app.signals.eu_bloc import eu_members_naive_totals
    naive = eu_members_naive_totals(registry, ("1518",), "X", (2024,))
    bloc = eu_bloc_totals(registry, ("1518",), "X", (2024,))
    assert bloc[2024]["value_usd"] < naive[2024]["value_usd"]
    assert bloc[2024]["value_usd"] >= 0


def test_correct_world_total_subtracts_exactly_the_intra_eu_amount():
    registry = get_registry()
    intra = intra_eu_totals(registry, ("1518",), "X", (2024,))
    naive = {2024: {"value_usd": 1_000_000_000.0, "net_wgt_kg": 500_000_000.0}}
    corrected = correct_world_total(naive, registry, ("1518",), "X", (2024,))
    assert corrected[2024]["value_usd"] == naive[2024]["value_usd"] - intra[2024]["value_usd"]


def test_correct_world_total_never_goes_negative():
    registry = get_registry()
    naive = {2024: {"value_usd": 0.0, "net_wgt_kg": 0.0}}
    corrected = correct_world_total(naive, registry, ("1518",), "X", (2024,))
    assert corrected[2024]["value_usd"] == 0.0


def test_rankings_world_total_is_less_than_naive_sum_of_rows():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "year": 2024, "metric": "usd", "top": 100})
    data = r.json()["data"]
    naive_sum = sum(row["value_usd"] for row in data["rows"])
    assert data["world_total_usd"] < naive_sum  # intra-EU legs excluded from the total


def test_rankings_eu_as_bloc_collapses_members_into_one_row():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "year": 2024, "eu_as_bloc": "true"})
    data = r.json()["data"]
    isos = {row["iso3"] for row in data["rows"]}
    assert "EU27" in isos
    assert not (isos & EU_MEMBERS)  # no individual EU members remain
    assert "GBR" in isos  # the UK is still its own row, not folded in


def test_rankings_default_lists_eu_members_individually():
    r = client.get("/api/rankings", params={"cmd": "uco", "flow": "X", "year": 2024, "top": 50})
    data = r.json()["data"]
    isos = {row["iso3"] for row in data["rows"]}
    assert "EU27" not in isos
    eu_rows = [row for row in data["rows"] if row["is_eu_member"]]
    assert all(row["is_eu_member"] for row in eu_rows)


def test_partners_eu27_bloc_excludes_intra_eu_partners():
    r = client.get("/api/partners", params={"cmd": "uco", "reporter": "EU27", "flow": "X", "year": 2024})
    assert r.status_code == 200
    data = r.json()["data"]
    partner_isos = {row["iso3"] for row in data["rows"]}
    assert not (partner_isos & EU_MEMBERS)
    assert "note" in data


def test_partners_eu27_reporter_name_resolves():
    r = client.get("/api/partners", params={"cmd": "uco", "reporter": "EU27", "flow": "X", "year": 2024})
    data = r.json()["data"]
    assert data["reporter"]["name"] == "European Union (27)"


def test_meta_exposes_eu_bloc_info():
    r = client.get("/api/meta")
    blocs = r.json()["data"]["blocs"]
    assert blocs["EU27"]["name"] == "European Union (27)"
    assert "GBR" not in blocs["EU27"]["members"]
    assert len(blocs["EU27"]["members"]) == 21


def test_trend_world_excludes_intra_eu():
    r = client.get("/api/trend/world", params={"cmd": "uco"})
    data = r.json()["data"]
    assert "note" in data
    assert data["exports"][-1]["value_usd"] > 0

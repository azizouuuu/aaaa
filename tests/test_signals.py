from app.models import TradeRecord
from app.signals.corridors import hub_share
from app.signals.engine import disaggregate_flow
from app.signals.mirror import consistency_score
from app.signals.origination import corridor_flags, country_flags
from app.signals.unit_value import band_membership


def test_band_membership_inside_is_one():
    assert band_membership(600, 450, 750) == 1.0


def test_band_membership_falls_off_outside():
    assert 0 < band_membership(800, 450, 750) < 1.0
    assert band_membership(2000, 450, 750) == 0.0


def test_band_membership_zero_or_negative_is_zero():
    assert band_membership(0, 450, 750) == 0.0
    assert band_membership(-5, 450, 750) == 0.0


def _rec(reporter, partner, value, wgt, code="1522", flow="X", year=2024):
    return TradeRecord(
        source="test", reporter=reporter, partner=partner, flow=flow,
        code=code, code_system="HS6", year=year, value_usd=value, net_wgt_kg=wgt,
    )


def test_disaggregate_flow_favors_pome_for_indonesia_to_hub():
    # $650/t Indonesia -> Netherlands: squarely in the POME band, hub destination.
    rows = [_rec("IDN", "NLD", 650_000, 1_000_000)]
    result = disaggregate_flow("pome", "IDN", "NLD", 2024, "X", rows)
    assert result.candidates[0][0] == "pome"
    assert result.candidates[0][1] > 0.6
    assert result.confidence in ("medium", "high")
    assert any("Unit value" in e for e in result.explanations)


def test_disaggregate_flow_favors_soapstock_for_low_value_non_palm_origin():
    # $300/t Spain -> Germany: below the POME band, non-palm origin, non-hub.
    rows = [_rec("ESP", "DEU", 300_000, 1_000_000)]
    result = disaggregate_flow("pome", "ESP", "DEU", 2024, "X", rows)
    assert result.candidates[0][0] == "soapstock_degras"


def test_disaggregate_flow_handles_missing_weight():
    rows = [_rec("IDN", "NLD", 650_000, None)]
    result = disaggregate_flow("pome", "IDN", "NLD", 2024, "X", rows)
    assert result.unit_value is None
    assert result.candidates  # still produces a ranking from origin/destination alone


def test_disaggregate_flow_probabilities_sum_to_one():
    rows = [_rec("IDN", "NLD", 650_000, 1_000_000)]
    result = disaggregate_flow("pome", "IDN", "NLD", 2024, "X", rows)
    assert abs(sum(p for _, p in result.candidates) - 1.0) < 1e-6


def test_disaggregate_flow_no_candidates_for_unshared_commodity():
    rows = [_rec("BRA", "NLD", 1_000_000, 1_000_000, code="1507")]
    result = disaggregate_flow("soy", "BRA", "NLD", 2024, "X", rows)
    assert result.candidates == []
    assert result.confidence == "high"


def test_hub_share_computes_weighted_share():
    rows = [_rec("IDN", "NLD", 100, 1), _rec("IDN", "THA", 100, 1)]
    result = hub_share(rows)
    assert result["share"] == 0.5  # NLD is a hub, THA is not


def test_hub_share_empty_input():
    assert hub_share([])["share"] is None


def test_consistency_score_within_normal_band():
    assert consistency_score({"available": True, "ratio": 1.1}) == 1.0


def test_consistency_score_outside_band_penalized():
    score = consistency_score({"available": True, "ratio": 3.0})
    assert 0.0 <= score < 1.0


def test_consistency_score_unavailable_is_none():
    assert consistency_score({"available": False}) is None


def test_country_flags_detects_new_exporter():
    flags = country_flags({2023: {}, 2024: {"IDN": 50_000_000}}, 2024)
    assert flags[0]["type"] == "new_exporter"


def test_country_flags_detects_surge_and_collapse():
    values = {2023: {"A": 100_000_000, "B": 100_000_000}, 2024: {"A": 160_000_000, "B": 50_000_000}}
    flags = country_flags(values, 2024)
    types = {f["iso3"]: f["type"] for f in flags}
    assert types["A"] == "surge"
    assert types["B"] == "collapse"


def test_country_flags_ignores_noise_below_threshold():
    flags = country_flags({2023: {"X": 1_000_000}, 2024: {"X": 2_000_000}}, 2024)
    assert flags == []  # below MIN_FLAG_VALUE


def test_corridor_flags_new_corridor():
    flags = corridor_flags({"NLD": 20_000_000}, {"NLD": 0})
    assert flags[0]["type"] == "new_corridor"

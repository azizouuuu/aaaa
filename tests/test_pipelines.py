from app.models import FlowQuery
from app.pipelines.comtrade import N_ALL_PARTNERS, N_ALL_REPORTERS, RECORD_BUDGET, build_requests


def _expected(reporters, partners, codes, years):
    n_rep = len(reporters) if reporters is not None else N_ALL_REPORTERS
    n_par = len(partners) if partners is not None else N_ALL_PARTNERS
    return n_rep * n_par * len(codes) * len(years)


def test_all_requests_stay_under_budget_world_trend():
    # the shape that would 10x-blow the cap if not split: all reporters x
    # world x 1 code x 7 years
    q = FlowQuery(("1518",), "X", tuple(range(2018, 2025)), None, ("WLD",))
    reqs = build_requests(q)
    assert len(reqs) == 7  # one call per year
    for r in reqs:
        years = r["period"].split(",")
        codes = r["cmdCode"].split(",")
        assert N_ALL_REPORTERS * 1 * len(codes) * len(years) <= RECORD_BUDGET


def test_all_requests_stay_under_budget_rankings():
    q = FlowQuery(("1518",), "X", (2024,), None, ("WLD",))
    reqs = build_requests(q)
    assert len(reqs) == 1  # already under budget, no split needed


def test_all_requests_stay_under_budget_watchlist_multi_code_multi_country():
    q = FlowQuery(("1518", "1502", "1522"), "X", (2024,), ("IDN", "MYS", "CHN"), ("WLD",))
    reqs = build_requests(q)
    for r in reqs:
        years = r["period"].split(",")
        codes = r["cmdCode"].split(",")
        assert 3 * 1 * len(codes) * len(years) <= RECORD_BUDGET


def test_all_requests_stay_under_budget_partner_trend_multi_year():
    # one reporter x all partners x 1 code x 7 years — would be 230*7=1610 unsplit
    q = FlowQuery(("1522",), "X", tuple(range(2018, 2025)), ("IDN",), None)
    reqs = build_requests(q)
    for r in reqs:
        years = r["period"].split(",")
        codes = r["cmdCode"].split(",")
        assert 1 * N_ALL_PARTNERS * len(codes) * len(years) <= RECORD_BUDGET
    assert len(reqs) == 7


def test_build_requests_preserves_flow_and_reporter_param():
    q = FlowQuery(("1518",), "M", (2024,), ("USA",), ("WLD",))
    reqs = build_requests(q)
    assert all(r["flowCode"] == "M" for r in reqs)
    assert all("reporterCode" in r for r in reqs)

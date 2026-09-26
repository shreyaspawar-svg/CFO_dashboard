"""Unit tests for app.metrics.ratios -- hand-computed fixtures, with
explicit coverage of zero denominators and negative equity, per the Phase 2
acceptance criteria in PLAN.md."""

from __future__ import annotations

import math

import pytest

from app.metrics import ratios as r


# --------------------------------------------------------------------------
# Growth
# --------------------------------------------------------------------------


def test_yoy_growth_basic():
    assert r.yoy_growth(110, 100) == pytest.approx(10.0)


def test_yoy_growth_zero_previous_is_none():
    assert r.yoy_growth(100, 0) is None


def test_yoy_growth_negative_previous_is_none_not_meaningful():
    # PLAN.md "Phase 4.2 review": a non-positive base makes the percentage
    # not meaningful, even for a same-sign "loss shrinking" case -- this
    # superseded an earlier version of the function that let this through.
    assert r.yoy_growth(-50, -100) is None
    assert r.growth_reason(-50, -100) == "not_meaningful"


def test_yoy_growth_sign_crossing_negative_to_positive_is_none_not_meaningful():
    # INDIGO's real PAT: FY23 -Rs305.79 Cr -> FY24 +Rs8,172.50 Cr. The raw
    # formula would give a nonsensical "+2,673%"; this must be None instead.
    assert r.yoy_growth(8172.50, -305.79) is None
    assert r.growth_reason(8172.50, -305.79) == "not_meaningful"


def test_yoy_growth_none_inputs():
    assert r.yoy_growth(None, 100) is None
    assert r.yoy_growth(100, None) is None


def test_growth_reason_missing_vs_not_meaningful():
    assert r.growth_reason(None, 100) == "missing"
    assert r.growth_reason(100, None) == "missing"
    assert r.growth_reason(100, 0) == "not_meaningful"  # non-positive, not "missing"
    assert r.growth_reason(110, 100) is None  # a real value, no reason needed


def test_cagr_basic():
    # 100 -> 133.1 over 3 years = 10% CAGR
    assert r.cagr(100, 133.1, 3) == pytest.approx(10.0, abs=0.05)


def test_cagr_negative_begin_or_end_is_none():
    assert r.cagr(-100, 200, 3) is None
    assert r.cagr(100, -200, 3) is None
    assert r.cagr(0, 200, 3) is None


def test_cagr_nonpositive_years_is_none():
    assert r.cagr(100, 200, 0) is None
    assert r.cagr(100, 200, -1) is None


def test_cagr_reason_missing_vs_not_meaningful():
    assert r.cagr_reason(None, 200, 3) == "missing"
    assert r.cagr_reason(100, 200, None) == "missing"
    assert r.cagr_reason(100, 200, 0) == "missing"  # no valid span
    assert r.cagr_reason(-100, 200, 3) == "not_meaningful"
    assert r.cagr_reason(100, -200, 3) == "not_meaningful"
    assert r.cagr_reason(100, 200, 3) is None  # a real value, no reason needed


# --------------------------------------------------------------------------
# Margins
# --------------------------------------------------------------------------


def test_margin_basic():
    assert r.margin(25, 100) == pytest.approx(25.0)


def test_margin_zero_revenue_is_none():
    assert r.margin(25, 0) is None


# --------------------------------------------------------------------------
# Returns
# --------------------------------------------------------------------------


def test_return_on_equity_basic():
    assert r.return_on_equity(20, 100) == pytest.approx(20.0)


def test_return_on_equity_negative_equity_computes_real_value():
    """Negative book equity is a real (if alarming) state -- ROE should
    still be computed, not hidden as None, so the caller/UI can flag it."""
    result = r.return_on_equity(10, -50)
    assert result == pytest.approx(-20.0)


def test_return_on_equity_zero_equity_is_none():
    assert r.return_on_equity(10, 0) is None


def test_return_on_assets_basic():
    assert r.return_on_assets(10, 200) == pytest.approx(5.0)


def test_capital_employed():
    assert r.capital_employed(1000, 300) == 700


def test_return_on_capital_employed():
    assert r.return_on_capital_employed(70, 700) == pytest.approx(10.0)


def test_invested_capital_defaults_cash_to_zero():
    assert r.invested_capital(500, 300, None) == 800
    assert r.invested_capital(500, 300, 100) == 700


def test_effective_tax_rate_basic():
    assert r.effective_tax_rate(25, 100) == pytest.approx(0.25)


def test_effective_tax_rate_zero_pretax_is_none():
    assert r.effective_tax_rate(25, 0) is None


def test_effective_tax_rate_extreme_rate_rejected():
    # A barely-profitable year with disproportionate tax can produce a
    # nonsensical "rate" (e.g. 300%) -- reject rather than propagate noise.
    assert r.effective_tax_rate(30, 10) is None
    assert r.effective_tax_rate(-30, 10) is None


def test_nopat_and_roic():
    nopat = r.nopat(100, 0.25)
    assert nopat == pytest.approx(75.0)
    roic = r.return_on_invested_capital(100, 0.25, 500)
    assert roic == pytest.approx(15.0)


def test_dupont_decomposition_product_matches_direct_roe():
    components = r.dupont_decomposition(
        net_income=50, revenue=1000, avg_total_assets=800, avg_equity=400
    )
    direct_roe = r.return_on_equity(50, 400)
    assert components["roe_check_pct"] == pytest.approx(direct_roe)
    assert components["net_margin_pct"] == pytest.approx(5.0)
    assert components["asset_turnover"] == pytest.approx(1.25)
    assert components["equity_multiplier"] == pytest.approx(2.0)


def test_dupont_decomposition_missing_input_leaves_roe_check_none():
    components = r.dupont_decomposition(50, 1000, None, 400)
    assert components["asset_turnover"] is None
    assert components["roe_check_pct"] is None
    assert components["net_margin_pct"] == pytest.approx(5.0)


def test_dupont_bank_product_matches_direct_roe():
    # PLAN.md §4.3: bank/NBFC 2-step (ROA x Leverage) is an exact algebraic
    # identity, not an approximation -- ROA x (Assets/Equity) = NI/Equity.
    components = r.dupont_bank(net_income=50, avg_total_assets=800, avg_equity=400)
    direct_roe = r.return_on_equity(50, 400)
    assert components["roe_check_pct"] == pytest.approx(direct_roe)
    assert components["roa_pct"] == pytest.approx(6.25)
    assert components["leverage"] == pytest.approx(2.0)


def test_dupont_bank_missing_input_leaves_roe_check_none():
    components = r.dupont_bank(50, None, 400)
    assert components["leverage"] is None
    assert components["roe_check_pct"] is None
    assert components["roa_pct"] is None


# --------------------------------------------------------------------------
# Leverage
# --------------------------------------------------------------------------


def test_debt_to_equity_basic():
    assert r.debt_to_equity(200, 100) == pytest.approx(2.0)


def test_debt_to_equity_negative_equity_is_real_negative_value():
    assert r.debt_to_equity(200, -100) == pytest.approx(-2.0)


def test_debt_to_equity_zero_equity_is_none():
    assert r.debt_to_equity(200, 0) is None


def test_net_debt_to_ebitda():
    assert r.net_debt_to_ebitda(500, 100, 200) == pytest.approx(2.0)
    assert r.net_debt_to_ebitda(500, None, 200) == pytest.approx(2.5)


def test_interest_coverage_zero_interest_is_none():
    assert r.interest_coverage(100, 0) is None


def test_interest_coverage_basic():
    assert r.interest_coverage(100, 25) == pytest.approx(4.0)


def test_debt_to_assets_basic():
    assert r.debt_to_assets(300, 1000) == pytest.approx(0.3)


# --------------------------------------------------------------------------
# Liquidity
# --------------------------------------------------------------------------


def test_current_ratio_zero_liabilities_is_none():
    assert r.current_ratio(500, 0) is None


def test_quick_ratio_treats_missing_inventory_as_zero():
    assert r.quick_ratio(500, None, 250) == pytest.approx(2.0)
    assert r.quick_ratio(500, 100, 250) == pytest.approx(1.6)


def test_cash_ratio_basic():
    assert r.cash_ratio(150, 300) == pytest.approx(0.5)


# --------------------------------------------------------------------------
# Efficiency
# --------------------------------------------------------------------------


def test_debtor_days_basic():
    assert r.debtor_days(receivables=100, revenue=1000) == pytest.approx(36.5, abs=0.01)


def test_inventory_and_payable_days_and_ccc():
    dd = r.debtor_days(100, 1000)
    idays = r.inventory_days(50, 800)
    pdays = r.payable_days(80, 800)
    ccc = r.cash_conversion_cycle(dd, idays, pdays)
    assert ccc == pytest.approx(dd + idays - pdays)


def test_cash_conversion_cycle_none_if_any_missing():
    assert r.cash_conversion_cycle(10, None, 5) is None


# --------------------------------------------------------------------------
# Cash flow
# --------------------------------------------------------------------------


def test_free_cash_flow_prefers_reported_value():
    assert r.free_cash_flow(cfo=100, capex=-20, reported_fcf=999) == 999


def test_free_cash_flow_falls_back_to_cfo_plus_capex():
    assert r.free_cash_flow(cfo=100, capex=-20) == 80


def test_free_cash_flow_none_cfo_is_none():
    assert r.free_cash_flow(cfo=None, capex=-20) is None


def test_cfo_to_pat_negative_net_income_flips_sign():
    assert r.cfo_to_pat(50, -25) == pytest.approx(-2.0)


def test_capex_intensity_uses_absolute_value():
    assert r.capex_intensity(-50, 500) == pytest.approx(10.0)


# --------------------------------------------------------------------------
# Valuation
# --------------------------------------------------------------------------


def test_enterprise_value_defaults():
    assert r.enterprise_value(1000, 200, 50) == 1150
    assert r.enterprise_value(1000, None, None) == 1000


def test_enterprise_value_adds_minority_interest():
    # PLAN.md "Phase 2 review" item 1: EV reflects the whole consolidated
    # enterprise, so minority interest is added, not netted into equity.
    assert r.enterprise_value(1000, 200, 50, minority_interest=300) == 1450
    assert r.enterprise_value(1000, 200, 50, minority_interest=None) == 1150


def test_book_value_per_share_and_relative_divergence():
    assert r.book_value_per_share(1000, 100) == pytest.approx(10.0)
    assert r.book_value_per_share(1000, 0) is None
    assert r.relative_divergence(530, 390) == pytest.approx(35.897, abs=0.01)
    assert r.relative_divergence(None, 390) is None
    assert r.relative_divergence(530, 0) is None


def test_price_to_per_share_value_matches_price_to_earnings():
    assert r.price_to_per_share_value(2082, 136.01) == r.price_to_earnings(2082, 136.01)
    assert r.price_to_per_share_value(100, 0) is None


def test_price_to_earnings_negative_eps_is_real_negative_pe():
    assert r.price_to_earnings(100, -5) == pytest.approx(-20.0)


def test_price_to_earnings_zero_eps_is_none():
    assert r.price_to_earnings(100, 0) is None


def test_price_to_book_basic():
    assert r.price_to_book(2000, 1000) == pytest.approx(2.0)


def test_ev_to_ebitda_and_sales():
    assert r.ev_to_ebitda(1150, 230) == pytest.approx(5.0)
    assert r.ev_to_sales(1150, 500) == pytest.approx(2.3)


def test_peg_ratio_rejects_negative_pe_or_growth():
    assert r.peg_ratio(-10, 15) is None
    assert r.peg_ratio(20, -5) is None
    assert r.peg_ratio(20, 0) is None
    assert r.peg_ratio(20, 10) == pytest.approx(2.0)


def test_dividend_and_earnings_yield():
    assert r.dividend_yield(10, 200) == pytest.approx(5.0)
    assert r.earnings_yield(20, 200) == pytest.approx(10.0)


def test_payout_ratio_rejects_negative_or_zero_eps():
    assert r.payout_ratio(5, -2) is None
    assert r.payout_ratio(5, 0) is None
    assert r.payout_ratio(5, 20) == pytest.approx(25.0)


# --------------------------------------------------------------------------
# Bank / NBFC derived
# --------------------------------------------------------------------------


def test_net_interest_margin_proxy():
    assert r.net_interest_margin(50, 1000) == pytest.approx(5.0)


def test_cost_to_income_basic():
    assert r.cost_to_income(non_interest_expense=60, net_interest_income=80, non_interest_income=20) == pytest.approx(60.0)


def test_cost_to_income_none_when_both_income_components_missing():
    assert r.cost_to_income(60, None, None) is None


# --------------------------------------------------------------------------
# Quality flags
# --------------------------------------------------------------------------


def test_altman_z_score_hand_computed():
    # A=0.2, B=0.3, C=0.15, D=1.5, E=0.8 (arbitrary but clean fixture)
    z = r.altman_z_score(
        working_capital=200,
        retained_earnings=300,
        ebit=150,
        market_cap=1500,
        total_liabilities=1000,
        revenue=800,
        total_assets=1000,
    )
    expected = 1.2 * 0.2 + 1.4 * 0.3 + 3.3 * 0.15 + 0.6 * 1.5 + 1.0 * 0.8
    assert z == pytest.approx(expected)


def test_altman_z_score_none_if_any_component_missing():
    assert (
        r.altman_z_score(
            working_capital=200,
            retained_earnings=None,
            ebit=150,
            market_cap=1500,
            total_liabilities=1000,
            revenue=800,
            total_assets=1000,
        )
        is None
    )


def test_altman_z_score_zero_total_assets_is_none():
    assert (
        r.altman_z_score(
            working_capital=200,
            retained_earnings=300,
            ebit=150,
            market_cap=1500,
            total_liabilities=1000,
            revenue=800,
            total_assets=0,
        )
        is None
    )


def test_piotroski_f_score_all_criteria_pass():
    current = {
        "net_income": 100,
        "total_assets": 1000,
        "cfo": 150,
        "total_debt": 200,
        "current_assets": 500,
        "current_liabilities": 250,
        "shares_outstanding": 100,
        "gross_profit": 400,
        # Revenue > prior's 900/900=1.0x turnover, so asset turnover strictly
        # improves too (all 9 criteria must be a strict improvement).
        "revenue": 1050,
    }
    prior = {
        "net_income": 50,
        "total_assets": 900,
        "cfo": 40,
        "total_debt": 300,
        "current_assets": 400,
        "current_liabilities": 300,
        "shares_outstanding": 100,
        "gross_profit": 300,
        "revenue": 900,
    }
    earned, possible = r.piotroski_f_score(current, prior)
    assert possible == 9
    assert earned == 9


def test_piotroski_f_score_partial_data_scores_out_of_fewer_points():
    # A bank-shaped dataset: no current_assets/current_liabilities or
    # gross_profit -- those 2 criteria should be excluded, not scored as 0.
    current = {"net_income": 100, "total_assets": 1000, "cfo": 150, "total_debt": 200, "shares_outstanding": 100, "revenue": 1050}
    prior = {"net_income": 50, "total_assets": 900, "cfo": 40, "total_debt": 300, "shares_outstanding": 100, "revenue": 900}
    earned, possible = r.piotroski_f_score(current, prior)
    assert possible == 7  # current_ratio and gross_margin criteria excluded
    assert earned == 7


def test_piotroski_f_score_all_missing_scores_zero_of_zero():
    earned, possible = r.piotroski_f_score({}, {})
    assert (earned, possible) == (0, 0)


def test_altman_z_score_detailed_matches_aggregate_and_labels_5_components():
    detail = r.altman_z_score_detailed(
        working_capital=200,
        retained_earnings=300,
        ebit=150,
        market_cap=1500,
        total_liabilities=1000,
        revenue=800,
        total_assets=1000,
    )
    aggregate = r.altman_z_score(200, 300, 150, 1500, 1000, 800, 1000)
    assert detail["score"] == pytest.approx(aggregate)
    assert len(detail["components"]) == 5
    assert detail["components"][0]["value"] == pytest.approx(0.2)


def test_altman_z_score_detailed_zone_boundaries():
    # score >= 2.99 -> safe; the hand-computed fixture above scores ~2.55
    safe = r.altman_z_score_detailed(1000, 1000, 1000, 5000, 500, 1000, 500)
    assert safe["zone"] == "safe"
    distress = r.altman_z_score_detailed(-500, -500, -200, 100, 2000, 500, 1000)
    assert distress["zone"] == "distress"


def test_altman_z_score_detailed_missing_component_has_no_score_or_zone():
    detail = r.altman_z_score_detailed(200, None, 150, 1500, 1000, 800, 1000)
    assert detail["score"] is None
    assert detail["zone"] is None
    assert len(detail["components"]) == 5  # still reports what it could


def test_piotroski_f_score_detailed_matches_aggregate_and_labels_9_tests():
    current = {
        "net_income": 100,
        "total_assets": 1000,
        "cfo": 150,
        "total_debt": 200,
        "current_assets": 500,
        "current_liabilities": 250,
        "shares_outstanding": 100,
        "gross_profit": 400,
        "revenue": 1050,
    }
    prior = {
        "net_income": 50,
        "total_assets": 900,
        "cfo": 40,
        "total_debt": 300,
        "current_assets": 400,
        "current_liabilities": 300,
        "shares_outstanding": 100,
        "gross_profit": 300,
        "revenue": 900,
    }
    detail = r.piotroski_f_score_detailed(current, prior)
    earned, possible = r.piotroski_f_score(current, prior)
    assert (detail["earned"], detail["possible"]) == (earned, possible)
    assert len(detail["tests"]) == 9
    assert all(t["passed"] is True for t in detail["tests"])


def test_piotroski_f_score_detailed_excludes_missing_tests_not_fails_them():
    current = {"net_income": 100, "total_assets": 1000, "cfo": 150, "total_debt": 200, "shares_outstanding": 100, "revenue": 1050}
    prior = {"net_income": 50, "total_assets": 900, "cfo": 40, "total_debt": 300, "shares_outstanding": 100, "revenue": 900}
    detail = r.piotroski_f_score_detailed(current, prior)
    assert len(detail["tests"]) == 9  # every test is still listed
    none_tests = [t for t in detail["tests"] if t["passed"] is None]
    assert len(none_tests) == 2  # current ratio + gross margin, data missing
    assert detail["possible"] == 7

"""compute_symbol_metrics against saved fixtures -- exercises the full
router-to-ratios wiring (not just the pure functions in isolation), using
one company per template. Network is blocked by conftest.py's autouse
fixture, same as the API endpoint tests.
"""

from __future__ import annotations

import asyncio

import pytest

from app.metrics.templates import headline_kpis
from app.services.datasource import YahooDataSource, set_data_source
from app.services.metrics_engine import compute_symbol_metrics


def _run(symbol: str) -> dict:
    return asyncio.run(compute_symbol_metrics(symbol))


def test_tcs_general_template_has_core_metrics():
    result = _run("TCS")
    metrics = result["metrics"]
    assert result["company"].template == "general"
    assert metrics["ebitda_margin"] is not None
    assert 15 < metrics["ebitda_margin"] < 40  # sanity band, not a hardcoded value
    assert metrics["roe"] is not None
    assert metrics["pe"] is not None
    assert metrics["revenue_cagr_3y"] is not None
    # A general company's headline KPI set shouldn't surface bank-only
    # cards -- even if the raw engine happens to compute a NIM proxy from
    # a large IT company's treasury interest income (real data, just not a
    # meaningful headline metric for this template).
    general_kpi_keys = {kpi["key"] for kpi in headline_kpis("general")}
    assert "nim" not in general_kpi_keys
    assert "cost_to_income" not in general_kpi_keys


def test_hdfcbank_template_has_bank_metrics_not_general_ones():
    result = _run("HDFCBANK")
    metrics = result["metrics"]
    assert result["company"].template == "bank"
    assert metrics["nim"] is not None
    assert metrics["cost_to_income"] is not None
    assert metrics["roe"] is not None
    assert metrics["debt_to_equity"] is not None
    # A bank has no EBITDA/gross-profit concept -- must stay None, not 0.
    assert metrics["ebitda_margin"] is None
    assert metrics["current_ratio"] is None
    # Altman Z / Piotroski are non-financial-only per PLAN.md §2.
    assert "altman_z_score" not in metrics


def test_bajfinance_nbfc_template():
    result = _run("BAJFINANCE")
    metrics = result["metrics"]
    assert result["company"].template == "nbfc"
    assert metrics["nim"] is not None
    assert metrics["roe"] is not None


def test_hdfclife_insurance_template_has_premium_growth():
    result = _run("HDFCLIFE")
    metrics = result["metrics"]
    assert result["company"].template == "insurance"
    assert metrics["roe"] is not None


def test_bse_exchange_template_has_general_style_metrics():
    result = _run("BSE")
    metrics = result["metrics"]
    assert result["company"].template == "exchange"
    assert metrics["ebitda_margin"] is not None
    assert metrics["pe"] is not None


def test_tcs_altman_z_and_piotroski_present_for_general_template():
    result = _run("TCS")
    metrics = result["metrics"]
    assert metrics["altman_z_score"] is not None
    assert metrics["piotroski_f_score"] is not None
    assert 0 <= metrics["piotroski_f_score"] <= metrics["piotroski_f_score_possible"] <= 9


def test_unknown_symbol_returns_empty_metrics_with_warning():
    result = _run("NOTREAL")
    assert result["metrics"] == {}
    assert any("Unknown symbol" in w for w in result["warnings"])


# --------------------------------------------------------------------------
# Phase 2.1 regression: HDFCBANK's book value diverged 36% from Screener.in
# (Rs530/share vs Rs390) because Yahoo's StockholdersEquity, though already
# minority-interest-excluded per its own schema, still overstated true
# parent book value for this post-merger, partly-divested-subsidiary bank.
# The fix is Yahoo's own crumb-gated key-statistics cross-check
# (financialData.returnOnEquity, defaultKeyStatistics.bookValue/
# trailingEps), preferred over our fundamentals-timeseries-derived figures
# when available. These tests inject a fake key-statistics response (the
# fixture-mocked network always reports the crumb as unavailable, so the
# real override path is otherwise never exercised in the test suite) to
# regression-guard the override wiring itself.
# --------------------------------------------------------------------------


class _FakeKeyStatsDataSource:
    """Delegates everything to the real YahooDataSource (still routed
    through the fixture-mocked network) except get_key_statistics, which
    returns a fixed, synthetic response."""

    def __init__(self, key_stats: dict):
        self._key_stats = key_stats
        self._real = YahooDataSource()

    async def get_key_statistics(self, yf_ticker):
        return self._key_stats

    def __getattr__(self, name):
        return getattr(self._real, name)


def _run_with_fake_key_stats(symbol: str, key_stats: dict) -> dict:
    set_data_source(_FakeKeyStatsDataSource(key_stats))
    try:
        return asyncio.run(compute_symbol_metrics(symbol))
    finally:
        set_data_source(None)


def test_hdfcbank_roe_prefers_yahoo_key_stats_over_own_calculation():
    # Real values pulled live during the Phase 2 review's investigation.
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": 13.84, "roa_pct": 1.75, "book_value_per_share": 393.81, "trailing_eps": 45.75},
    )
    assert result["metrics"]["roe"] == pytest.approx(13.84)
    assert result["metrics"]["roa"] == pytest.approx(1.75)


def test_hdfcbank_pb_and_pe_use_yahoo_book_value_and_eps():
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": None, "roa_pct": None, "book_value_per_share": 393.81, "trailing_eps": 45.75},
    )
    price = result["quote"].last_price
    assert result["metrics"]["pb"] == pytest.approx(price / 393.81, rel=1e-6)
    assert result["metrics"]["pe"] == pytest.approx(price / 45.75, rel=1e-6)


def test_hdfcbank_book_value_divergence_flagged():
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": None, "roa_pct": None, "book_value_per_share": 393.81, "trailing_eps": None},
    )
    divergences = {d["metric"]: d for d in result["cross_check_divergences"]}
    assert "book_value_per_share" in divergences
    assert divergences["book_value_per_share"]["divergence_pct"] > 10


def test_hdfcbank_no_yahoo_cross_check_falls_back_to_own_calculation():
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": None, "roa_pct": None, "book_value_per_share": None, "trailing_eps": None},
    )
    # Falls back to our own fundamentals-derived figures -- still a real
    # number, not None, and no divergence is flagged with nothing to
    # compare against.
    assert result["metrics"]["roe"] is not None
    assert result["cross_check_divergences"] == []


def test_own_book_value_per_share_is_unit_correct_not_crore_vs_raw_mismatch():
    """Regression: total_equity is stored in Rs crore, shares_outstanding
    is a raw count. Dividing them directly (forgetting to re-expand equity
    to raw rupees first) silently produced a book value ~1e7x too small --
    every single symbol showed a spurious "100% divergence" against
    Yahoo's key statistics the first time this shipped. Sanity-band check
    (not an exact value, which would break on live data drift): a real
    Indian large-cap's book value per share is never under Rs1."""
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": None, "roa_pct": None, "book_value_per_share": None, "trailing_eps": None},
    )
    assert result["cross_check_divergences"] == []
    # pb = price / book_value_per_share; back it out and check it's sane.
    price = result["quote"].last_price
    pb = result["metrics"]["pb"]
    implied_book_value_per_share = price / pb
    assert implied_book_value_per_share > 1


def test_hdfcbank_balance_sheet_carries_minority_interest():
    """The fixture confirms MinorityInterest is a real, populated field for
    a partly-divested-subsidiary bank like HDFCBANK -- enterprise_value
    (app.metrics.ratios) adds it back per PLAN.md "Phase 2 review" item 1;
    see test_ratios.py for that function's own unit tests."""
    result = _run("HDFCBANK")
    assert result["latest_balance"].get("minority_interest") is not None
    assert result["latest_balance"]["minority_interest"] > 0

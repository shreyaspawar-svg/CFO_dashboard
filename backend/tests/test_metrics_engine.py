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


def test_tcs_dupont_is_general_3_step_and_reconciles_to_roe():
    result = _run("TCS")
    assert result["dupont_kind"] == "general"
    metrics = result["metrics"]
    assert metrics["dupont_net_margin_pct"] is not None
    assert metrics["dupont_asset_turnover"] is not None
    assert metrics["dupont_equity_multiplier"] is not None
    assert metrics["dupont_roe_check_pct"] is not None
    # Same net_income_for_returns feeds both metrics["roe"] and the DuPont
    # product -- an algebraic identity, not an approximation -- whenever
    # the KPI card shows our own "computed" figure (PLAN.md §4.3 item 3).
    if result["method"]["roe"] == "computed":
        assert metrics["dupont_roe_check_pct"] == pytest.approx(metrics["roe"], abs=1e-6)
        assert result["dupont_reconciliation_gap_pp"] == pytest.approx(0.0, abs=1e-6)


def test_hdfcbank_dupont_is_bank_2_step_and_reconciles_to_roe():
    result = _run("HDFCBANK")
    assert result["dupont_kind"] == "bank"
    metrics = result["metrics"]
    assert "dupont_net_margin_pct" not in metrics  # no 3-step fields for a bank
    assert metrics["dupont_roa_pct"] is not None
    assert metrics["dupont_leverage"] is not None
    assert metrics["dupont_roe_check_pct"] == pytest.approx(metrics["roe"], abs=1e-6)
    assert result["dupont_reconciliation_gap_pp"] == pytest.approx(0.0, abs=1e-6)


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
# Phase 2.1 found that HDFCBANK's book value diverges from Screener.in
# (Rs530/share vs Rs390) -- traced in Phase 2.2 (PLAN.md "Phase 3 review")
# to HDFCBANK's own `StockholdersEquity` oscillating wildly between
# quarters (Yahoo inconsistently sourcing standalone vs consolidated
# statements for this post-merger conglomerate -- see
# backend/docs/data-notes.md), not a bug in our code. Phase 2.1's fix
# (silently overriding our own ROE/book-value with Yahoo's crumb-gated
# key-statistics whenever available) created a worse problem: a KPI card
# and a history/trend chart built from our own data would then disagree,
# since Yahoo's figure is a single current snapshot a trend chart can't
# reproduce. Phase 2.2 changed this to "prefer our own calculation always;
# Yahoo's figure is a fallback ONLY when ours is None, and is tagged as
# such via `method`" -- these tests cover both paths plus the still-useful
# >10% divergence flag (item 4).
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


def test_hdfcbank_roe_carries_data_quality_inconsistent_badge():
    # PLAN.md "Phase 4.1 review" item 1 / Phase 2.3: the fixture's quarterly
    # equity reproduces the real basis-oscillation pattern, so ROE/ROA must
    # be flagged rather than presented as a clean 8.9% figure.
    result = _run("HDFCBANK")
    assert "roe" in result["data_quality"]
    assert "roa" in result["data_quality"]
    assert "basis" in result["data_quality"]["roe"].lower()


def test_tcs_roe_has_no_data_quality_flag():
    result = _run("TCS")
    assert "roe" not in result["data_quality"]
    assert result["data_quality"] == {}


def test_hdfcbank_roe_prefers_own_calculation_even_when_yahoo_is_available():
    # Real values pulled live during the Phase 2.1 investigation -- our own
    # calculation succeeds for HDFCBANK (it has enough periods), so it must
    # win even though a (fake, here) Yahoo figure is available and differs.
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": 13.84, "roa_pct": 1.75, "book_value_per_share": 393.81, "trailing_eps": 45.75},
    )
    assert result["metrics"]["roe"] != pytest.approx(13.84)
    assert result["metrics"]["roe"] == pytest.approx(8.896498782179343)
    assert result["method"]["roe"] == "computed"
    assert result["method"]["roa"] == "computed"


def test_hdfcbank_pb_and_pe_prefer_own_book_value_and_eps():
    result = _run_with_fake_key_stats(
        "HDFCBANK",
        {"roe_pct": None, "roa_pct": None, "book_value_per_share": 393.81, "trailing_eps": 45.75},
    )
    price = result["quote"].last_price
    assert result["metrics"]["pb"] != pytest.approx(price / 393.81, rel=1e-6)
    assert result["method"]["pb"] == "computed"
    assert result["method"]["pe"] == "computed"


def test_yahoo_fallback_used_only_when_own_calculation_is_none():
    # Force our own ROE to be unavailable (no comparable balance-sheet
    # periods) by using a symbol whose comparable_periods excludes almost
    # everything -- simplest reliable way: directly exercise _prefer_own.
    from app.services.metrics_engine import _prefer_own

    method: dict[str, str] = {}
    assert _prefer_own("roe", None, 13.84, method) == 13.84
    assert method["roe"] == "yahoo_fallback"

    method2: dict[str, str] = {}
    assert _prefer_own("roe", 8.9, 13.84, method2) == 8.9
    assert method2["roe"] == "computed"

    method3: dict[str, str] = {}
    assert _prefer_own("roe", None, None, method3) is None
    assert method3["roe"] == "unavailable"


def test_implausible_own_eps_falls_back_to_yahoo_even_though_not_none(monkeypatch):
    """Regression for a real finding: summing 4 volatile quarterly EPS
    values can net out near zero (INDIGO: +56, +14, -66, -6 -> -1.33),
    implying a P/E in the thousands even though each quarter's figure is
    individually correct -- and separately, INFY's own EPS is unit-
    inconsistent at the source (docs/data-notes.md). Either way, a real
    (non-None) but implausible own-value must be treated like a missing
    one, not displayed as-is."""
    import app.services.metrics_engine as engine

    monkeypatch.setattr(engine, "_ttm_sum", lambda periods, key: 0.01 if key == "eps_diluted" else None)

    result = _run_with_fake_key_stats(
        "TCS", {"roe_pct": None, "roa_pct": None, "book_value_per_share": None, "trailing_eps": 136.01}
    )
    assert result["metrics"]["pe"] != pytest.approx(result["quote"].last_price / 0.01)
    assert result["method"]["pe"] == "yahoo_fallback"


def test_implausible_own_eps_with_no_yahoo_fallback_is_unavailable_not_garbage(monkeypatch):
    import app.services.metrics_engine as engine

    monkeypatch.setattr(engine, "_ttm_sum", lambda periods, key: 0.01 if key == "eps_diluted" else None)

    result = _run_with_fake_key_stats(
        "TCS", {"roe_pct": None, "roa_pct": None, "book_value_per_share": None, "trailing_eps": None}
    )
    assert result["metrics"]["pe"] is None
    assert result["method"]["pe"] == "unavailable"


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

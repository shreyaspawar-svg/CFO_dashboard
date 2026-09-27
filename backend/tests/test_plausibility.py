from app.metrics.plausibility import (
    book_value_per_share_is_plausible,
    eps_price_ratio_is_plausible,
    market_cap_matches_price_times_shares,
    multiple_is_plausible,
    pe_is_plausible,
)


def test_book_value_per_share_plausible_real_value():
    assert book_value_per_share_is_plausible(393.81) is True


def test_book_value_per_share_catches_the_1e7x_regression():
    # The Phase 2.1 bug produced ~5.3e-5 instead of ~530.
    assert book_value_per_share_is_plausible(2.963996848237655e-05) is False


def test_book_value_per_share_catches_absurdly_large_value():
    assert book_value_per_share_is_plausible(50_000_000) is False


def test_book_value_per_share_none_is_plausible():
    assert book_value_per_share_is_plausible(None) is True


def test_market_cap_matches_real_tcs_figures():
    # TCS: price 2082, ~3.618B shares -> ~753,286 Cr, matches our own
    # computed market cap almost exactly.
    assert market_cap_matches_price_times_shares(753286, 2082.0, 3_618_087_518.0) is True


def test_market_cap_catches_double_counted_shares():
    # The Phase 1.5 split-double-counting bug produced exactly 2x.
    price, shares, real_market_cap = 1362.6, 1_928_314_320.0, 262752.11
    doubled_market_cap = real_market_cap * 2
    assert market_cap_matches_price_times_shares(doubled_market_cap, price, shares) is False


def test_market_cap_missing_inputs_is_plausible():
    assert market_cap_matches_price_times_shares(None, 100.0, 1000.0) is True
    assert market_cap_matches_price_times_shares(100.0, 100.0, None) is True
    assert market_cap_matches_price_times_shares(100.0, 100.0, 0) is True


def test_eps_price_ratio_plausible_real_value():
    assert eps_price_ratio_is_plausible(136.01, 2082.0) is True


def test_eps_price_ratio_catches_wrong_scale():
    # A TTM sum bug once produced ~0.80 against a price of ~1000 for INFY,
    # implying a P/E > 1000 -- an obvious scale mismatch, not a real P/E.
    assert eps_price_ratio_is_plausible(0.80, 1000.2) is False


def test_eps_price_ratio_negative_eps_within_band_is_plausible():
    assert eps_price_ratio_is_plausible(-5.0, 100.0) is True


def test_eps_price_ratio_missing_inputs_is_plausible():
    assert eps_price_ratio_is_plausible(None, 100.0) is True
    assert eps_price_ratio_is_plausible(10.0, None) is True


def test_pe_is_plausible_real_value():
    assert pe_is_plausible(15.31) is True


def test_pe_is_plausible_catches_scale_mismatch():
    # INFY's own raw (unit-inconsistent) EPS implied a P/E > 1000; the
    # DISPLAYED P/E (after falling back to Yahoo's correctly-scaled
    # trailingEps) should instead be plausible.
    assert pe_is_plausible(1250.25) is False
    assert pe_is_plausible(12.90) is True


def test_pe_is_plausible_none_is_plausible():
    assert pe_is_plausible(None) is True


def test_multiple_is_plausible_real_values():
    assert multiple_is_plausible("pe", 14.92) is True
    assert multiple_is_plausible("pb", 7.02) is True
    assert multiple_is_plausible("ev_ebitda", 10.51) is True
    assert multiple_is_plausible("ev_sales", 2.84) is True
    assert multiple_is_plausible("dividend_yield", 5.33) is True
    assert multiple_is_plausible("dividend_yield", 0.0) is True  # zero yield is real, not missing


def test_multiple_is_plausible_catches_infy_regression():
    # INFY's income statement (revenue/EBITDA/net income) and own book
    # value per share are each individually ~80-100x too small (see
    # docs/data-notes.md) -- the narrower per-input checks don't catch it,
    # but the resulting multiples obviously aren't plausible for a NIFTY
    # 50 constituent. These are INFY's actual (buggy) computed values.
    assert multiple_is_plausible("pb", 413.6266298960148) is False
    assert multiple_is_plausible("ev_ebitda", 793.1705661434281) is False


def test_multiple_is_plausible_boundaries_are_exclusive_except_dividend_yield():
    assert multiple_is_plausible("pe", 0.0) is False
    assert multiple_is_plausible("pe", 300.0) is False
    assert multiple_is_plausible("ev_ebitda", 100.0) is False
    assert multiple_is_plausible("ev_sales", 50.0) is False
    assert multiple_is_plausible("pb", 100.0) is False
    assert multiple_is_plausible("dividend_yield", 20.0) is False


def test_multiple_is_plausible_none_and_unknown_key_is_plausible():
    assert multiple_is_plausible("pe", None) is True
    assert multiple_is_plausible("peg", 999.0) is True  # not a gated key

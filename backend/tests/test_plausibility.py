from app.metrics.plausibility import (
    book_value_per_share_is_plausible,
    eps_price_ratio_is_plausible,
    market_cap_matches_price_times_shares,
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

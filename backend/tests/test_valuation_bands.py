from app.metrics.valuation_bands import band_summary, compute_pe_pb_band, trailing_eps_series


def test_trailing_eps_is_none_until_four_quarters_available():
    quarters = [
        {"period_end": "2024-06-30", "eps_diluted": 5},
        {"period_end": "2024-09-30", "eps_diluted": 6},
        {"period_end": "2024-12-31", "eps_diluted": 7},
    ]
    result = trailing_eps_series(quarters)
    assert all(r["trailing_eps"] is None for r in result)


def test_trailing_eps_sums_last_four_quarters_once_available():
    quarters = [
        {"period_end": "2024-06-30", "eps_diluted": 5},
        {"period_end": "2024-09-30", "eps_diluted": 6},
        {"period_end": "2024-12-31", "eps_diluted": 7},
        {"period_end": "2025-03-31", "eps_diluted": 8},
        {"period_end": "2025-06-30", "eps_diluted": 9},
    ]
    result = trailing_eps_series(quarters)
    assert result[3]["trailing_eps"] == 26  # 5+6+7+8
    assert result[4]["trailing_eps"] == 30  # 6+7+8+9


def test_pe_pb_band_steps_at_report_dates_not_interpolated():
    trailing_eps = [
        {"period_end": "2024-03-31", "trailing_eps": 10},
        {"period_end": "2024-06-30", "trailing_eps": 12},
    ]
    bvps = [{"period_end": "2024-03-31", "bvps": 50}]
    price_bars = [
        {"date": "2024-01-01", "close": 100},  # before first checkpoint
        {"date": "2024-04-01", "close": 120},  # after Q1 report
        {"date": "2024-07-01", "close": 132},  # after Q2 report
    ]
    band = compute_pe_pb_band(price_bars, trailing_eps, bvps)
    assert band[0]["pe"] is None  # no trailing EPS yet
    assert band[1]["pe"] == 12.0  # 120 / 10
    assert band[2]["pe"] == 11.0  # 132 / 12 -- stepped, not interpolated
    assert band[1]["pb"] == 2.4  # 120 / 50
    assert band[2]["pb"] == 132 / 50  # bvps unchanged, no Q2 balance sheet checkpoint


def test_band_summary_min_median_max_current():
    band = [{"pe": 10}, {"pe": 20}, {"pe": None}, {"pe": 30}]
    summary = band_summary(band, "pe")
    assert summary == {"min": 10, "median": 20, "max": 30, "current": 30}


def test_band_summary_all_none_returns_all_none():
    summary = band_summary([{"pe": None}], "pe")
    assert summary == {"min": None, "median": None, "max": None, "current": None}

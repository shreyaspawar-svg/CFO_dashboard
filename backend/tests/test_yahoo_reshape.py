from app.services.yahoo import _bars_from_chart, reshape_fundamentals_timeseries


def test_reshape_fundamentals_timeseries_merges_fields_by_date():
    raw = {
        "timeseries": {
            "result": [
                {
                    "meta": {"symbol": ["TCS.NS"], "type": ["annualTotalRevenue"]},
                    "annualTotalRevenue": [
                        {"asOfDate": "2023-03-31", "reportedValue": {"raw": 100.0}},
                        {"asOfDate": "2024-03-31", "reportedValue": {"raw": 120.0}},
                    ],
                },
                {
                    "meta": {"symbol": ["TCS.NS"], "type": ["annualNetIncome"]},
                    "annualNetIncome": [
                        {"asOfDate": "2024-03-31", "reportedValue": {"raw": 20.0}},
                    ],
                },
            ]
        }
    }
    records = reshape_fundamentals_timeseries(
        raw, keys=["TotalRevenue", "NetIncome"], timescale="annual"
    )
    assert records == [
        {"index": "2023-03-31", "TotalRevenue": 100.0},
        {"index": "2024-03-31", "TotalRevenue": 120.0, "NetIncome": 20.0},
    ]


def test_reshape_fundamentals_timeseries_ignores_wrong_timescale_and_unknown_keys():
    raw = {
        "timeseries": {
            "result": [
                {
                    "quarterlyTotalRevenue": [
                        {"asOfDate": "2024-06-30", "reportedValue": {"raw": 50.0}}
                    ]
                },
                {
                    "annualSomeUnrequestedField": [
                        {"asOfDate": "2024-03-31", "reportedValue": {"raw": 1.0}}
                    ]
                },
            ]
        }
    }
    records = reshape_fundamentals_timeseries(raw, keys=["TotalRevenue"], timescale="annual")
    assert records == []


def test_reshape_fundamentals_timeseries_skips_null_points():
    raw = {
        "timeseries": {
            "result": [
                {
                    "annualTotalRevenue": [
                        None,
                        {"asOfDate": "2024-03-31", "reportedValue": {"raw": 10.0}},
                    ]
                }
            ]
        }
    }
    records = reshape_fundamentals_timeseries(raw, keys=["TotalRevenue"], timescale="annual")
    assert records == [{"index": "2024-03-31", "TotalRevenue": 10.0}]


def test_bars_from_chart_zips_parallel_arrays():
    chart = {
        "timestamp": [1700000000, 1700086400],
        "indicators": {
            "quote": [
                {
                    "open": [10.0, 11.0],
                    "high": [12.0, 13.0],
                    "low": [9.0, 10.5],
                    "close": [11.5, 12.5],
                    "volume": [1000, 2000],
                }
            ]
        },
    }
    bars = _bars_from_chart(chart)
    assert len(bars) == 2
    assert bars[0]["Open"] == 10.0
    assert bars[1]["Close"] == 12.5
    assert bars[0]["Date"].tzinfo is not None


def test_bars_from_chart_handles_empty_chart():
    assert _bars_from_chart({}) == []

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.metrics.beta import compute_beta, daily_returns, paired_daily_returns

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "beta"


def _bars_from_fixture(filename: str) -> list[dict]:
    """Real captured Yahoo chart responses (tests/fixtures/beta/), not
    synthetic arrays -- see PLAN.md "Phase 4.1 review" item 2: the old
    `compute_beta`-against-synthetic-arrays tests below all passed while the
    real pipeline was silently broken, because synthetic data never
    exercised how the two return series get built from live bars."""
    chart = json.loads((FIXTURES_DIR / filename).read_text())
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    return [
        {
            "Date": datetime.fromtimestamp(ts, tz=timezone.utc),
            "Close": closes[i] if i < len(closes) else None,
        }
        for i, ts in enumerate(timestamps)
    ]


def test_daily_returns_basic():
    closes = [100.0, 110.0, 99.0]
    returns = daily_returns(closes)
    assert returns == pytest.approx([0.10, -0.10])


def test_daily_returns_skips_gaps():
    closes = [100.0, None, 110.0]
    returns = daily_returns(closes)
    assert returns == []  # neither pair has both sides present


def test_daily_returns_skips_zero_prior_close():
    closes = [0.0, 100.0]
    assert daily_returns(closes) == []


def test_compute_beta_of_a_series_against_itself_is_one():
    returns = [0.01, -0.02, 0.03, -0.01, 0.02] * 10  # 50 observations
    assert compute_beta(returns, returns) == pytest.approx(1.0)


def test_compute_beta_double_volatility_is_two():
    benchmark = [0.01, -0.02, 0.03, -0.01, 0.02] * 10
    symbol = [x * 2 for x in benchmark]
    assert compute_beta(symbol, benchmark) == pytest.approx(2.0)


def test_compute_beta_inverse_is_negative():
    benchmark = [0.01, -0.02, 0.03, -0.01, 0.02] * 10
    symbol = [-x for x in benchmark]
    assert compute_beta(symbol, benchmark) == pytest.approx(-1.0)


def test_compute_beta_too_few_observations_is_none():
    assert compute_beta([0.01] * 10, [0.01] * 10) is None


def test_compute_beta_zero_variance_benchmark_is_none():
    assert compute_beta([0.01] * 40, [0.0] * 40) is None


def test_compute_beta_uses_longest_common_trailing_window():
    benchmark = [0.01, -0.02, 0.03, -0.01, 0.02] * 10
    symbol = benchmark[5:]  # shorter series
    beta = compute_beta(symbol, benchmark)
    assert beta == pytest.approx(1.0)


# --- Real-data regression: PLAN.md "Phase 4.1 review" item 2 -------------
#
# tests/fixtures/beta/{tcs,nsei}_chart_1y.json are real captured 1-year
# daily bars. ^NSEI's own feed has 5 scattered null closes that TCS doesn't
# share on the same days -- exactly the condition that broke position-based
# pairing (each null silently drops two of *only* NSEI's return entries,
# shifting every subsequent "same position" comparison onto the wrong day).


def test_real_fixture_still_reproduces_the_null_close_condition():
    """Sanity check on the fixture itself, so a future re-capture that
    happens to land on a clean data day doesn't make the tests below
    vacuously pass."""
    nsei_bars = _bars_from_fixture("nsei_chart_1y.json")
    tcs_bars = _bars_from_fixture("tcs_chart_1y.json")
    null_dates = {b["Date"].date().isoformat() for b in nsei_bars if b["Close"] is None}
    assert len(null_dates) == 5
    assert not any(b["Close"] is None for b in tcs_bars)


def test_paired_daily_returns_drops_nulls_from_both_series_symmetrically():
    tcs_bars = _bars_from_fixture("tcs_chart_1y.json")
    nsei_bars = _bars_from_fixture("nsei_chart_1y.json")
    symbol_returns, benchmark_returns = paired_daily_returns(tcs_bars, nsei_bars)
    assert len(symbol_returns) == len(benchmark_returns) == 246


def test_real_tcs_beta_is_plausible_after_the_date_alignment_fix():
    tcs_bars = _bars_from_fixture("tcs_chart_1y.json")
    nsei_bars = _bars_from_fixture("nsei_chart_1y.json")
    symbol_returns, benchmark_returns = paired_daily_returns(tcs_bars, nsei_bars)
    beta = compute_beta(symbol_returns, benchmark_returns)
    assert beta is not None
    # Large NIFTY constituents typically run 0.6-1.3x; IT majors often sit
    # a bit under 1 (revenue/currency dynamics decouple them somewhat from
    # the domestic index) -- PLAN.md "Phase 4.1 review" item 2's band.
    assert 0.3 < beta < 2.0


def test_old_positional_pairing_on_the_same_real_data_gave_a_materially_lower_beta():
    """Proves the fix isn't a no-op on real data: the OLD code path (build
    each series' returns independently via `daily_returns`, then hand both
    lists straight to `compute_beta`, which zips by trailing position) is
    reproduced here directly and shown to diverge materially from the fixed
    `paired_daily_returns` result on the exact same fixture."""
    tcs_bars = _bars_from_fixture("tcs_chart_1y.json")
    nsei_bars = _bars_from_fixture("nsei_chart_1y.json")

    old_symbol_returns = daily_returns([b["Close"] for b in tcs_bars])
    old_benchmark_returns = daily_returns([b["Close"] for b in nsei_bars])
    old_beta = compute_beta(old_symbol_returns, old_benchmark_returns)

    new_symbol_returns, new_benchmark_returns = paired_daily_returns(tcs_bars, nsei_bars)
    new_beta = compute_beta(new_symbol_returns, new_benchmark_returns)

    assert old_beta is not None and new_beta is not None
    assert old_beta < 0.15  # the bug's signature: implausibly near zero
    assert new_beta > old_beta + 0.3  # materially different, not a rounding wobble

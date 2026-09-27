"""FCFF (free cash flow to firm) discounted cash flow, and its reverse:
solving for the growth rate the current price implies.

Pure functions -- no I/O. Inputs (FCFF, net debt) are expected in the same
₹-crore units the rest of the app uses; per-share outputs come out in ₹.
"""

from __future__ import annotations

DEFAULT_FORECAST_YEARS = 5
_BISECTION_ITERATIONS = 60
_GROWTH_SEARCH_LOW_PCT = -50.0
_GROWTH_SEARCH_HIGH_PCT = 100.0


def _project_and_discount_fcff(
    base_fcff: float,
    growth_rate_pct: float,
    wacc_pct: float,
    terminal_growth_pct: float,
    forecast_years: int,
) -> float | None:
    """Enterprise value: sum of discounted projected FCFF plus a
    discounted Gordon-growth terminal value. None if wacc <= terminal
    growth (the terminal-value formula divides by zero or goes negative)."""
    if wacc_pct <= terminal_growth_pct:
        return None

    wacc = wacc_pct / 100
    growth = growth_rate_pct / 100
    terminal_growth = terminal_growth_pct / 100

    pv_sum = 0.0
    fcff = base_fcff
    for year in range(1, forecast_years + 1):
        fcff = fcff * (1 + growth)
        pv_sum += fcff / (1 + wacc) ** year

    terminal_value = fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** forecast_years

    return pv_sum + pv_terminal


def dcf_intrinsic_value(
    base_fcff: float | None,
    growth_rate_pct: float | None,
    wacc_pct: float | None,
    terminal_growth_pct: float | None,
    net_debt: float | None,
    shares_outstanding: float | None,
    forecast_years: int = DEFAULT_FORECAST_YEARS,
) -> dict[str, float | None]:
    """A simple 2-stage FCFF DCF: explicit `growth_rate_pct` for
    `forecast_years`, then a Gordon-growth terminal value at
    `terminal_growth_pct`, discounted at `wacc_pct`.

    Returns a dict with `enterprise_value`, `equity_value`, and
    `intrinsic_value_per_share` -- each `None` if its required inputs are
    missing or the WACC/terminal-growth relationship is invalid.
    """
    if (
        base_fcff is None
        or growth_rate_pct is None
        or wacc_pct is None
        or terminal_growth_pct is None
        or forecast_years <= 0
    ):
        return {"enterprise_value": None, "equity_value": None, "intrinsic_value_per_share": None}

    ev = _project_and_discount_fcff(
        base_fcff, growth_rate_pct, wacc_pct, terminal_growth_pct, forecast_years
    )
    if ev is None:
        return {"enterprise_value": None, "equity_value": None, "intrinsic_value_per_share": None}

    equity_value = ev - (net_debt or 0)
    per_share = (
        equity_value / shares_outstanding
        if shares_outstanding is not None and shares_outstanding > 0
        else None
    )
    return {
        "enterprise_value": ev,
        "equity_value": equity_value,
        "intrinsic_value_per_share": per_share,
    }


def dcf_sensitivity_table(
    base_fcff: float | None,
    growth_rate_pct: float | None,
    wacc_values_pct: list[float],
    terminal_growth_values_pct: list[float],
    net_debt: float | None,
    shares_outstanding: float | None,
    forecast_years: int = DEFAULT_FORECAST_YEARS,
) -> dict:
    """Intrinsic value/share for every (WACC, terminal growth) pair in the
    grid -- monotonically decreasing in WACC and increasing in terminal
    growth, holding the other axis fixed (each column/row's contents are
    just a fixed-terminal-growth or fixed-WACC slice of `dcf_intrinsic_value`,
    which is itself monotonic in each of those two inputs)."""
    values: list[list[float | None]] = []
    for wacc_pct in wacc_values_pct:
        row = []
        for terminal_growth_pct in terminal_growth_values_pct:
            result = dcf_intrinsic_value(
                base_fcff, growth_rate_pct, wacc_pct, terminal_growth_pct, net_debt, shares_outstanding, forecast_years
            )
            row.append(result["intrinsic_value_per_share"])
        values.append(row)
    return {
        "wacc_values_pct": wacc_values_pct,
        "terminal_growth_values_pct": terminal_growth_values_pct,
        "values": values,
    }


def reverse_dcf_implied_growth(
    base_fcff: float | None,
    current_price: float | None,
    wacc_pct: float | None,
    terminal_growth_pct: float | None,
    net_debt: float | None,
    shares_outstanding: float | None,
    forecast_years: int = DEFAULT_FORECAST_YEARS,
) -> float | None:
    """The constant forecast growth rate (%) that makes `dcf_intrinsic_value`
    equal `current_price`, found by bisection (DCF value is monotonically
    increasing in growth rate for wacc > terminal growth, so the search is
    well-posed). None if any required input is missing, if WACC doesn't
    exceed terminal growth, or if the implied growth falls outside a wide
    [-50%, 100%] search band (the DCF's growth/WACC/terminal-growth
    combination doesn't support solving for a bounded growth rate)."""
    if (
        base_fcff is None
        or current_price is None
        or wacc_pct is None
        or terminal_growth_pct is None
        or shares_outstanding is None
        or shares_outstanding <= 0
        or wacc_pct <= terminal_growth_pct
    ):
        return None

    target_equity_value = current_price * shares_outstanding

    def equity_value_at(growth_pct: float) -> float | None:
        ev = _project_and_discount_fcff(
            base_fcff, growth_pct, wacc_pct, terminal_growth_pct, forecast_years
        )
        if ev is None:
            return None
        return ev - (net_debt or 0)

    low, high = _GROWTH_SEARCH_LOW_PCT, _GROWTH_SEARCH_HIGH_PCT
    value_at_low = equity_value_at(low)
    value_at_high = equity_value_at(high)
    if value_at_low is None or value_at_high is None:
        return None
    if not (value_at_low <= target_equity_value <= value_at_high):
        return None  # implied growth is outside the search band

    for _ in range(_BISECTION_ITERATIONS):
        mid = (low + high) / 2
        value_at_mid = equity_value_at(mid)
        if value_at_mid is None:
            return None
        if value_at_mid < target_equity_value:
            low = mid
        else:
            high = mid

    return (low + high) / 2

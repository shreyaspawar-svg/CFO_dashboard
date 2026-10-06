"""Pure functions for the 20-KPI CFO scorecard (RIL single-company pivot)
that aren't already covered by `app.metrics.ratios`. Same conventions as
that module: plain numbers in, `float | None` out, no I/O.

Most of the scorecard's 20 KPIs reuse `ratios.py` functions directly
(margin, yoy_growth, net_debt_to_ebitda, debtor/inventory/payable days,
cash_conversion_cycle, free_cash_flow, current_ratio, return_on_capital_
employed) -- the assembly layer (`app.services.kpi_scorecard_engine`)
just has to feed them TTM/annualised inputs instead of annual ones. Only
the two genuinely new calculations below live here.
"""

from __future__ import annotations


def liquidity_runway_months(cash: float | None, quarterly_fcf: float | None) -> float | None:
    """Months of cash runway at the current quarter's free-cash-flow burn
    rate. Only meaningful when the company is actually burning cash
    (`quarterly_fcf < 0`) -- a profitable, FCF-positive quarter has no
    "runway" to run out of, so this returns `None` rather than a
    nonsensical (or infinite) number; the caller shows a liquidity ratio
    instead for that case."""
    if cash is None or quarterly_fcf is None or quarterly_fcf >= 0:
        return None
    monthly_burn = abs(quarterly_fcf) / 3
    if monthly_burn == 0:
        return None
    return cash / monthly_burn


def capex_return_pct(incremental_ebit: float | None, trailing_capex: float | None) -> float | None:
    """Approximate return on recent capital investment: the EBIT earned
    over the last year divided by the CAPEX deployed roughly a year
    earlier, as a percentage. A heuristic (real capital-project paybacks
    span many years and specific projects, not a single trailing-EBIT
    delta) -- shown as an approximation, not a precise IRR."""
    if incremental_ebit is None or trailing_capex is None or trailing_capex == 0:
        return None
    return incremental_ebit / abs(trailing_capex) * 100

"""Pure, unit-tested ratio functions. Every function takes plain numbers
(never a period dict) and returns `float | None` -- `None` for "can't be
computed" (missing input, zero/undefined denominator), never `0`, `inf` or
`nan`. This module has no I/O and no knowledge of caching, symbols, or
templates -- callers assemble the inputs.

Percentages are returned as e.g. `12.5` for 12.5%, not `0.125`. Ratios that
are conventionally expressed as a multiple (D/E, P/E, P/B, EV/EBITDA, ...)
are returned as that multiple (e.g. `1.8` for a 1.8x P/B), not a percentage.
"""

from __future__ import annotations

import math
from typing import TypedDict

DAYS_PER_YEAR = 365.0


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    result = numerator / denominator
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def average_of(a: float | None, b: float | None) -> float | None:
    """Average of two period-end balances (e.g. opening + closing equity),
    falling back to whichever one is present if only one is."""
    if a is not None and b is not None:
        return (a + b) / 2
    return a if a is not None else b


# --------------------------------------------------------------------------
# Growth
# --------------------------------------------------------------------------


def yoy_growth(current: float | None, previous: float | None) -> float | None:
    """Year-over-year growth, as a percentage. `None` when the prior
    period's value is missing or non-positive.

    PLAN.md "Phase 4.2 review": growth from a non-positive base isn't a
    meaningful percentage, even when it's computable -- INDIGO's PAT
    swinging from -Rs306 Cr to +Rs8,172 Cr isn't "+2,673% growth", it's a
    sign change a percentage can't honestly describe. An earlier version
    of this function let a negative-previous case through (reasoning that
    "a loss shrinking is meaningful growth"), but that conflates two
    different things: a same-sign move (-200 -> -100, still a loss, arguably
    describable as "improved") and a sign-crossing move (-306 -> +8,172,
    not a "growth rate" in any normal sense). Rather than special-case the
    same-sign case, the accepted product decision is simpler and safer: any
    non-positive prior value makes the percentage not meaningful, full
    stop. Use `growth_reason` to distinguish this from a genuinely missing
    input for display purposes ("n.m." vs "—")."""
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) / previous * 100


def growth_reason(current: float | None, previous: float | None) -> str | None:
    """Why `yoy_growth(current, previous)` returned `None`, or `None` if it
    returned a real value. `"missing"`: an input is genuinely absent.
    `"not_meaningful"`: both inputs are present but the prior value is
    non-positive (PLAN.md "Phase 4.2 review")."""
    if current is None or previous is None:
        return "missing"
    if previous <= 0:
        return "not_meaningful"
    return None


def cagr(begin_value: float | None, end_value: float | None, years: float | None) -> float | None:
    """Compound annual growth rate, as a percentage. Undefined (None) when
    either endpoint is zero/negative (a fractional power of a negative
    number isn't a real CAGR) or `years` isn't positive."""
    if begin_value is None or end_value is None or years is None:
        return None
    if begin_value <= 0 or end_value <= 0 or years <= 0:
        return None
    return ((end_value / begin_value) ** (1 / years) - 1) * 100


def cagr_reason(begin_value: float | None, end_value: float | None, years: float | None) -> str | None:
    """Why `cagr(begin_value, end_value, years)` returned `None`, or `None`
    if it returned a real value. `"missing"`: an input is absent or `years`
    isn't positive (no valid span to compute over). `"not_meaningful"`:
    both endpoints are present and `years` is valid, but an endpoint is
    non-positive -- a fractional power of a negative base isn't a real
    CAGR (PLAN.md "Phase 4.2 review", same principle as `growth_reason`)."""
    if begin_value is None or end_value is None or years is None or years <= 0:
        return "missing"
    if begin_value <= 0 or end_value <= 0:
        return "not_meaningful"
    return None


# --------------------------------------------------------------------------
# Profitability (margins)
# --------------------------------------------------------------------------


def margin(numerator: float | None, revenue: float | None) -> float | None:
    """Generic `numerator / revenue * 100`, for gross/EBITDA/EBIT/PAT margins."""
    result = _safe_div(numerator, revenue)
    return result * 100 if result is not None else None


# --------------------------------------------------------------------------
# Returns
# --------------------------------------------------------------------------


def return_on_equity(net_income: float | None, avg_equity: float | None) -> float | None:
    """ROE, as a percentage. Computed even when `avg_equity` is negative
    (real, if unusual, balance-sheet state) -- callers should flag a
    negative-equity ROE for interpretation, not hide the number."""
    result = _safe_div(net_income, avg_equity)
    return result * 100 if result is not None else None


def return_on_assets(net_income: float | None, avg_total_assets: float | None) -> float | None:
    result = _safe_div(net_income, avg_total_assets)
    return result * 100 if result is not None else None


def capital_employed(
    total_assets: float | None, current_liabilities: float | None
) -> float | None:
    if total_assets is None or current_liabilities is None:
        return None
    return total_assets - current_liabilities


def return_on_capital_employed(ebit: float | None, capital_employed_: float | None) -> float | None:
    result = _safe_div(ebit, capital_employed_)
    return result * 100 if result is not None else None


def invested_capital(
    total_debt: float | None, total_equity: float | None, cash: float | None
) -> float | None:
    if total_debt is None or total_equity is None:
        return None
    return total_debt + total_equity - (cash or 0)


def nopat(ebit: float | None, effective_tax_rate: float | None) -> float | None:
    """Net operating profit after tax = EBIT x (1 - effective tax rate)."""
    if ebit is None or effective_tax_rate is None:
        return None
    return ebit * (1 - effective_tax_rate)


def effective_tax_rate(tax: float | None, pretax_income: float | None) -> float | None:
    if tax is None or pretax_income is None or pretax_income == 0:
        return None
    rate = tax / pretax_income
    # Guard against nonsensical rates from a near-zero or negative
    # pretax_income (e.g. a barely-profitable or loss-making year) --
    # ROIC on top of a wild tax rate is more misleading than absent.
    if rate < -1 or rate > 1:
        return None
    return rate


def return_on_invested_capital(
    ebit: float | None,
    effective_tax_rate_: float | None,
    invested_capital_: float | None,
) -> float | None:
    nopat_ = nopat(ebit, effective_tax_rate_)
    result = _safe_div(nopat_, invested_capital_)
    return result * 100 if result is not None else None


def dupont_decomposition(
    net_income: float | None,
    revenue: float | None,
    avg_total_assets: float | None,
    avg_equity: float | None,
) -> dict[str, float | None]:
    """3-step DuPont: ROE = net margin x asset turnover x equity multiplier.
    Each component is independently None-safe; `roe_check` (the product) is
    only populated when all three components are, so it can be compared
    against `return_on_equity`'s direct calculation as a sanity check."""
    net_margin = _safe_div(net_income, revenue)
    asset_turnover_ = _safe_div(revenue, avg_total_assets)
    equity_multiplier = _safe_div(avg_total_assets, avg_equity)

    roe_check = None
    if net_margin is not None and asset_turnover_ is not None and equity_multiplier is not None:
        roe_check = net_margin * asset_turnover_ * equity_multiplier * 100

    return {
        "net_margin_pct": net_margin * 100 if net_margin is not None else None,
        "asset_turnover": asset_turnover_,
        "equity_multiplier": equity_multiplier,
        "roe_check_pct": roe_check,
    }


def dupont_bank(
    net_income: float | None,
    avg_total_assets: float | None,
    avg_equity: float | None,
) -> dict[str, float | None]:
    """2-step DuPont for bank/NBFC templates (PLAN.md §4.3): ROE = ROA x
    Leverage (Assets/Equity). A bank's "revenue" (interest + non-interest
    income) doesn't decompose into a margin/turnover split the way a
    general company's sales do, so this shows the 2 factors a bank's
    profitability is actually framed around, not a 3-step split that
    forces a general-company shape onto a business model it doesn't fit."""
    roa = _safe_div(net_income, avg_total_assets)
    leverage = _safe_div(avg_total_assets, avg_equity)

    roe_check = None
    if roa is not None and leverage is not None:
        roe_check = roa * leverage * 100

    return {
        "roa_pct": roa * 100 if roa is not None else None,
        "leverage": leverage,
        "roe_check_pct": roe_check,
    }


# --------------------------------------------------------------------------
# Leverage
# --------------------------------------------------------------------------


def debt_to_equity(total_debt: float | None, total_equity: float | None) -> float | None:
    """Real, unguarded division -- a negative result (negative equity) is a
    meaningful, if alarming, signal, not an error to hide."""
    return _safe_div(total_debt, total_equity)


def net_debt_to_ebitda(
    total_debt: float | None, cash: float | None, ebitda: float | None
) -> float | None:
    if total_debt is None:
        return None
    net_debt = total_debt - (cash or 0)
    return _safe_div(net_debt, ebitda)


def interest_coverage(ebit: float | None, interest_expense: float | None) -> float | None:
    """EBIT / interest expense. None when interest expense is exactly zero
    (undefined -- not "infinite coverage")."""
    return _safe_div(ebit, interest_expense)


def debt_to_assets(total_debt: float | None, total_assets: float | None) -> float | None:
    return _safe_div(total_debt, total_assets)


# --------------------------------------------------------------------------
# Liquidity
# --------------------------------------------------------------------------


def current_ratio(current_assets: float | None, current_liabilities: float | None) -> float | None:
    return _safe_div(current_assets, current_liabilities)


def quick_ratio(
    current_assets: float | None,
    inventory: float | None,
    current_liabilities: float | None,
) -> float | None:
    """(current assets - inventory) / current liabilities. `inventory=None`
    is treated as 0 (common for non-manufacturing businesses where Yahoo
    doesn't report an inventory line at all)."""
    if current_assets is None:
        return None
    return _safe_div(current_assets - (inventory or 0), current_liabilities)


def cash_ratio(cash: float | None, current_liabilities: float | None) -> float | None:
    return _safe_div(cash, current_liabilities)


# --------------------------------------------------------------------------
# Efficiency
# --------------------------------------------------------------------------


def asset_turnover(revenue: float | None, avg_total_assets: float | None) -> float | None:
    return _safe_div(revenue, avg_total_assets)


def debtor_days(receivables: float | None, revenue: float | None) -> float | None:
    result = _safe_div(receivables, revenue)
    return result * DAYS_PER_YEAR if result is not None else None


def inventory_days(inventory: float | None, cogs: float | None) -> float | None:
    result = _safe_div(inventory, cogs)
    return result * DAYS_PER_YEAR if result is not None else None


def payable_days(payables: float | None, cogs: float | None) -> float | None:
    result = _safe_div(payables, cogs)
    return result * DAYS_PER_YEAR if result is not None else None


def cash_conversion_cycle(
    debtor_days_: float | None, inventory_days_: float | None, payable_days_: float | None
) -> float | None:
    if debtor_days_ is None or inventory_days_ is None or payable_days_ is None:
        return None
    return debtor_days_ + inventory_days_ - payable_days_


# --------------------------------------------------------------------------
# Cash flow
# --------------------------------------------------------------------------


def free_cash_flow(
    cfo: float | None, capex: float | None, reported_fcf: float | None = None
) -> float | None:
    """Prefers Yahoo's own reported FreeCashFlow figure (more authoritative
    -- it may include adjustments we don't have inputs for); falls back to
    CFO + CapEx (CapEx is a negative outflow in Yahoo's convention) when
    Yahoo doesn't report it directly."""
    if reported_fcf is not None:
        return reported_fcf
    if cfo is None:
        return None
    return cfo + (capex or 0)


def fcf_margin(fcf: float | None, revenue: float | None) -> float | None:
    result = _safe_div(fcf, revenue)
    return result * 100 if result is not None else None


def cfo_to_pat(cfo: float | None, net_income: float | None) -> float | None:
    """Earnings-quality check: CFO meaningfully below net income can signal
    aggressive accrual accounting. Sign is preserved (a negative net_income
    flips the ratio's sign, which is itself informative)."""
    return _safe_div(cfo, net_income)


def capex_intensity(capex: float | None, revenue: float | None) -> float | None:
    if capex is None:
        return None
    result = _safe_div(abs(capex), revenue)
    return result * 100 if result is not None else None


# --------------------------------------------------------------------------
# Valuation
# --------------------------------------------------------------------------


def enterprise_value(
    market_cap: float | None,
    total_debt: float | None,
    cash: float | None,
    minority_interest: float | None = None,
) -> float | None:
    """EV = market cap (parent shareholders only) + total debt + minority
    interest - cash. Minority interest is added, not netted into equity,
    per PLAN.md "Phase 2 review" item 1: EV should reflect the whole
    consolidated enterprise even though market cap only prices the
    parent's shares."""
    if market_cap is None:
        return None
    return market_cap + (total_debt or 0) + (minority_interest or 0) - (cash or 0)


def price_to_per_share_value(price: float | None, per_share_value: float | None) -> float | None:
    """Generic `price / per_share_value` -- P/E (value=EPS) and P/B-by-book-
    value-per-share (value=book value/share) are both this same shape.
    None when `per_share_value` is exactly zero. A negative value produces
    a negative ratio, which is real (flag downstream, don't hide it)."""
    return _safe_div(price, per_share_value)


def price_to_earnings(price: float | None, eps: float | None) -> float | None:
    return price_to_per_share_value(price, eps)


def price_to_book(market_cap: float | None, total_equity: float | None) -> float | None:
    return _safe_div(market_cap, total_equity)


def book_value_per_share(total_equity: float | None, shares_outstanding: float | None) -> float | None:
    return _safe_div(total_equity, shares_outstanding)


def relative_divergence(a: float | None, b: float | None) -> float | None:
    """|a - b| / |b| as a percentage -- used to flag when our own
    fundamentals-derived figure and Yahoo's own summary-stats figure
    disagree by more than a threshold (PLAN.md "Phase 2 review" item 4)."""
    if a is None or b is None or b == 0:
        return None
    return abs(a - b) / abs(b) * 100


def ev_to_ebitda(ev: float | None, ebitda: float | None) -> float | None:
    return _safe_div(ev, ebitda)


def ev_to_sales(ev: float | None, revenue: float | None) -> float | None:
    return _safe_div(ev, revenue)


def peg_ratio(pe: float | None, growth_rate_pct: float | None) -> float | None:
    """PEG is only meaningful for positive P/E and positive growth; both a
    negative P/E and negative/zero growth make the ratio uninterpretable."""
    if pe is None or growth_rate_pct is None or pe <= 0 or growth_rate_pct <= 0:
        return None
    return pe / growth_rate_pct


def dividend_yield(dividend_per_share: float | None, price: float | None) -> float | None:
    result = _safe_div(dividend_per_share, price)
    return result * 100 if result is not None else None


def earnings_yield(eps: float | None, price: float | None) -> float | None:
    result = _safe_div(eps, price)
    return result * 100 if result is not None else None


def payout_ratio(dividend_per_share: float | None, eps: float | None) -> float | None:
    """None when EPS is zero or negative (a payout ratio against a loss
    isn't a meaningful percentage)."""
    if dividend_per_share is None or eps is None or eps <= 0:
        return None
    return dividend_per_share / eps * 100


# --------------------------------------------------------------------------
# Bank / NBFC / insurance derived
# --------------------------------------------------------------------------


def net_interest_margin(
    net_interest_income: float | None, avg_total_assets: float | None
) -> float | None:
    """NIM PROXY: true NIM divides by average interest-earning assets, which
    isn't a field this free data source exposes; total assets is used as a
    stand-in (documented explicitly, per PLAN.md §2)."""
    result = _safe_div(net_interest_income, avg_total_assets)
    return result * 100 if result is not None else None


def cost_to_income(
    non_interest_expense: float | None,
    net_interest_income: float | None,
    non_interest_income: float | None,
) -> float | None:
    if net_interest_income is None and non_interest_income is None:
        return None
    total_income = (net_interest_income or 0) + (non_interest_income or 0)
    result = _safe_div(non_interest_expense, total_income)
    return result * 100 if result is not None else None


# --------------------------------------------------------------------------
# Quality flags
# --------------------------------------------------------------------------


def altman_z_score(
    working_capital: float | None,
    retained_earnings: float | None,
    ebit: float | None,
    market_cap: float | None,
    total_liabilities: float | None,
    revenue: float | None,
    total_assets: float | None,
) -> float | None:
    """Classic 5-factor Altman Z-score for public non-financial companies.
    Not meaningful for banks/NBFCs/insurers (no current_assets/liabilities
    concept) -- callers should only compute this for the `general` and
    `exchange` templates."""
    if total_assets is None or total_assets == 0:
        return None
    a = _safe_div(working_capital, total_assets)
    b = _safe_div(retained_earnings, total_assets)
    c = _safe_div(ebit, total_assets)
    d = _safe_div(market_cap, total_liabilities)
    e = _safe_div(revenue, total_assets)
    if any(component is None for component in (a, b, c, d, e)):
        return None
    return 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e


def piotroski_f_score(current: dict, prior: dict) -> tuple[int, int]:
    """9-point Piotroski F-score comparing two consecutive annual periods.

    Each period dict may contain: net_income, total_assets, cfo, total_debt,
    total_equity, current_assets, current_liabilities, shares_outstanding,
    gross_profit, revenue. Any single criterion is scored 1/0 only when
    every input it needs is present in BOTH periods; otherwise it's left out
    of both the numerator and the denominator, so a bank missing gross
    margin/current-ratio inputs gets a score out of fewer than 9 points
    rather than being penalised for data it was never going to have.

    Returns (points_earned, points_possible).
    """
    points_earned = 0
    points_possible = 0

    def _score(condition_value: bool | None) -> None:
        nonlocal points_earned, points_possible
        if condition_value is None:
            return
        points_possible += 1
        if condition_value:
            points_earned += 1

    curr_roa = return_on_assets(current.get("net_income"), current.get("total_assets"))
    prior_roa = return_on_assets(prior.get("net_income"), prior.get("total_assets"))

    _score(curr_roa > 0 if curr_roa is not None else None)
    _score(current.get("cfo") > 0 if current.get("cfo") is not None else None)
    _score(
        curr_roa > prior_roa if curr_roa is not None and prior_roa is not None else None
    )
    _score(
        current.get("cfo") > current.get("net_income")
        if current.get("cfo") is not None and current.get("net_income") is not None
        else None
    )

    curr_leverage = debt_to_assets(current.get("total_debt"), current.get("total_assets"))
    prior_leverage = debt_to_assets(prior.get("total_debt"), prior.get("total_assets"))
    _score(
        curr_leverage < prior_leverage
        if curr_leverage is not None and prior_leverage is not None
        else None
    )

    curr_current_ratio = current_ratio(
        current.get("current_assets"), current.get("current_liabilities")
    )
    prior_current_ratio = current_ratio(
        prior.get("current_assets"), prior.get("current_liabilities")
    )
    _score(
        curr_current_ratio > prior_current_ratio
        if curr_current_ratio is not None and prior_current_ratio is not None
        else None
    )

    curr_shares = current.get("shares_outstanding")
    prior_shares = prior.get("shares_outstanding")
    _score(curr_shares <= prior_shares if curr_shares is not None and prior_shares is not None else None)

    curr_gross_margin = margin(current.get("gross_profit"), current.get("revenue"))
    prior_gross_margin = margin(prior.get("gross_profit"), prior.get("revenue"))
    _score(
        curr_gross_margin > prior_gross_margin
        if curr_gross_margin is not None and prior_gross_margin is not None
        else None
    )

    curr_asset_turnover = asset_turnover(current.get("revenue"), current.get("total_assets"))
    prior_asset_turnover = asset_turnover(prior.get("revenue"), prior.get("total_assets"))
    _score(
        curr_asset_turnover > prior_asset_turnover
        if curr_asset_turnover is not None and prior_asset_turnover is not None
        else None
    )

    return points_earned, points_possible


class AltmanZComponent(TypedDict):
    label: str
    value: float | None


class AltmanZDetail(TypedDict):
    score: float | None
    zone: str | None
    components: list[AltmanZComponent]


def altman_z_score_detailed(
    working_capital: float | None,
    retained_earnings: float | None,
    ebit: float | None,
    market_cap: float | None,
    total_liabilities: float | None,
    revenue: float | None,
    total_assets: float | None,
) -> AltmanZDetail:
    """Same 5-factor Altman Z as `altman_z_score`, plus each labelled
    component and the distress zone (PLAN.md §4.3 item 6) -- kept as a
    separate function rather than changing `altman_z_score`'s return type,
    since `metrics_engine.py`'s flat `metrics` dict needs a plain float."""
    a = _safe_div(working_capital, total_assets)
    b = _safe_div(retained_earnings, total_assets)
    c = _safe_div(ebit, total_assets)
    d = _safe_div(market_cap, total_liabilities)
    e = _safe_div(revenue, total_assets)
    components = [
        {"label": "Working capital / Total assets", "value": a},
        {"label": "Retained earnings / Total assets", "value": b},
        {"label": "EBIT / Total assets", "value": c},
        {"label": "Market cap / Total liabilities", "value": d},
        {"label": "Revenue / Total assets", "value": e},
    ]
    if any(component is None for component in (a, b, c, d, e)):
        return {"score": None, "zone": None, "components": components}
    score = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e
    if score >= 2.99:
        zone = "safe"
    elif score >= 1.8:
        zone = "grey"
    else:
        zone = "distress"
    return {"score": score, "zone": zone, "components": components}


class PiotroskiTest(TypedDict):
    label: str
    passed: bool | None


class PiotroskiDetail(TypedDict):
    earned: int
    possible: int
    tests: list[PiotroskiTest]


def piotroski_f_score_detailed(current: dict, prior: dict) -> PiotroskiDetail:
    """Same 9-point Piotroski F-score as `piotroski_f_score`, plus a
    labelled pass/fail checklist (PLAN.md §4.3 item 6)."""
    tests: list[PiotroskiTest] = []
    earned = 0
    possible = 0

    def _test(label: str, condition_value: bool | None) -> None:
        nonlocal earned, possible
        tests.append({"label": label, "passed": condition_value})
        if condition_value is None:
            return
        possible += 1
        if condition_value:
            earned += 1

    curr_roa = return_on_assets(current.get("net_income"), current.get("total_assets"))
    prior_roa = return_on_assets(prior.get("net_income"), prior.get("total_assets"))

    _test("Positive ROA", curr_roa > 0 if curr_roa is not None else None)
    _test(
        "Positive operating cash flow",
        current.get("cfo") > 0 if current.get("cfo") is not None else None,
    )
    _test(
        "ROA improved vs prior year",
        curr_roa > prior_roa if curr_roa is not None and prior_roa is not None else None,
    )
    _test(
        "Operating cash flow exceeds net income (earnings quality)",
        current.get("cfo") > current.get("net_income")
        if current.get("cfo") is not None and current.get("net_income") is not None
        else None,
    )

    curr_leverage = debt_to_assets(current.get("total_debt"), current.get("total_assets"))
    prior_leverage = debt_to_assets(prior.get("total_debt"), prior.get("total_assets"))
    _test(
        "Leverage (Debt/Assets) decreased",
        curr_leverage < prior_leverage if curr_leverage is not None and prior_leverage is not None else None,
    )

    curr_current_ratio = current_ratio(current.get("current_assets"), current.get("current_liabilities"))
    prior_current_ratio = current_ratio(prior.get("current_assets"), prior.get("current_liabilities"))
    _test(
        "Current ratio improved",
        curr_current_ratio > prior_current_ratio
        if curr_current_ratio is not None and prior_current_ratio is not None
        else None,
    )

    curr_shares = current.get("shares_outstanding")
    prior_shares = prior.get("shares_outstanding")
    _test(
        "No new shares issued (non-dilutive)",
        curr_shares <= prior_shares if curr_shares is not None and prior_shares is not None else None,
    )

    curr_gross_margin = margin(current.get("gross_profit"), current.get("revenue"))
    prior_gross_margin = margin(prior.get("gross_profit"), prior.get("revenue"))
    _test(
        "Gross margin improved",
        curr_gross_margin > prior_gross_margin
        if curr_gross_margin is not None and prior_gross_margin is not None
        else None,
    )

    curr_asset_turnover = asset_turnover(current.get("revenue"), current.get("total_assets"))
    prior_asset_turnover = asset_turnover(prior.get("revenue"), prior.get("total_assets"))
    _test(
        "Asset turnover improved",
        curr_asset_turnover > prior_asset_turnover
        if curr_asset_turnover is not None and prior_asset_turnover is not None
        else None,
    )

    return {"earned": earned, "possible": possible, "tests": tests}

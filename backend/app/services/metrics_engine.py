"""Assembles a flat metric-name -> value dict for one symbol, by fetching
its quote + financials and feeding them through the pure functions in
`app.metrics.ratios`. This is the one place that bridges I/O (routers,
data source, cache) and the pure metrics layer.

Growth/CAGR figures are computed only from `comparable_periods` (PLAN.md
"Phase 1.5 review" item 2) -- TMPV's pre-demerger years and JIOFIN's FY23
shell year never enter a CAGR or feed the health-radar score.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.metrics import ratios as r
from app.metrics.basis_consistency import equity_basis_oscillation_detected
from app.metrics.comparability import comparable_periods
from app.metrics.plausibility import book_value_per_share_is_plausible, pe_is_plausible
from app.metrics.units import Crore, Shares, per_share_value
from app.services.datasource import get_data_source
from app.services.universe import get_company

_TTM_DIVIDEND_WINDOW_DAYS = 365

# Method provenance values (PLAN.md "Phase 3 review" / Phase 2.2 item 3).
# "computed": our own fundamentals-timeseries-derived calculation succeeded
# -- the common case, and the ONLY one a history/trend chart can be built
# from consistently. "yahoo_fallback": our own calculation returned None
# (e.g. too few periods), so Yahoo's crumb-gated key-statistics figure
# filled in -- a single-point snapshot, not something a trend chart can
# replicate, so it's tagged distinctly rather than presented as equivalent.
# "unavailable": neither worked.
METHOD_COMPUTED = "computed"
METHOD_YAHOO_FALLBACK = "yahoo_fallback"
METHOD_UNAVAILABLE = "unavailable"


def _prefer_own(
    key: str, own_value: float | None, fallback_value: float | None, method: dict[str, str]
) -> float | None:
    """Use `own_value` when available; only reach for `fallback_value` (and
    tag it as such) when our own calculation came back None. Never silently
    prefer the fallback over a value we were able to compute ourselves --
    that's exactly the "KPI card says 13.8%, its trend chart says 9%"
    inconsistency Phase 2.2 exists to close."""
    if own_value is not None:
        method[key] = METHOD_COMPUTED
        return own_value
    if fallback_value is not None:
        method[key] = METHOD_YAHOO_FALLBACK
        return fallback_value
    method[key] = METHOD_UNAVAILABLE
    return None


def _years_between(start_iso: str, end_iso: str) -> float:
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    return (end - start).days / 365.25


def _ttm_sum(quarterly_periods: list[dict], key: str) -> float | None:
    """Sum of `key` across the last 4 comparable quarters, or None if fewer
    than 4 are available (Yahoo gives ~5-6 quarters -- see PLAN.md "Phase 1
    review" item 4 -- so this is usually satisfiable, but not always: our
    own HDFCBANK spot-check only had 3)."""
    if len(quarterly_periods) < 4:
        return None
    last_four = quarterly_periods[-4:]
    values = [p["line_items"].get(key) for p in last_four]
    if any(v is None for v in values):
        return None
    return sum(values)


async def _ttm_dividend_per_share(yf_ticker: str) -> float | None:
    data_source = get_data_source()
    try:
        dividends = await data_source.get_dividends(yf_ticker)
    except Exception:  # noqa: BLE001
        return None
    if not dividends:
        return None
    cutoff = datetime.now(timezone.utc).date().toordinal() - _TTM_DIVIDEND_WINDOW_DAYS
    total = sum(
        d["amount"] for d in dividends if date.fromisoformat(d["date"]).toordinal() >= cutoff
    )
    return total if total > 0 else None


async def compute_symbol_metrics(symbol: str) -> dict[str, Any]:
    """Returns a dict with:
    - `company`: the CompanyRef
    - `metrics`: flat metric-key -> float|None
    - `warnings`: list[str]
    - `growth_note`: str|None (which years a CAGR/growth figure excludes, if any)
    - `comparable_annual_years`: int (span used for the *_cagr_3y metrics -- may not be 3)
    """
    from app.routers.financials import get_financials
    from app.routers.quote import get_quote

    company = get_company(symbol)
    if company is None:
        return {"company": None, "metrics": {}, "warnings": [f"Unknown symbol: {symbol}"]}

    warnings: list[str] = []
    cross_check_divergences: list[dict[str, Any]] = []
    data_source = get_data_source()

    quote = await get_quote(symbol)
    warnings.extend(quote.warnings)

    # Yahoo's own already-computed ROE/ROA/book-value/EPS (PLAN.md "Phase 2
    # review"): our own fundamentals-timeseries-derived book value for
    # HDFCBANK diverged 36% from Screener.in; this crumb-gated cross-check
    # turned out to be the actual fix (see fetch_key_statistics's
    # docstring for the full investigation). Used to override our own
    # calculation when available, and to flag >10% divergences either way
    # (item 4) -- never silently trusted without a fallback, since the
    # crumb is issued inconsistently.
    key_stats = await data_source.get_key_statistics(company.yf_ticker)

    financials = await get_financials(symbol, period="annual")
    warnings.extend(financials.warnings)

    income_raw = [p.model_dump() for p in financials.income_statement]
    balance_raw = [p.model_dump() for p in financials.balance_sheet]
    cashflow_raw = [p.model_dump() for p in financials.cash_flow]

    income_periods, growth_note = comparable_periods(symbol, income_raw)
    balance_periods, _ = comparable_periods(symbol, balance_raw)
    cashflow_periods, _ = comparable_periods(symbol, cashflow_raw)
    if growth_note:
        warnings.append(growth_note)

    # Trailing-twelve-month earnings figures (PLAN.md "Phase 1 review" item
    # 4: "trailing multiples use the last 4 quarters"). A Screener.in
    # spot-check (Phase 2 review) showed our ROE/ROCE/P/E running ~5-13%
    # off theirs specifically because we were using the latest ANNUAL
    # figure instead of TTM -- this closes that gap. Falls back to the
    # latest annual figure (with a warning) when fewer than 4 comparable
    # quarters are available.
    try:
        quarterly_financials = await get_financials(symbol, period="quarterly")
        quarterly_income_raw = [p.model_dump() for p in quarterly_financials.income_statement]
        quarterly_income_periods, _ = comparable_periods(symbol, quarterly_income_raw)
        quarterly_equity = [
            p.line_items.get("total_equity") for p in quarterly_financials.balance_sheet
        ]
    except Exception as exc:  # noqa: BLE001
        quarterly_income_periods = []
        quarterly_equity = []
        warnings.append(f"Quarterly income statement fetch failed (TTM unavailable): {exc}")

    metrics: dict[str, float | None] = {}
    method: dict[str, str] = {}
    # Metric key -> human-readable reason, for a metric whose own-calculated
    # value is real (non-None) but built on data we've positively detected
    # as unreliable -- surfaced as an amber "source data inconsistent" badge
    # rather than presented as a clean number (PLAN.md "Phase 4.1 review"
    # item 1). Distinct from `method`: a badged metric can still be
    # "computed", just computed from data flagged as shaky.
    data_quality: dict[str, str] = {}
    comparable_annual_years = 0

    if not income_periods:
        return {
            "company": company,
            "quote": quote,
            "metrics": metrics,
            "method": method,
            "data_quality": data_quality,
            "latest_income": {},
            "latest_balance": {},
            "latest_cashflow": {},
            "warnings": warnings + ["No comparable annual periods available"],
            "growth_note": growth_note,
            "comparable_annual_years": 0,
            "cross_check_divergences": cross_check_divergences,
        }

    latest_income = income_periods[-1]["line_items"]
    prior_income = income_periods[-2]["line_items"] if len(income_periods) >= 2 else {}
    earliest_income = income_periods[0]["line_items"]
    comparable_annual_years = max(
        len(income_periods) - 1,
        0,
    )

    latest_balance = balance_periods[-1]["line_items"] if balance_periods else {}
    prior_balance = balance_periods[-2]["line_items"] if len(balance_periods) >= 2 else {}
    latest_cashflow = cashflow_periods[-1]["line_items"] if cashflow_periods else {}

    avg_equity = r.average_of(latest_balance.get("total_equity"), prior_balance.get("total_equity"))
    avg_assets = r.average_of(latest_balance.get("total_assets"), prior_balance.get("total_assets"))

    ttm_net_income = _ttm_sum(quarterly_income_periods, "net_income")
    ttm_ebit = _ttm_sum(quarterly_income_periods, "ebit")
    ttm_eps_diluted = _ttm_sum(quarterly_income_periods, "eps_diluted")
    if ttm_net_income is None:
        ttm_net_income = latest_income.get("net_income")
        warnings.append("TTM net income unavailable (<4 comparable quarters) -- used latest annual instead")
    if ttm_ebit is None:
        ttm_ebit = latest_income.get("ebit")
    if ttm_eps_diluted is None:
        ttm_eps_diluted = latest_income.get("eps_diluted") or latest_income.get("eps_basic")

    # --- Growth -----------------------------------------------------------
    metrics["revenue_growth"] = r.yoy_growth(latest_income.get("revenue"), prior_income.get("revenue"))
    metrics["ebitda_growth"] = r.yoy_growth(latest_income.get("ebitda"), prior_income.get("ebitda"))
    metrics["pat_growth"] = r.yoy_growth(latest_income.get("net_income"), prior_income.get("net_income"))
    metrics["nii_growth"] = r.yoy_growth(
        latest_income.get("net_interest_income"), prior_income.get("net_interest_income")
    )
    metrics["premium_growth"] = r.yoy_growth(
        latest_income.get("premiums_earned"), prior_income.get("premiums_earned")
    )
    years_span = (
        _years_between(income_periods[0]["period_end"], income_periods[-1]["period_end"])
        if len(income_periods) >= 2
        else None
    )
    metrics["revenue_cagr_3y"] = r.cagr(
        earliest_income.get("revenue"), latest_income.get("revenue"), years_span
    )
    metrics["pat_cagr_3y"] = r.cagr(
        earliest_income.get("net_income"), latest_income.get("net_income"), years_span
    )

    # --- Margins ------------------------------------------------------------
    metrics["gross_margin"] = r.margin(latest_income.get("gross_profit"), latest_income.get("revenue"))
    metrics["ebitda_margin"] = r.margin(latest_income.get("ebitda"), latest_income.get("revenue"))
    metrics["ebit_margin"] = r.margin(latest_income.get("ebit"), latest_income.get("revenue"))
    metrics["pat_margin"] = r.margin(latest_income.get("net_income"), latest_income.get("revenue"))

    # --- Returns (TTM earnings over the latest annual balance sheet -- our
    # own calculation is authoritative whenever it succeeds, so a KPI card
    # and an ROE-over-time chart are guaranteed to agree at the latest
    # point: they're the same function, just over different periods. Yahoo's
    # key-statistics ROE/ROA is a fallback for when ours is None, tagged as
    # such, and always checked for a >10% divergence either way -- see
    # PLAN.md "Phase 3 review" / docs/data-notes.md for why HDFCBANK's own
    # figure legitimately differs from Screener's rather than being a bug.
    # A symbol whose quarterly equity oscillates between reporting bases
    # (PLAN.md "Phase 4.1 review" item 1 -- see docs/data-notes.md for
    # HDFCBANK's writeup) can't safely use TTM net income (summed from
    # quarters that may themselves span both bases) over an annual average
    # equity: numerator and denominator can end up measured on different
    # bases even though each individually looks clean. For a flagged
    # symbol, fall back to annual net income -- same filing, same basis as
    # the annual equity already used for avg_equity/avg_assets -- and flag
    # the result as data-quality-inconsistent rather than presenting it as
    # a normal "computed" figure, since even the basis-matched number may
    # still not be trustworthy (the underlying source data disagreement is
    # the real problem, not just which periods get averaged).
    basis_oscillating = equity_basis_oscillation_detected(quarterly_equity)
    net_income_for_returns = ttm_net_income
    if basis_oscillating:
        net_income_for_returns = latest_income.get("net_income")
        reason = (
            "Quarterly equity shows a basis-switching pattern (alternating figures "
            "inconsistent with organic growth) -- ROE/ROA computed from annual, "
            "same-basis net income instead of TTM-summed-quarterly. See "
            "backend/docs/data-notes.md."
        )
        warnings.append(reason)
        data_quality["roe"] = reason
        data_quality["roa"] = reason

    own_roe = r.return_on_equity(net_income_for_returns, avg_equity)
    own_roa = r.return_on_assets(net_income_for_returns, avg_assets)
    metrics["roe"] = _prefer_own("roe", own_roe, key_stats["roe_pct"], method)
    metrics["roa"] = _prefer_own("roa", own_roa, key_stats["roa_pct"], method)

    roe_divergence = r.relative_divergence(own_roe, key_stats["roe_pct"])
    if roe_divergence is not None and roe_divergence > 10:
        cross_check_divergences.append(
            {"metric": "roe", "ours": own_roe, "yahoo": key_stats["roe_pct"], "divergence_pct": roe_divergence}
        )

    cap_employed = r.capital_employed(latest_balance.get("total_assets"), latest_balance.get("current_liabilities"))
    metrics["roce"] = r.return_on_capital_employed(ttm_ebit, cap_employed)
    tax_rate = r.effective_tax_rate(latest_income.get("tax"), latest_income.get("pretax_income"))
    inv_capital = r.invested_capital(
        latest_balance.get("total_debt"), latest_balance.get("total_equity"), latest_balance.get("cash_and_equivalents")
    )
    metrics["roic"] = r.return_on_invested_capital(ttm_ebit, tax_rate, inv_capital)

    dupont = r.dupont_decomposition(
        latest_income.get("net_income"), latest_income.get("revenue"), avg_assets, avg_equity
    )
    metrics["dupont_net_margin_pct"] = dupont["net_margin_pct"]
    metrics["dupont_asset_turnover"] = dupont["asset_turnover"]
    metrics["dupont_equity_multiplier"] = dupont["equity_multiplier"]
    metrics["dupont_roe_check_pct"] = dupont["roe_check_pct"]

    # --- Leverage ---------------------------------------------------------
    metrics["debt_to_equity"] = r.debt_to_equity(latest_balance.get("total_debt"), latest_balance.get("total_equity"))
    metrics["net_debt_to_ebitda"] = r.net_debt_to_ebitda(
        latest_balance.get("total_debt"), latest_balance.get("cash_and_equivalents"), latest_income.get("ebitda")
    )
    metrics["interest_coverage"] = r.interest_coverage(latest_income.get("ebit"), latest_income.get("interest_expense"))
    metrics["debt_to_assets"] = r.debt_to_assets(latest_balance.get("total_debt"), latest_balance.get("total_assets"))

    # --- Liquidity ----------------------------------------------------------
    metrics["current_ratio"] = r.current_ratio(latest_balance.get("current_assets"), latest_balance.get("current_liabilities"))
    metrics["quick_ratio"] = r.quick_ratio(
        latest_balance.get("current_assets"), latest_balance.get("inventory"), latest_balance.get("current_liabilities")
    )
    metrics["cash_ratio"] = r.cash_ratio(latest_balance.get("cash_and_equivalents"), latest_balance.get("current_liabilities"))

    # --- Efficiency -----------------------------------------------------
    metrics["asset_turnover"] = r.asset_turnover(latest_income.get("revenue"), avg_assets)
    debtor_days = r.debtor_days(latest_balance.get("receivables"), latest_income.get("revenue"))
    inventory_days = r.inventory_days(latest_balance.get("inventory"), latest_income.get("cogs"))
    payable_days = r.payable_days(latest_balance.get("payables"), latest_income.get("cogs"))
    metrics["debtor_days"] = debtor_days
    metrics["inventory_days"] = inventory_days
    metrics["payable_days"] = payable_days
    metrics["cash_conversion_cycle"] = r.cash_conversion_cycle(debtor_days, inventory_days, payable_days)

    # --- Cash flow --------------------------------------------------------
    fcf = r.free_cash_flow(
        latest_cashflow.get("cfo"), latest_cashflow.get("capex"), latest_cashflow.get("free_cash_flow")
    )
    metrics["fcf"] = fcf
    metrics["fcf_margin"] = r.fcf_margin(fcf, latest_income.get("revenue"))
    metrics["cfo_to_pat"] = r.cfo_to_pat(latest_cashflow.get("cfo"), latest_income.get("net_income"))
    metrics["capex_intensity"] = r.capex_intensity(latest_cashflow.get("capex"), latest_income.get("revenue"))

    # --- Valuation (needs live price/market cap from the quote; trailing
    # multiples use TTM EPS, per PLAN.md "Phase 1 review" item 4; our own
    # book value and EPS are authoritative, with Yahoo's cross-check only
    # as a fallback when ours is None -- same reasoning as ROE/ROA above) --
    price = quote.last_price
    market_cap = quote.market_cap

    # total_equity is Crore (this app's internal currency convention);
    # shares_outstanding is a raw Shares count. per_share_value is the ONE
    # place this conversion happens -- see metrics/units.py's docstring for
    # the ~1e7x bug that ad-hoc `* CRORE` call sites caused before it existed.
    own_book_value_per_share = (
        per_share_value(
            Crore(latest_balance["total_equity"]), Shares(latest_balance["shares_outstanding"])
        )
        if latest_balance.get("total_equity") is not None
        and latest_balance.get("shares_outstanding") is not None
        else None
    )
    bvps_divergence = r.relative_divergence(own_book_value_per_share, key_stats["book_value_per_share"])
    if bvps_divergence is not None and bvps_divergence > 10:
        cross_check_divergences.append(
            {
                "metric": "book_value_per_share",
                "ours": own_book_value_per_share,
                "yahoo": key_stats["book_value_per_share"],
                "divergence_pct": bvps_divergence,
            }
        )
    # A plausibility gate, not just a None check: our own calculation can
    # come back a real (non-None) number that's still nonsensical -- either
    # because the underlying Yahoo data is unit-inconsistent for this
    # symbol (INFY: see docs/data-notes.md) or because summing 4 volatile
    # quarterly EPS values can net out near zero even when each quarter's
    # figure is individually correct (INDIGO: +56, +14, -66, -6 sums to
    # -1.33, implying a P/E in the thousands). Either way, an implausible
    # own-value is treated the same as a missing one -- fall back to
    # Yahoo, or `None`, rather than display it.
    if not book_value_per_share_is_plausible(own_book_value_per_share):
        own_book_value_per_share = None
    book_value_per_share = _prefer_own(
        "pb", own_book_value_per_share, key_stats["book_value_per_share"], method
    )

    eps_divergence = r.relative_divergence(ttm_eps_diluted, key_stats["trailing_eps"])
    if eps_divergence is not None and eps_divergence > 10:
        cross_check_divergences.append(
            {
                "metric": "eps",
                "ours": ttm_eps_diluted,
                "yahoo": key_stats["trailing_eps"],
                "divergence_pct": eps_divergence,
            }
        )
    own_eps_for_display = ttm_eps_diluted
    if not pe_is_plausible(r.price_to_earnings(price, ttm_eps_diluted)):
        own_eps_for_display = None
    eps_final = _prefer_own("pe", own_eps_for_display, key_stats["trailing_eps"], method)
    # earnings_yield/peg/payout_ratio derive from the same eps_final, so
    # they share pe's provenance rather than being tagged independently.
    method["earnings_yield"] = method["pe"]
    method["peg"] = method["pe"]

    metrics["pe"] = r.price_to_earnings(price, eps_final)
    metrics["pb"] = r.price_to_per_share_value(price, book_value_per_share)
    ev = r.enterprise_value(
        market_cap,
        latest_balance.get("total_debt"),
        latest_balance.get("cash_and_equivalents"),
        latest_balance.get("minority_interest"),
    )
    metrics["ev_ebitda"] = r.ev_to_ebitda(ev, latest_income.get("ebitda"))
    metrics["ev_sales"] = r.ev_to_sales(ev, latest_income.get("revenue"))
    metrics["earnings_yield"] = r.earnings_yield(eps_final, price)
    metrics["peg"] = r.peg_ratio(metrics["pe"], metrics["pat_growth"])

    dividend_per_share = await _ttm_dividend_per_share(company.yf_ticker)
    metrics["dividend_yield"] = r.dividend_yield(dividend_per_share, price)
    metrics["payout_ratio"] = r.payout_ratio(dividend_per_share, eps_final)
    method["payout_ratio"] = method["pe"]

    # --- Bank / NBFC / insurance derived ------------------------------------
    metrics["nim"] = r.net_interest_margin(latest_income.get("net_interest_income"), avg_assets)
    metrics["cost_to_income"] = r.cost_to_income(
        latest_income.get("non_interest_expense"),
        latest_income.get("net_interest_income"),
        latest_income.get("non_interest_income"),
    )

    # --- Quality flags (non-financial templates only, per PLAN.md §2) -----
    if company.template in ("general", "exchange"):
        working_capital = None
        if latest_balance.get("current_assets") is not None and latest_balance.get("current_liabilities") is not None:
            working_capital = latest_balance["current_assets"] - latest_balance["current_liabilities"]
        metrics["altman_z_score"] = r.altman_z_score(
            working_capital,
            latest_balance.get("retained_earnings"),
            latest_income.get("ebit"),
            market_cap,
            latest_balance.get("total_liabilities"),
            latest_income.get("revenue"),
            latest_balance.get("total_assets"),
        )

        if len(income_periods) >= 2 and len(balance_periods) >= 2:
            curr = {
                "net_income": latest_income.get("net_income"),
                "total_assets": latest_balance.get("total_assets"),
                "cfo": latest_cashflow.get("cfo"),
                "total_debt": latest_balance.get("total_debt"),
                "current_assets": latest_balance.get("current_assets"),
                "current_liabilities": latest_balance.get("current_liabilities"),
                "shares_outstanding": latest_balance.get("shares_outstanding"),
                "gross_profit": latest_income.get("gross_profit"),
                "revenue": latest_income.get("revenue"),
            }
            prior_cashflow = cashflow_periods[-2]["line_items"] if len(cashflow_periods) >= 2 else {}
            prior = {
                "net_income": prior_income.get("net_income"),
                "total_assets": prior_balance.get("total_assets"),
                "cfo": prior_cashflow.get("cfo"),
                "total_debt": prior_balance.get("total_debt"),
                "current_assets": prior_balance.get("current_assets"),
                "current_liabilities": prior_balance.get("current_liabilities"),
                "shares_outstanding": prior_balance.get("shares_outstanding"),
                "gross_profit": prior_income.get("gross_profit"),
                "revenue": prior_income.get("revenue"),
            }
            earned, possible = r.piotroski_f_score(curr, prior)
            metrics["piotroski_f_score"] = float(earned)
            metrics["piotroski_f_score_possible"] = float(possible)

    for divergence in cross_check_divergences:
        warnings.append(
            "{metric}: our figure ({ours:.2f}) diverges {divergence_pct:.1f}% from "
            "Yahoo's own key statistics ({yahoo:.2f})".format(**divergence)
        )

    # Every metric not already explicitly tagged above (roe/roa/pb/pe and
    # its derivatives, which can fall back to Yahoo) was computed purely
    # from our own data -- "computed" if it has a value, "unavailable" if
    # the inputs it needed were missing.
    for key, value in metrics.items():
        if key not in method:
            method[key] = METHOD_COMPUTED if value is not None else METHOD_UNAVAILABLE

    return {
        "company": company,
        "quote": quote,
        "metrics": metrics,
        "method": method,
        "data_quality": data_quality,
        "latest_income": latest_income,
        "latest_balance": latest_balance,
        "latest_cashflow": latest_cashflow,
        "warnings": warnings,
        "growth_note": growth_note,
        "comparable_annual_years": comparable_annual_years,
        "cross_check_divergences": cross_check_divergences,
    }

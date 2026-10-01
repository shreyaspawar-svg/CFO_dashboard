"""Assembles the 20-KPI CFO scorecard (RIL single-company pivot, PLAN.md
"RIL KPI scorecard") from quarterly financials, with a quarter-over-
quarter comparison for every KPI that's actually computable from free
data. Mirrors `app.services.metrics_engine`'s bridge-between-I/O-and-
pure-functions shape, but quarter-indexed instead of annual-indexed --
kept as a separate module rather than extending metrics_engine.py since
the TTM-window and QoQ-delta concerns here are genuinely different from
that module's annual KPI-card + fiscal-year-history shape.

Two free-data-source realities this module has to work around (both
confirmed live for RELIANCE.NS, not assumed):

1. The three quarterly statements don't share reporting dates. Income
   statement quarters are the most complete (RIL: 5 of the last ~6
   quarters), balance sheet quarters are sparser (RIL: only 3, skipping
   some quarters entirely) and cash flow is sometimes not reported
   quarterly AT ALL (RIL: zero quarterly cash-flow periods from Yahoo's
   fundamentals-timeseries, despite annual cash flow being fully
   available). An exact-date inner join across all three (what
   `metrics_engine._align_periods_by_end` does for TTM sums) would
   produce zero usable periods here. Income statement is used as the
   spine instead; balance-sheet figures are attached via a step lookup
   (the latest balance-sheet snapshot at or before each income period's
   date -- same "step, never interpolate" principle as the P/E-band's
   `_step_lookup` in `app.metrics.valuation_bands`), and cash-flow-
   dependent KPIs fall back to the latest two ANNUAL cash-flow periods
   (YoY, not QoQ, and labelled as such) whenever quarterly cash flow
   isn't reported at all.

2. ROCE, Net Debt/EBITDA, and the three working-capital-days ratios all
   divide a balance-sheet balance (a stock) by an income-statement flow.
   Feeding them a single quarter's flow would make them look ~4x off
   from the annual figures shown elsewhere in this app (e.g. the Ratios
   tab's ROCE) -- so this sums the trailing 4 quarters ending at a given
   income period (a rolling TTM window) for those denominators, both for
   the latest quarter and the one before it, so the comparison is
   apples-to-apples (TTM-ending-this-quarter vs TTM-ending-last-quarter).
   This needs 5 income quarters; when fewer are available the KPI still
   reports its current value with `qoq_delta=None`, never a fabricated
   comparison.

Five of the 20 KPIs the CFO asked for (Capacity Utilisation, Manufacturing
Cost per Unit, Overall Equipment Effectiveness, Internal Audit &
Compliance Issues, and the Safety/ESG/Cybersecurity dashboard) describe
internal operational, audit, and ESG-incident data that no public
financial statement reports -- these are returned as `method:
"unavailable"` with an explicit reason, never a fabricated number."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.metrics import kpi_scorecard as kpi
from app.metrics import ratios as r
from app.metrics.comparability import comparable_periods
from app.routers.financials import get_financials
from app.services.universe import get_company

_TTM_QUARTERS = 4


def _step_align(
    income_periods: list[dict], balance_periods: list[dict], cashflow_periods: list[dict]
) -> list[dict[str, Any]]:
    """Income statement is the spine (best quarterly coverage of the
    three); balance sheet and cash flow are attached via a step lookup
    (latest period at or before the income period's date) rather than an
    exact-date match, since the three statements don't share reporting
    dates for every symbol (see module docstring). A period's `balance`/
    `cashflow` dict is `{}` (not an error) when no statement period exists
    on or before that date yet."""
    balance_sorted = sorted(balance_periods, key=lambda p: p["period_end"])
    cashflow_sorted = sorted(cashflow_periods, key=lambda p: p["period_end"])

    def _latest_at_or_before(periods: list[dict], as_of: str) -> dict | None:
        candidate: dict | None = None
        for p in periods:
            if p["period_end"] > as_of:
                break
            candidate = p
        return candidate

    aligned = []
    for inc in sorted(income_periods, key=lambda p: p["period_end"]):
        balance_match = _latest_at_or_before(balance_sorted, inc["period_end"])
        cashflow_match = _latest_at_or_before(cashflow_sorted, inc["period_end"])
        aligned.append(
            {
                "period_end": inc["period_end"],
                "fiscal_year": inc["fiscal_year"],
                "income": inc["line_items"],
                "balance": balance_match["line_items"] if balance_match else {},
                "balance_as_of": balance_match["period_end"] if balance_match else None,
                "cashflow": cashflow_match["line_items"] if cashflow_match else {},
            }
        )
    return aligned


def _ttm_sum_at(aligned: list[dict], statement: str, key: str, end_index: int) -> float | None:
    """Sum of `key` over the 4 quarters ending at `end_index` (inclusive),
    or None if that window runs off the start of the list or any quarter
    in it is missing the field."""
    start = end_index - _TTM_QUARTERS + 1
    if start < 0:
        return None
    window = aligned[start : end_index + 1]
    values = [p[statement].get(key) for p in window]
    if any(v is None for v in values):
        return None
    return sum(values)


def _entry(
    key: str,
    label: str,
    unit: str,
    value: float | None,
    prior_value: float | None,
    *,
    method: str = "computed",
    reason: str | None = None,
    driver_note: str | None = None,
    is_margin: bool = False,
) -> dict[str, Any]:
    qoq_delta = None
    qoq_delta_pct = None
    if value is not None and prior_value is not None:
        qoq_delta = value - prior_value
        if not is_margin and prior_value != 0:
            qoq_delta_pct = (value - prior_value) / abs(prior_value) * 100
    if value is None and method == "computed":
        method = "unavailable"
        reason = reason or "Not enough quarterly history from this free data source to compute this."
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "value": value,
        "prior_value": prior_value,
        "qoq_delta": qoq_delta,
        "qoq_delta_pct": qoq_delta_pct,
        "method": method,
        "reason": reason,
        "driver_note": driver_note,
    }


_UNAVAILABLE_OPERATIONAL = (
    "Not available from free financial-data sources -- requires internal "
    "plant-level operations data (production volumes, installed capacity, "
    "machine uptime logs), not public financial statements."
)
_UNAVAILABLE_GOVERNANCE = (
    "Not available from free financial-data sources -- requires internal "
    "audit/compliance tracking systems and ESG/safety incident reporting, "
    "not public financial statements."
)
_ANNUAL_CASHFLOW_FALLBACK_REASON = (
    "Yahoo does not report this symbol's cash-flow statement on a "
    "quarterly basis -- showing year-over-year change between the latest "
    "two annual periods instead of quarter-over-quarter."
)

# `ratios.growth_reason` returns a terse code meant for a "n.m." vs "—"
# display distinction (see its docstring); this scorecard shows a full
# reason sentence instead, so the code is translated here rather than
# surfaced raw.
_GROWTH_REASON_TEXT = {
    "missing": "Insufficient quarterly revenue data from this free source.",
    "not_meaningful": "Not meaningful: the prior quarter's revenue was zero or negative.",
}


async def compute_kpi_scorecard(symbol: str) -> dict[str, Any]:
    company = get_company(symbol)
    warnings: list[str] = []

    quarterly = await get_financials(symbol, period="quarterly")
    warnings.extend(quarterly.warnings)
    annual = await get_financials(symbol, period="annual")

    income_periods, _ = comparable_periods(symbol, [p.model_dump() for p in quarterly.income_statement])
    balance_periods, _ = comparable_periods(symbol, [p.model_dump() for p in quarterly.balance_sheet])
    cashflow_periods, _ = comparable_periods(symbol, [p.model_dump() for p in quarterly.cash_flow])
    annual_income_periods, _ = comparable_periods(symbol, [p.model_dump() for p in annual.income_statement])
    annual_cashflow_periods, _ = comparable_periods(symbol, [p.model_dump() for p in annual.cash_flow])

    aligned = _step_align(income_periods, balance_periods, cashflow_periods)

    n = len(aligned)
    if n < 2:
        warnings.append(
            f"Only {n} comparable income-statement quarter(s) available -- quarter-over-quarter comparisons need at least 2."
        )

    cur = aligned[-1] if n >= 1 else None
    prev = aligned[-2] if n >= 2 else None

    # When the two income quarters step-looked-up to the SAME balance-sheet
    # snapshot (no new quarterly balance sheet reported between them -- see
    # module docstring, point 1), a pure balance-sheet KPI's "QoQ" delta
    # would otherwise show a flat 0, which reads as "unchanged" rather than
    # "we don't have a newer number yet". Flagged explicitly instead.
    same_balance_snapshot = (
        cur is not None
        and prev is not None
        and cur["balance_as_of"] is not None
        and cur["balance_as_of"] == prev["balance_as_of"]
    )
    stale_balance_note = (
        f"Based on the same balance sheet (as of {cur['balance_as_of']}) as the prior quarter -- "
        "no newer quarterly balance sheet has been reported yet by this free source."
        if same_balance_snapshot
        else None
    )

    def _with_stale_note(note: str | None) -> str | None:
        if not same_balance_snapshot:
            return note
        return f"{note} {stale_balance_note}" if note else stale_balance_note

    quarter_label = f"{cur['fiscal_year']} (quarter ended {cur['period_end']})" if cur else None
    prior_quarter_label = f"{prev['fiscal_year']} (quarter ended {prev['period_end']})" if prev else None

    annual_cf_cur = annual_cashflow_periods[-1]["line_items"] if annual_cashflow_periods else {}
    annual_cf_prev = annual_cashflow_periods[-2]["line_items"] if len(annual_cashflow_periods) >= 2 else {}
    annual_inc_cur = annual_income_periods[-1]["line_items"] if annual_income_periods else {}
    annual_inc_prev = annual_income_periods[-2]["line_items"] if len(annual_income_periods) >= 2 else {}

    def inc(p: dict | None, field: str) -> float | None:
        return p["income"].get(field) if p else None

    def bal(p: dict | None, field: str) -> float | None:
        return p["balance"].get(field) if p else None

    def cf_with_annual_fallback(field: str) -> tuple[float | None, float | None, bool]:
        """(current, prior, used_annual_fallback). Quarterly cash flow is
        used only when BOTH quarters have it -- never mix a quarterly
        current value with an annual prior value, which would compare two
        different-length periods as if they were the same kind of delta."""
        q_cur = cur["cashflow"].get(field) if cur else None
        q_prev = prev["cashflow"].get(field) if prev else None
        if q_cur is not None and q_prev is not None:
            return q_cur, q_prev, False
        return annual_cf_cur.get(field), annual_cf_prev.get(field), True

    # TTM income-statement windows ending at the latest quarter and the one
    # before it -- None when there isn't a full 4-quarter window at that
    # index (see module docstring, point 2).
    cur_idx = n - 1 if n >= 1 else None
    prev_idx = n - 2 if n >= 2 else None

    def ttm(field: str, end_index: int | None) -> float | None:
        if end_index is None or end_index < 0:
            return None
        return _ttm_sum_at(aligned, "income", field, end_index)

    ttm_revenue_cur, ttm_revenue_prev = ttm("revenue", cur_idx), ttm("revenue", prev_idx)
    ttm_cogs_cur, ttm_cogs_prev = ttm("cogs", cur_idx), ttm("cogs", prev_idx)
    ttm_ebit_cur, ttm_ebit_prev = ttm("ebit", cur_idx), ttm("ebit", prev_idx)
    ttm_ebitda_cur, ttm_ebitda_prev = ttm("ebitda", cur_idx), ttm("ebitda", prev_idx)

    groups: list[dict[str, Any]] = []

    # --- Financial Performance ------------------------------------------------
    rev_cur, rev_prev = inc(cur, "revenue"), inc(prev, "revenue")
    ebitda_cur, ebitda_prev = inc(cur, "ebitda"), inc(prev, "ebitda")
    pat_cur, pat_prev = inc(cur, "net_income"), inc(prev, "net_income")

    cfo_cur, cfo_prev, cfo_is_annual = cf_with_annual_fallback("cfo")

    ebitda_margin_cur = r.margin(ebitda_cur, rev_cur)
    ebitda_margin_prev = r.margin(ebitda_prev, rev_prev)
    pat_margin_cur = r.margin(pat_cur, rev_cur)
    pat_margin_prev = r.margin(pat_prev, rev_prev)
    # EBITDA-to-cash-conversion mixes a cash-flow figure (possibly annual)
    # with EBITDA -- keep both sides on the same basis as cfo_cur/cfo_prev
    # (the matching annual income statement's EBITDA, not a quarterly TTM
    # figure, which could cover a different window than the annual CFO).
    ebitda_for_conv_cur = annual_inc_cur.get("ebitda") if cfo_is_annual else ebitda_cur
    ebitda_for_conv_prev = annual_inc_prev.get("ebitda") if cfo_is_annual else ebitda_prev
    cash_conv_cur = r.margin(cfo_cur, ebitda_for_conv_cur)
    cash_conv_prev = r.margin(cfo_prev, ebitda_for_conv_prev)

    roce_cur = r.return_on_capital_employed(
        ttm_ebit_cur, r.capital_employed(bal(cur, "total_assets"), bal(cur, "current_liabilities"))
    )
    roce_prev = r.return_on_capital_employed(
        ttm_ebit_prev, r.capital_employed(bal(prev, "total_assets"), bal(prev, "current_liabilities"))
    )

    groups.append(
        {
            "name": "Financial Performance",
            "entries": [
                _entry(
                    "revenue_growth_qoq",
                    "Revenue Growth (QoQ)",
                    "pct",
                    r.yoy_growth(rev_cur, rev_prev),
                    None,
                    reason=_GROWTH_REASON_TEXT.get(r.growth_reason(rev_cur, rev_prev)),
                    driver_note="Quarter-on-quarter change in total revenue.",
                ),
                _entry(
                    "ebitda_margin",
                    "EBITDA Margin",
                    "pct",
                    ebitda_margin_cur,
                    ebitda_margin_prev,
                    is_margin=True,
                    driver_note=(
                        f"EBITDA margin moved from {ebitda_margin_prev:.1f}% to {ebitda_margin_cur:.1f}% "
                        f"as EBITDA changed {r.yoy_growth(ebitda_cur, ebitda_prev):+.1f}% against revenue "
                        f"growth of {r.yoy_growth(rev_cur, rev_prev):+.1f}%."
                        if None not in (ebitda_margin_prev, ebitda_margin_cur, rev_cur, rev_prev)
                        and r.yoy_growth(ebitda_cur, ebitda_prev) is not None
                        and r.yoy_growth(rev_cur, rev_prev) is not None
                        else None
                    ),
                ),
                _entry(
                    "pat_margin",
                    "PAT Margin",
                    "pct",
                    pat_margin_cur,
                    pat_margin_prev,
                    is_margin=True,
                    driver_note=(
                        f"Net profit margin moved from {pat_margin_prev:.1f}% to {pat_margin_cur:.1f}%."
                        if None not in (pat_margin_prev, pat_margin_cur)
                        else None
                    ),
                ),
                _entry(
                    "ebitda_cash_conversion",
                    "EBITDA to Cash Conversion" + (" (Annual)" if cfo_is_annual else ""),
                    "pct",
                    cash_conv_cur,
                    cash_conv_prev,
                    is_margin=True,
                    reason=_ANNUAL_CASHFLOW_FALLBACK_REASON if cfo_is_annual and cash_conv_cur is not None else None,
                    driver_note="Operating cash flow as a share of EBITDA -- a low/falling value can signal working-capital build-up or earnings quality concerns.",
                ),
                _entry(
                    "roce",
                    "Return on Capital Employed (ROCE, TTM)",
                    "pct",
                    roce_cur,
                    roce_prev,
                    is_margin=True,
                    reason="Needs 4 trailing quarters of EBIT; insufficient quarterly history from this free source."
                    if roce_cur is None
                    else None,
                    driver_note=_with_stale_note(
                        "Trailing-twelve-month EBIT / (Total assets - Current liabilities) as of the latest quarter-end."
                    ),
                ),
            ],
        }
    )

    # --- Cash & Liquidity ------------------------------------------------------
    capex_cur, capex_prev, capex_is_annual = cf_with_annual_fallback("capex")
    reported_fcf_cur, reported_fcf_prev, fcf_is_annual = cf_with_annual_fallback("free_cash_flow")
    fcf_cur = r.free_cash_flow(cfo_cur, capex_cur, reported_fcf_cur)
    fcf_prev = r.free_cash_flow(cfo_prev, capex_prev, reported_fcf_prev)
    fcf_is_annual = cfo_is_annual or capex_is_annual or fcf_is_annual

    net_debt_to_ebitda_cur = r.net_debt_to_ebitda(bal(cur, "total_debt"), bal(cur, "cash_and_equivalents"), ttm_ebitda_cur)
    net_debt_to_ebitda_prev = r.net_debt_to_ebitda(bal(prev, "total_debt"), bal(prev, "cash_and_equivalents"), ttm_ebitda_prev)
    cash_cur, cash_prev = bal(cur, "cash_and_equivalents"), bal(prev, "cash_and_equivalents")
    current_ratio_cur = r.current_ratio(bal(cur, "current_assets"), bal(cur, "current_liabilities"))
    # Liquidity runway only makes sense against a QUARTERLY burn rate --
    # the annual-fallback FCF (a full year) can't stand in for one.
    runway_cur = None if fcf_is_annual else kpi.liquidity_runway_months(cash_cur, fcf_cur)

    dso_cur = r.debtor_days(bal(cur, "receivables"), ttm_revenue_cur)
    dso_prev = r.debtor_days(bal(prev, "receivables"), ttm_revenue_prev)
    dio_cur = r.inventory_days(bal(cur, "inventory"), ttm_cogs_cur)
    dio_prev = r.inventory_days(bal(prev, "inventory"), ttm_cogs_prev)
    dpo_cur = r.payable_days(bal(cur, "payables"), ttm_cogs_cur)
    dpo_prev = r.payable_days(bal(prev, "payables"), ttm_cogs_prev)
    ccc_cur = r.cash_conversion_cycle(dso_cur, dio_cur, dpo_cur)
    ccc_prev = r.cash_conversion_cycle(dso_prev, dio_prev, dpo_prev)

    if runway_cur is not None:
        liquidity_note = f"Cash runway at the current quarterly burn rate: {runway_cur:.1f} months."
    elif current_ratio_cur is not None:
        liquidity_note = (
            f"Liquidity shown via current ratio ({current_ratio_cur:.2f}x) rather than a cash-burn runway: "
            "RIL has been free-cash-flow positive, so a burn-rate runway isn't a meaningful figure."
        )
    else:
        liquidity_note = None

    groups.append(
        {
            "name": "Cash & Liquidity",
            "entries": [
                _entry(
                    "operating_cash_flow",
                    "Operating Cash Flow" + (" (Annual)" if cfo_is_annual else ""),
                    "inr_cr",
                    cfo_cur,
                    cfo_prev,
                    reason=_ANNUAL_CASHFLOW_FALLBACK_REASON if cfo_is_annual and cfo_cur is not None else None,
                ),
                _entry(
                    "free_cash_flow",
                    "Free Cash Flow" + (" (Annual)" if fcf_is_annual else ""),
                    "inr_cr",
                    fcf_cur,
                    fcf_prev,
                    reason=_ANNUAL_CASHFLOW_FALLBACK_REASON if fcf_is_annual and fcf_cur is not None else None,
                ),
                _entry(
                    "net_debt_to_ebitda",
                    "Net Debt / EBITDA (TTM)",
                    "x",
                    net_debt_to_ebitda_cur,
                    net_debt_to_ebitda_prev,
                    reason="Needs trailing-twelve-month EBITDA; insufficient quarterly history."
                    if net_debt_to_ebitda_cur is None
                    else None,
                    driver_note=_with_stale_note(None),
                ),
                _entry(
                    "cash_balance",
                    "Cash Balance & Liquidity",
                    "inr_cr",
                    cash_cur,
                    None if same_balance_snapshot else cash_prev,
                    reason=stale_balance_note if same_balance_snapshot else None,
                    driver_note=None if same_balance_snapshot else liquidity_note,
                ),
                _entry(
                    "working_capital_days",
                    "Working Capital Days (CCC, TTM)",
                    "days",
                    ccc_cur,
                    ccc_prev,
                    reason="Needs trailing-twelve-month revenue/COGS; insufficient quarterly history."
                    if ccc_cur is None
                    else None,
                    driver_note=_with_stale_note("Debtor days + inventory days - creditor days."),
                ),
            ],
        }
    )

    # --- Working Capital Efficiency ---------------------------------------------
    groups.append(
        {
            "name": "Working Capital Efficiency",
            "entries": [
                _entry(
                    "debtor_days",
                    "Debtor Days (DSO)",
                    "days",
                    dso_cur,
                    dso_prev,
                    reason="Needs trailing-twelve-month revenue; insufficient quarterly history." if dso_cur is None else None,
                    driver_note=_with_stale_note(None),
                ),
                _entry(
                    "inventory_days",
                    "Inventory Days",
                    "days",
                    dio_cur,
                    dio_prev,
                    reason="Needs trailing-twelve-month COGS; insufficient quarterly history." if dio_cur is None else None,
                    driver_note=_with_stale_note(None),
                ),
                _entry(
                    "creditor_days",
                    "Creditor Days (DPO)",
                    "days",
                    dpo_cur,
                    dpo_prev,
                    reason="Needs trailing-twelve-month COGS; insufficient quarterly history." if dpo_cur is None else None,
                    driver_note=_with_stale_note(None),
                ),
            ],
        }
    )

    # --- Operational Excellence (not derivable from public filings) ------------
    groups.append(
        {
            "name": "Operational Excellence",
            "entries": [
                _entry("capacity_utilisation", "Capacity Utilisation", "pct", None, None, method="unavailable", reason=_UNAVAILABLE_OPERATIONAL),
                _entry("manufacturing_cost_per_unit", "Manufacturing Cost per Unit", "inr", None, None, method="unavailable", reason=_UNAVAILABLE_OPERATIONAL),
                _entry("oee", "Overall Equipment Effectiveness (OEE)", "pct", None, None, method="unavailable", reason=_UNAVAILABLE_OPERATIONAL),
            ],
        }
    )

    # --- Growth & Capital Allocation --------------------------------------------
    # "vs Budget" needs an internal budget figure this free source doesn't
    # have -- actual CAPEX (the public half of that comparison) is shown
    # instead, clearly labelled as such.
    incremental_ebit = (
        ttm_ebit_cur - ttm_ebit_prev if ttm_ebit_cur is not None and ttm_ebit_prev is not None else None
    )
    capex_return = kpi.capex_return_pct(incremental_ebit, capex_prev)

    capex_reason_parts = []
    if capex_is_annual and capex_cur is not None:
        capex_reason_parts.append(_ANNUAL_CASHFLOW_FALLBACK_REASON)
    capex_reason_parts.append(
        "RIL does not publicly disclose a CAPEX budget -- actual CAPEX is shown as the best available public proxy."
    )
    # Displayed as a positive spend amount -- `capex_cur`/`capex_prev` stay
    # in Yahoo's outflow-is-negative convention for the FCF/capex-return
    # maths above, but a board-facing "CAPEX spent" card reads as a
    # magnitude, not a signed cash-flow-statement line.
    capex_display_cur = abs(capex_cur) if capex_cur is not None else None
    capex_display_prev = abs(capex_prev) if capex_prev is not None else None

    groups.append(
        {
            "name": "Growth & Capital Allocation",
            "entries": [
                _entry(
                    "capex_actual",
                    "CAPEX (Actual vs Budget)" + (" (Annual)" if capex_is_annual else ""),
                    "inr_cr",
                    capex_display_cur,
                    capex_display_prev,
                    reason=" ".join(capex_reason_parts),
                ),
                _entry(
                    "capex_return",
                    "Return on Recent CAPEX Investments",
                    "pct",
                    capex_return,
                    None,
                    reason="Approximate: needs trailing-twelve-month EBIT growth and the prior period's CAPEX; insufficient quarterly history from this free source."
                    if capex_return is None
                    else None,
                    driver_note="A heuristic (incremental EBIT / recent CAPEX), not a project-level IRR -- real capital paybacks span multiple years and specific projects.",
                ),
            ],
        }
    )

    # --- Risk, Compliance & Governance (not derivable from public filings) -----
    groups.append(
        {
            "name": "Risk, Compliance & Governance",
            "entries": [
                _entry(
                    "audit_compliance",
                    "Internal Audit & Compliance Issues (Open vs Closed)",
                    "count",
                    None,
                    None,
                    method="unavailable",
                    reason=_UNAVAILABLE_GOVERNANCE,
                ),
                _entry(
                    "safety_esg_cyber",
                    "Safety, ESG & Cybersecurity Dashboard",
                    "text",
                    None,
                    None,
                    method="unavailable",
                    reason=_UNAVAILABLE_GOVERNANCE,
                ),
            ],
        }
    )

    return {
        "symbol": company.symbol,
        "as_of": datetime.now(timezone.utc),
        "source": "yahoo",
        "quarter_label": quarter_label,
        "prior_quarter_label": prior_quarter_label,
        "warnings": warnings,
        "groups": groups,
    }

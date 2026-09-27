from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.schemas import FinancialsResponse
from app.services.cache import get_cache
from app.services.balance_sheet import compute_balance_sheet_detail
from app.services.cash_flow_detail import compute_cash_flow_ratios, compute_cash_flow_sankey
from app.services.corporate_actions import comparable_from, notes_for_symbol
from app.services.datasource import get_data_source
from app.services.normalize import (
    BALANCE_SHEET_MAP,
    CASH_FLOW_MAP,
    INCOME_STATEMENT_MAP,
    missing_fields,
    normalize_balance_sheet,
    normalize_cash_flow,
    normalize_income_statement,
)
from app.services.universe import get_company

FINANCIAL_TEMPLATES = ("bank", "nbfc", "insurance")


def _by_period_end(periods: list[dict]) -> dict[str, dict]:
    return {p["period_end"]: p["line_items"] for p in periods}

router = APIRouter(prefix="/api", tags=["financials"])

# Yahoo typically gives ~4 annual periods and ~5-6 quarters (see PLAN.md
# "Phase 1 review"): the frontend/metrics engine should default to 3-year
# CAGR, a valuation band "over available history" rather than a fixed 5y,
# and trailing multiples from the last 4 quarters -- not assume more
# history exists than Yahoo actually returns.
MIN_EXPECTED_ANNUAL_PERIODS = 4


@router.get("/financials/{symbol}", response_model=FinancialsResponse)
async def get_financials(
    symbol: str,
    period: Literal["annual", "quarterly"] = Query("annual"),
) -> FinancialsResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    cache_key = f"financials:{company.symbol}:{period}"
    cached = cache.get(cache_key)
    if cached is not None:
        return FinancialsResponse(**cached)

    quarterly = period == "quarterly"
    data_source = get_data_source()
    warnings: list[str] = []

    async def _safe_fetch(fn, label: str):
        try:
            return await fn(company.yf_ticker, quarterly=quarterly)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{label} fetch failed: {exc}")
            return []

    income_raw = await _safe_fetch(data_source.get_income_statement, "Income statement")
    balance_raw = await _safe_fetch(data_source.get_balance_sheet, "Balance sheet")
    cashflow_raw = await _safe_fetch(data_source.get_cash_flow, "Cash flow")

    income = normalize_income_statement(income_raw)
    balance = normalize_balance_sheet(balance_raw)
    cashflow = normalize_cash_flow(cashflow_raw)

    for periods, field_map, label in (
        (income, INCOME_STATEMENT_MAP, "Income statement"),
        (balance, BALANCE_SHEET_MAP, "Balance sheet"),
        (cashflow, CASH_FLOW_MAP, "Cash flow"),
    ):
        missing = missing_fields(periods, field_map)
        if missing:
            warnings.append(f"{label} missing fields: {', '.join(sorted(missing))}")

    if not quarterly and len(income) < MIN_EXPECTED_ANNUAL_PERIODS:
        warnings.append(
            f"Only {len(income)} annual income statement period(s) available "
            f"(<{MIN_EXPECTED_ANNUAL_PERIODS})"
        )

    period_ends = [p["period_end"] for p in income]
    notes = notes_for_symbol(company.symbol, period_ends)
    cutoff_date, cutoff_label = comparable_from(company.symbol)

    # --- Balance Sheet tab detail (PLAN.md §4.4) -- pure computation over
    # already-fetched, already-normalized periods, no extra I/O. ------------
    balance_sheet_detail = compute_balance_sheet_detail(balance, company.template)

    # --- Cash Flow tab detail (PLAN.md §4.5) --------------------------------
    income_by_end = _by_period_end(income)
    balance_by_end = _by_period_end(balance)
    cash_flow_detail = []
    for p in cashflow:
        li = p["line_items"]
        inc = income_by_end.get(p["period_end"], {})
        ratios = compute_cash_flow_ratios(
            li.get("cfo"), inc.get("ebitda"), inc.get("net_income"), li.get("free_cash_flow"), inc.get("revenue")
        )
        cash_flow_detail.append(
            {"fiscal_year": p["fiscal_year"], "period_end": p["period_end"], **ratios}
        )

    cash_flow_sankey = None
    if cashflow:
        latest_cf = cashflow[-1]["line_items"]
        latest_end = cashflow[-1]["period_end"]
        latest_bal = balance_by_end.get(latest_end)
        prior_bal = balance[-2]["line_items"] if len(balance) >= 2 else None
        # Prefer the cash flow statement's own EndCashPosition -
        # BeginningCashPosition (reconciles exactly with CFO+CFI+CFF+FX by
        # construction); fall back to the balance-sheet cash delta only if
        # Yahoo doesn't report those fields for this symbol.
        actual_change = None
        if latest_cf.get("end_cash_position") is not None and latest_cf.get("beginning_cash_position") is not None:
            actual_change = latest_cf["end_cash_position"] - latest_cf["beginning_cash_position"]
        elif (
            latest_bal is not None
            and prior_bal is not None
            and latest_bal.get("cash_and_equivalents") is not None
            and prior_bal.get("cash_and_equivalents") is not None
        ):
            actual_change = latest_bal["cash_and_equivalents"] - prior_bal["cash_and_equivalents"]
        cash_flow_sankey = compute_cash_flow_sankey(
            latest_cf.get("cfo"),
            latest_cf.get("cfi"),
            latest_cf.get("cff"),
            actual_change,
            latest_cf.get("fx_effect"),
        )

    response = FinancialsResponse(
        symbol=company.symbol,
        period=period,
        income_statement=income,
        balance_sheet=balance,
        cash_flow=cashflow,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
        notes=notes,
        comparable_from=cutoff_date,
        comparable_from_label=cutoff_label,
        balance_sheet_detail=balance_sheet_detail,
        cash_flow_detail=cash_flow_detail,
        cash_flow_sankey=cash_flow_sankey,
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

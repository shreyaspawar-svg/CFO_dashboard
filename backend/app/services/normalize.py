"""Map raw yfinance line items onto a fixed schema, convert to INR crore,
and label periods with Indian fiscal-year conventions.

Missing fields are always `None` (never 0) so charts can show a visible gap
instead of a fake zero.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

CRORE = 10_000_000  # 1 crore = 1e7

INCOME_STATEMENT_MAP: dict[str, str] = {
    "TotalRevenue": "revenue",
    "CostOfRevenue": "cogs",
    "GrossProfit": "gross_profit",
    "EBITDA": "ebitda",
    "EBIT": "ebit",
    "OperatingIncome": "operating_income",
    "ReconciledDepreciation": "d_and_a",
    "InterestExpense": "interest_expense",
    "TaxProvision": "tax",
    "PretaxIncome": "pretax_income",
    "NetIncome": "net_income",
    "DilutedEPS": "eps_diluted",
    "BasicEPS": "eps_basic",
    # Bank / NBFC / insurance specific (Phase 1.5): confirmed present for
    # HDFCBANK, BAJFINANCE, HDFCLIFE, BSE via a live fundamentals-timeseries
    # check. Always None for non-financial companies, same as ebitda etc.
    # is None for banks -- that's an expected, template-driven gap.
    "InterestIncome": "interest_income",
    "NetInterestIncome": "net_interest_income",
    "NonInterestIncome": "non_interest_income",
    "NonInterestExpense": "non_interest_expense",
    "TotalPremiumsEarned": "premiums_earned",
}

BALANCE_SHEET_MAP: dict[str, str] = {
    "TotalAssets": "total_assets",
    "TotalLiabilitiesNetMinorityInterest": "total_liabilities",
    "StockholdersEquity": "total_equity",
    "CashAndCashEquivalents": "cash_and_equivalents",
    "TotalDebt": "total_debt",
    "CurrentAssets": "current_assets",
    "CurrentLiabilities": "current_liabilities",
    "Inventory": "inventory",
    # Phase 1.5 fix: "Receivables" is not a real fundamentals-timeseries key
    # for any symbol we checked (yfinance's own DataFrame path names this
    # column "Receivables" after building it from "AccountsReceivable", but
    # that's a display rename, not the wire key). Confirmed present under
    # AccountsReceivable for TCS/RELIANCE/MARUTI etc.
    "AccountsReceivable": "receivables",
    "Payables": "payables",
    "NetPPE": "net_ppe",
    # Phase 2: needed for Altman Z-score (non-financial companies only).
    "RetainedEarnings": "retained_earnings",
    # Phase 2.1: enterprise value adds this back (PLAN.md "Phase 2 review"
    # item 1) -- StockholdersEquity already excludes it, so it's tracked
    # separately, not folded into total_equity.
    "MinorityInterest": "minority_interest",
    # Not exposed as a KPI, just carried through for market-cap calculation
    # (price x shares) and future per-share metrics.
    "OrdinarySharesNumber": "shares_outstanding",
}

CASH_FLOW_MAP: dict[str, str] = {
    "OperatingCashFlow": "cfo",
    "InvestingCashFlow": "cfi",
    "FinancingCashFlow": "cff",
    "CapitalExpenditure": "capex",
    "FreeCashFlow": "free_cash_flow",
}

# Fields expressed as a per-share value or a raw count in yfinance's data,
# and thus must NOT be scaled to crore like currency fields are.
_NON_CURRENCY_FIELDS = {"eps_diluted", "eps_basic", "shares_outstanding"}


def clean_numeric(raw: Any) -> float | None:
    """Coerce a raw yfinance/pandas scalar to float, or None if absent/NaN."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    return value


def _to_crore(value: float | None, field: str) -> float | None:
    if value is None or field in _NON_CURRENCY_FIELDS:
        return value
    return value / CRORE


def _fiscal_year_label(period_end: datetime) -> str:
    year = period_end.year
    if period_end.month > 3:
        year += 1
    return f"FY{year % 100:02d}"


def _normalize_statement(
    records: list[dict[str, Any]], field_map: dict[str, str]
) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    for record in records:
        period_end_raw = record.get("index")
        if period_end_raw is None:
            continue
        period_end = (
            period_end_raw
            if isinstance(period_end_raw, datetime)
            else datetime.fromisoformat(str(period_end_raw))
        )
        line_items: dict[str, float | None] = {}
        for yahoo_key, field in field_map.items():
            raw = record.get(yahoo_key)
            value = clean_numeric(raw)
            line_items[field] = _to_crore(value, field)
        periods.append(
            {
                "fiscal_year": _fiscal_year_label(period_end),
                "period_end": period_end.date().isoformat(),
                "line_items": line_items,
            }
        )
    periods.sort(key=lambda p: p["period_end"])
    return periods


def normalize_income_statement(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _normalize_statement(records, INCOME_STATEMENT_MAP)


def normalize_balance_sheet(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _normalize_statement(records, BALANCE_SHEET_MAP)


def normalize_cash_flow(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _normalize_statement(records, CASH_FLOW_MAP)


def missing_fields(periods: list[dict[str, Any]], field_map: dict[str, str]) -> set[str]:
    """Fields from `field_map` that are None in every period (i.e. absent)."""
    expected = set(field_map.values())
    if not periods:
        return expected
    present: set[str] = set()
    for period in periods:
        for field, value in period["line_items"].items():
            if value is not None:
                present.add(field)
    return expected - present

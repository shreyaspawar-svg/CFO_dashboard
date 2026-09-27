"""Template-aware balance-sheet composition, net debt and BVPS -- all
computed server-side (PLAN.md §4.4), from already-normalized balance-sheet
line items. An item this free data source doesn't separately map (e.g. a
bank's deposits/loans split) falls into "Other" by construction -- Other is
defined as the exact residual needed to make each side sum to its reported
total, never omitted or silently absorbed into a mapped bucket.
"""

from __future__ import annotations

from app.metrics.units import Crore, Shares, per_share_value

_FINANCIAL_TEMPLATES = ("bank", "nbfc", "insurance")


def _sum_known(parts: dict[str, float | None]) -> float:
    return sum(v for v in parts.values() if v is not None)


def compute_balance_sheet_period(
    fiscal_year: str, period_end: str, line_items: dict[str, float | None], template: str
) -> dict:
    li = line_items
    total_assets = li.get("total_assets")
    total_liabilities = li.get("total_liabilities")
    total_equity = li.get("total_equity")
    minority_interest = li.get("minority_interest")
    # TotalLiabilitiesNetMinorityInterest + StockholdersEquity leaves out
    # minority interest (it sits in neither Yahoo field) -- add it back so
    # the balance check compares TotalAssets against the FULL right-hand
    # side, matching TotalEquityGrossMinorityInterest's definition.
    total_liab_equity = (
        total_liabilities + total_equity + (minority_interest or 0)
        if total_liabilities is not None and total_equity is not None
        else None
    )

    if template in _FINANCIAL_TEMPLATES:
        assets: dict[str, float | None] = {
            "Cash & equivalents": li.get("cash_and_equivalents"),
            "Investments": li.get("investments"),
            "Loans": li.get("loans"),
            "Fixed assets": li.get("net_ppe"),
        }
        liab_equity: dict[str, float | None] = {
            "Equity": total_equity,
            "Minority interest": minority_interest,
            "Deposits": li.get("deposits"),
            "Borrowings": li.get("total_debt"),
        }
    else:
        assets = {
            "PP&E": li.get("net_ppe"),
            "Goodwill & intangibles": li.get("goodwill_intangibles"),
            "Investments": li.get("investments"),
            "Inventory": li.get("inventory"),
            "Receivables": li.get("receivables"),
            "Cash & equivalents": li.get("cash_and_equivalents"),
        }
        liab_equity = {
            "Equity": total_equity,
            "Minority interest": minority_interest,
            "Debt": li.get("total_debt"),
            "Payables": li.get("payables"),
        }

    # Split the residual where Yahoo does expose this much granularity,
    # instead of lumping everything into one opaque "Other".
    if li.get("other_current_assets") is not None:
        assets["Other current"] = li["other_current_assets"]
    if li.get("other_non_current_assets") is not None:
        assets["Other non-current"] = li["other_non_current_assets"]
    if li.get("other_current_liabilities") is not None:
        liab_equity["Other current"] = li["other_current_liabilities"]
    if li.get("other_non_current_liabilities") is not None:
        liab_equity["Other non-current"] = li["other_non_current_liabilities"]

    assets["Other"] = (total_assets - _sum_known(assets)) if total_assets is not None else None
    liab_equity["Other"] = (
        (total_liab_equity - _sum_known(liab_equity)) if total_liab_equity is not None else None
    )

    balance_check_pct = None
    if total_assets not in (None, 0) and total_liab_equity is not None:
        balance_check_pct = abs(total_assets - total_liab_equity) / abs(total_assets) * 100

    net_debt = None
    if li.get("total_debt") is not None and li.get("cash_and_equivalents") is not None:
        net_debt = li["total_debt"] - li["cash_and_equivalents"]

    bvps = None
    if total_equity is not None and li.get("shares_outstanding"):
        bvps = per_share_value(Crore(total_equity), Shares(li["shares_outstanding"]))

    return {
        "fiscal_year": fiscal_year,
        "period_end": period_end,
        "assets": assets,
        "liabilities_equity": liab_equity,
        "balance_check_pct": balance_check_pct,
        "net_debt": net_debt if template not in _FINANCIAL_TEMPLATES else None,
        "bvps": bvps,
    }


def compute_balance_sheet_detail(balance_periods: list[dict], template: str) -> list[dict]:
    return [
        compute_balance_sheet_period(p["fiscal_year"], p["period_end"], p["line_items"], template)
        for p in balance_periods
    ]

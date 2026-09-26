"""Which metrics show as headline KPI cards per business-model template
(PLAN.md §2). `available=False` entries are metrics the plan calls for that
this free data source cannot provide (credit cost, GNPA/NNPA, AUM growth,
P/EV, solvency ratio) -- routers must return these as `null` with
`available: false` so the UI can render "Not in free data source" instead
of inventing a number.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Template = Literal["bank", "nbfc", "insurance", "exchange", "general"]


class KPIDef(TypedDict):
    key: str
    label: str
    available: bool


KPI_DEFINITIONS: dict[Template, list[KPIDef]] = {
    "bank": [
        {"key": "nii_growth", "label": "NII growth", "available": True},
        {"key": "nim", "label": "NIM (derived)", "available": True},
        {"key": "cost_to_income", "label": "Cost-to-income", "available": True},
        {"key": "roa", "label": "ROA", "available": True},
        {"key": "roe", "label": "ROE", "available": True},
        {"key": "pb", "label": "P/B", "available": True},
        {"key": "advances_deposits_growth", "label": "Advances & deposits growth", "available": False},
        {"key": "credit_cost", "label": "Credit cost", "available": False},
        {"key": "gnpa_nnpa", "label": "GNPA/NNPA", "available": False},
    ],
    "nbfc": [
        {"key": "aum_growth", "label": "AUM/loan growth", "available": False},
        {"key": "nim", "label": "NIM (derived)", "available": True},
        {"key": "roa", "label": "ROA", "available": True},
        {"key": "roe", "label": "ROE", "available": True},
        {"key": "pb", "label": "P/B", "available": True},
        {"key": "debt_to_equity", "label": "D/E", "available": True},
    ],
    "insurance": [
        {"key": "premium_growth", "label": "Premium growth", "available": True},
        {"key": "p_ev", "label": "P/EV", "available": False},
        {"key": "roe", "label": "ROE", "available": True},
        {"key": "solvency_ratio", "label": "Solvency", "available": False},
        {"key": "pb", "label": "P/B", "available": True},
    ],
    "exchange": [
        {"key": "revenue_growth", "label": "Revenue growth", "available": True},
        {"key": "ebitda_margin", "label": "EBITDA margin", "available": True},
        {"key": "pat_margin", "label": "PAT margin", "available": True},
        {"key": "roe", "label": "ROE", "available": True},
        {"key": "pe", "label": "P/E", "available": True},
    ],
    "general": [
        {"key": "revenue_growth", "label": "Revenue growth", "available": True},
        {"key": "ebitda_growth", "label": "EBITDA growth", "available": True},
        {"key": "pat_growth", "label": "PAT growth", "available": True},
        {"key": "ebitda_margin", "label": "EBITDA margin", "available": True},
        {"key": "roce", "label": "ROCE", "available": True},
        {"key": "roe", "label": "ROE", "available": True},
        {"key": "debt_to_equity", "label": "D/E", "available": True},
        {"key": "interest_coverage", "label": "Interest coverage", "available": True},
        {"key": "cash_conversion_cycle", "label": "Working-capital days", "available": True},
        {"key": "fcf", "label": "FCF", "available": True},
        {"key": "ev_ebitda", "label": "EV/EBITDA", "available": True},
        {"key": "pe", "label": "P/E", "available": True},
    ],
}


def headline_kpis(template: Template) -> list[KPIDef]:
    return KPI_DEFINITIONS.get(template, KPI_DEFINITIONS["general"])

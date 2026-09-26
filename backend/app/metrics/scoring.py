"""6-axis financial health radar (Growth, Profitability, Leverage,
Liquidity, Efficiency, Valuation), scored 0-100 against a peer group.

PLAN.md "Phase 1.5 review" item 4: every axis score must come back with the
metrics and weights behind it (not just the number), so a tooltip can
explain *why* a company scored what it scored.

This module is pure: `axis_score`/`health_radar` take already-computed
metric values (for the company and its peers) and do no I/O. The router
layer is responsible for fetching financials and computing those values via
`app.metrics.ratios`.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from app.metrics.templates import Template

Axis = Literal["growth", "profitability", "leverage", "liquidity", "efficiency", "valuation"]


class MetricSpec(TypedDict):
    key: str
    weight: float
    higher_is_better: bool


# Metrics chosen per template based on what's actually available for that
# business model (per data_coverage_report.md) -- an axis with no
# computable metrics for a template is intentionally left empty rather than
# padded with a metric the template can't report, so its score comes back
# `None` ("not applicable"), not a misleading number.
AXIS_SPECS: dict[Template, dict[Axis, list[MetricSpec]]] = {
    "general": {
        "growth": [
            {"key": "revenue_cagr_3y", "weight": 0.6, "higher_is_better": True},
            {"key": "pat_cagr_3y", "weight": 0.4, "higher_is_better": True},
        ],
        "profitability": [
            {"key": "ebitda_margin", "weight": 0.5, "higher_is_better": True},
            {"key": "roe", "weight": 0.5, "higher_is_better": True},
        ],
        "leverage": [
            {"key": "debt_to_equity", "weight": 0.5, "higher_is_better": False},
            {"key": "interest_coverage", "weight": 0.5, "higher_is_better": True},
        ],
        "liquidity": [
            {"key": "current_ratio", "weight": 1.0, "higher_is_better": True},
        ],
        "efficiency": [
            {"key": "asset_turnover", "weight": 0.5, "higher_is_better": True},
            {"key": "cash_conversion_cycle", "weight": 0.5, "higher_is_better": False},
        ],
        "valuation": [
            {"key": "pe", "weight": 0.5, "higher_is_better": False},
            {"key": "ev_ebitda", "weight": 0.5, "higher_is_better": False},
        ],
    },
    "exchange": {
        "growth": [{"key": "revenue_cagr_3y", "weight": 1.0, "higher_is_better": True}],
        "profitability": [
            {"key": "ebitda_margin", "weight": 0.5, "higher_is_better": True},
            {"key": "roe", "weight": 0.5, "higher_is_better": True},
        ],
        "leverage": [
            {"key": "debt_to_equity", "weight": 0.5, "higher_is_better": False},
            {"key": "interest_coverage", "weight": 0.5, "higher_is_better": True},
        ],
        "liquidity": [{"key": "current_ratio", "weight": 1.0, "higher_is_better": True}],
        "efficiency": [{"key": "asset_turnover", "weight": 1.0, "higher_is_better": True}],
        "valuation": [
            {"key": "pe", "weight": 0.5, "higher_is_better": False},
            {"key": "ev_ebitda", "weight": 0.5, "higher_is_better": False},
        ],
    },
    "bank": {
        "growth": [{"key": "nii_growth", "weight": 1.0, "higher_is_better": True}],
        "profitability": [
            {"key": "roe", "weight": 0.5, "higher_is_better": True},
            {"key": "roa", "weight": 0.5, "higher_is_better": True},
        ],
        "leverage": [{"key": "debt_to_equity", "weight": 1.0, "higher_is_better": False}],
        "liquidity": [],  # no current_assets/liabilities concept for banks
        "efficiency": [{"key": "cost_to_income", "weight": 1.0, "higher_is_better": False}],
        "valuation": [{"key": "pb", "weight": 1.0, "higher_is_better": False}],
    },
    "nbfc": {
        "growth": [{"key": "nii_growth", "weight": 1.0, "higher_is_better": True}],
        "profitability": [
            {"key": "roe", "weight": 0.5, "higher_is_better": True},
            {"key": "roa", "weight": 0.5, "higher_is_better": True},
        ],
        "leverage": [{"key": "debt_to_equity", "weight": 1.0, "higher_is_better": False}],
        "liquidity": [],
        "efficiency": [],
        "valuation": [{"key": "pb", "weight": 1.0, "higher_is_better": False}],
    },
    "insurance": {
        "growth": [{"key": "premium_growth", "weight": 1.0, "higher_is_better": True}],
        "profitability": [{"key": "roe", "weight": 1.0, "higher_is_better": True}],
        "leverage": [],  # solvency ratio (the real leverage metric here) isn't available
        "liquidity": [],
        "efficiency": [],
        "valuation": [{"key": "pb", "weight": 1.0, "higher_is_better": False}],
    },
}


# Whether a *higher* value of each metric is better, for percentile-ranking
# purposes outside the fixed AXIS_SPECS (e.g. the /api/ratios peer-percentile
# column, which reports every computed metric, not just the ones that feed
# an axis). Anything not listed here defaults to True in the ratios router
# -- a reasonable default for growth/margin/return metrics, but worth
# reviewing if a listed metric here turns out wrong for a given use.
METRIC_HIGHER_IS_BETTER: dict[str, bool] = {
    "debt_to_equity": False,
    "net_debt_to_ebitda": False,
    "debt_to_assets": False,
    "debtor_days": False,
    "inventory_days": False,
    "cash_conversion_cycle": False,
    "pe": False,
    "pb": False,
    "ev_ebitda": False,
    "ev_sales": False,
    "peg": False,
    "cost_to_income": False,
    "payable_days": True,  # longer payment terms are generally favourable working capital
}


class AxisComponent(TypedDict):
    metric: str
    value: float | None
    weight: float
    higher_is_better: bool
    percentile: float | None


class AxisResult(TypedDict):
    score: float | None
    components: list[AxisComponent]


def percentile_rank(
    value: float | None, peer_values: list[float | None], higher_is_better: bool = True
) -> float | None:
    """What percentage of `peer_values` this `value` beats-or-ties, 0-100.
    `None` if `value` or every peer value is missing. Include the company's
    own value in `peer_values` if it should be ranked among its peers
    (typical usage) -- percentile_rank doesn't special-case self-inclusion."""
    if value is None:
        return None
    valid_peers = [v for v in peer_values if v is not None]
    if not valid_peers:
        return None
    if higher_is_better:
        beaten_or_tied = sum(1 for v in valid_peers if value >= v)
    else:
        beaten_or_tied = sum(1 for v in valid_peers if value <= v)
    return beaten_or_tied / len(valid_peers) * 100


def axis_score(
    metric_values: dict[str, float | None],
    peer_values: dict[str, list[float | None]],
    specs: list[MetricSpec],
) -> AxisResult:
    """One radar axis: a weighted average of each spec metric's percentile
    rank among peers. A spec whose value or peer data is missing drops out
    of both the numerator and the weight total, rather than being scored 0."""
    components: list[AxisComponent] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for spec in specs:
        value = metric_values.get(spec["key"])
        percentile = percentile_rank(
            value, peer_values.get(spec["key"], []), spec["higher_is_better"]
        )
        components.append(
            {
                "metric": spec["key"],
                "value": value,
                "weight": spec["weight"],
                "higher_is_better": spec["higher_is_better"],
                "percentile": percentile,
            }
        )
        if percentile is not None:
            weighted_sum += percentile * spec["weight"]
            weight_total += spec["weight"]

    score = weighted_sum / weight_total if weight_total > 0 else None
    return {"score": score, "components": components}


def health_radar(
    template: Template,
    metric_values: dict[str, float | None],
    peer_values: dict[str, list[float | None]],
) -> dict[Axis, AxisResult]:
    """All 6 axes for one company. An axis with no metrics defined for this
    template (e.g. Liquidity for a bank) comes back with an empty
    `components` list and `score: None` -- "not applicable", not "zero"."""
    specs_by_axis = AXIS_SPECS.get(template, AXIS_SPECS["general"])
    return {
        axis: axis_score(metric_values, peer_values, specs)
        for axis, specs in specs_by_axis.items()
    }

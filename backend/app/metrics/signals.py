"""Rule-based "Strengths & watch-outs" (PLAN.md §4.3/§4.3-fix) -- explicit,
unit-tested rules over already-computed metrics/history/peer data, not an
LLM or any kind of inference. Every message cites the numbers behind it.

Materiality floors (§4.3 review) keep a rule from firing on a real but
trivial move -- TCS's D/E rose 3 straight years (0.085x -> 0.105x) but both
ends are far below any leverage-comfort threshold and the total move is
tiny, so it shouldn't read as a watch-out.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from app.metrics.scoring import percentile_rank

SignalType = Literal["strength", "watch"]


class Signal(TypedDict):
    type: SignalType
    rule: str
    message: str
    values: dict[str, float | None]


def _trend_history(history: dict[str, list[dict]], key: str, min_points: int = 4) -> list[float] | None:
    points = history.get(key, [])
    if len(points) < min_points:
        return None
    trailing = points[-min_points:]
    values = [p["value"] for p in trailing]
    if any(v is None for v in values):
        return None
    return values


def _is_strictly_increasing(values: list[float]) -> bool:
    return all(b > a for a, b in zip(values, values[1:]))


def _peer_median(peer_values: dict, key: str) -> float | None:
    valid = [v for v in peer_values.get(key, []) if v is not None]
    return sorted(valid)[len(valid) // 2] if valid else None


# --------------------------------------------------------------------------
# General / exchange templates
# --------------------------------------------------------------------------


def _rule_roce_top_quartile(metrics: dict, peer_values: dict) -> Signal | None:
    value = metrics.get("roce")
    if value is None:
        return None
    peers = peer_values.get("roce", [])
    percentile = percentile_rank(value, peers, higher_is_better=True)
    if percentile is None or percentile < 75:
        return None
    median = _peer_median(peer_values, "roce")
    message = f"ROCE {value:.1f}%"
    if median is not None:
        message += f" vs sector median {median:.1f}%"
    message += " (top quartile)"
    return {
        "type": "strength",
        "rule": "roce_top_quartile",
        "message": message,
        "values": {"roce": value, "sector_median": median, "percentile": percentile},
    }


_DE_MATERIALITY_LEVEL = 0.5
_DE_MATERIALITY_RISE = 0.25


def _rule_debt_to_equity_rising(history: dict[str, list[dict]]) -> Signal | None:
    values = _trend_history(history, "debt_to_equity")
    if values is None or not _is_strictly_increasing(values):
        return None
    change = values[-1] - values[0]
    # Materiality floor (§4.3 review): a real, monotonic rise from a tiny,
    # comfortable base (TCS: 0.085x -> 0.105x) isn't a leverage watch-out --
    # only flag it if the level itself is already notable, or the total
    # move over the window is.
    if values[-1] <= _DE_MATERIALITY_LEVEL and change <= _DE_MATERIALITY_RISE:
        return None
    return {
        "type": "watch",
        "rule": "debt_to_equity_rising",
        "message": (
            f"D/E has risen for 3 straight years: "
            f"{values[0]:.2f}x -> {values[1]:.2f}x -> {values[2]:.2f}x -> {values[3]:.2f}x"
        ),
        "values": {"latest": values[-1], "change": change},
    }


_PAT_QUALITY_THRESHOLD = 0.8


def _rule_cfo_to_pat_weak(history: dict[str, list[dict]]) -> Signal | None:
    ratio_points = history.get("cfo_to_pat", [])
    pat_points = history.get("net_income", [])
    if len(ratio_points) < 2 or len(pat_points) < 2:
        return None
    trailing_ratio = [p["value"] for p in ratio_points[-2:]]
    trailing_pat = [p["value"] for p in pat_points[-2:]]
    if any(v is None for v in trailing_ratio) or any(v is None for v in trailing_pat):
        return None
    # §4.3 review: CFO/PAT < 0.8 is only a quality concern when there IS a
    # real profit to convert -- a company barely profitable or loss-making
    # has a noisy/meaningless CFO/PAT ratio, not a genuine earnings-quality
    # signal.
    if not all(v > 0 for v in trailing_pat):
        return None
    if not all(v < _PAT_QUALITY_THRESHOLD for v in trailing_ratio):
        return None
    return {
        "type": "watch",
        "rule": "cfo_to_pat_weak",
        "message": (
            f"CFO/PAT has stayed below 0.8x for 2+ years (latest {trailing_ratio[-1]:.2f}x) -- "
            "reported profit isn't fully converting to operating cash"
        ),
        "values": {"latest": trailing_ratio[-1], "prior": trailing_ratio[0]},
    }


_MARGIN_MATERIALITY_PP = 2.0


def _rule_margin_expanding(history: dict[str, list[dict]]) -> Signal | None:
    values = _trend_history(history, "ebitda_margin")
    if values is None or not _is_strictly_increasing(values):
        return None
    change = values[-1] - values[0]
    if change < _MARGIN_MATERIALITY_PP:
        return None
    return {
        "type": "strength",
        "rule": "margin_expanding",
        "message": (
            f"EBITDA margin has expanded for 3 straight years: "
            f"{values[0]:.1f}% -> {values[1]:.1f}% -> {values[2]:.1f}% -> {values[3]:.1f}%"
        ),
        "values": {"latest": values[-1], "change_pp": change},
    }


_INTEREST_COVERAGE_THRESHOLD = 3.0
_DEBT_MATERIALITY_OF_ASSETS = 0.05


def _rule_interest_coverage_thin(metrics: dict) -> Signal | None:
    value = metrics.get("interest_coverage")
    debt_to_assets = metrics.get("debt_to_assets")
    if value is None or value >= _INTEREST_COVERAGE_THRESHOLD:
        return None
    # §4.3 review: thin coverage on a near-debt-free balance sheet isn't a
    # real solvency concern (the ratio is just noisy near-zero-denominator
    # territory) -- only meaningful once debt is an actual part of the
    # capital structure.
    if debt_to_assets is None or debt_to_assets <= _DEBT_MATERIALITY_OF_ASSETS:
        return None
    return {
        "type": "watch",
        "rule": "interest_coverage_thin",
        "message": f"Interest coverage is {value:.2f}x, below the 3x comfort threshold",
        "values": {"interest_coverage": value, "debt_to_assets": debt_to_assets},
    }


# --------------------------------------------------------------------------
# Bank / NBFC templates
# --------------------------------------------------------------------------

_NIM_MATERIALITY_PP = 0.2
_COST_TO_INCOME_MATERIALITY_PP = 3.0


def _rule_nim_change(history: dict[str, list[dict]]) -> Signal | None:
    points = history.get("nim", [])
    if len(points) < 2:
        return None
    prev, latest = points[-2]["value"], points[-1]["value"]
    if prev is None or latest is None:
        return None
    change = latest - prev
    if abs(change) < _NIM_MATERIALITY_PP:
        return None
    return {
        "type": "strength" if change > 0 else "watch",
        "rule": "nim_change",
        "message": f"NIM {'improved' if change > 0 else 'declined'} {abs(change):.2f}pp YoY to {latest:.2f}%",
        "values": {"latest": latest, "change_pp": change},
    }


def _rule_cost_to_income_change(history: dict[str, list[dict]]) -> Signal | None:
    points = history.get("cost_to_income", [])
    if len(points) < 2:
        return None
    prev, latest = points[-2]["value"], points[-1]["value"]
    if prev is None or latest is None:
        return None
    change = latest - prev
    if abs(change) < _COST_TO_INCOME_MATERIALITY_PP:
        return None
    # Lower cost-to-income is better -- a decrease is a strength.
    return {
        "type": "watch" if change > 0 else "strength",
        "rule": "cost_to_income_change",
        "message": f"Cost-to-income {'rose' if change > 0 else 'fell'} {abs(change):.1f}pp YoY to {latest:.1f}%",
        "values": {"latest": latest, "change_pp": change},
    }


_ROA_WEAK_THRESHOLD = 1.0


def _rule_roa_extreme(metrics: dict, peer_values: dict) -> Signal | None:
    value = metrics.get("roa")
    if value is None:
        return None
    percentile = percentile_rank(value, peer_values.get("roa", []), higher_is_better=True)
    if percentile is not None and percentile >= 75:
        median = _peer_median(peer_values, "roa")
        message = f"ROA {value:.2f}%"
        if median is not None:
            message += f" vs template median {median:.2f}%"
        message += " (top quartile)"
        return {
            "type": "strength",
            "rule": "roa_top_quartile",
            "message": message,
            "values": {"roa": value, "percentile": percentile},
        }
    if value < _ROA_WEAK_THRESHOLD:
        return {
            "type": "watch",
            "rule": "roa_weak",
            "message": f"ROA is {value:.2f}%, below the 1% comfort threshold for this template",
            "values": {"roa": value},
        }
    return None


_PAT_LAGS_NII_PP = 10.0


def _rule_pat_lags_nii(history: dict[str, list[dict]]) -> Signal | None:
    nii = history.get("nii_growth", [])
    pat = history.get("pat_growth", [])
    if len(nii) < 2 or len(pat) < 2:
        return None
    trailing_nii = [p["value"] for p in nii[-2:]]
    trailing_pat = [p["value"] for p in pat[-2:]]
    if any(v is None for v in trailing_nii) or any(v is None for v in trailing_pat):
        return None
    gaps = [n - p for n, p in zip(trailing_nii, trailing_pat)]
    if not all(g > _PAT_LAGS_NII_PP for g in gaps):
        return None
    return {
        "type": "watch",
        "rule": "pat_lags_nii",
        "message": (
            f"PAT growth has trailed NII growth by >{_PAT_LAGS_NII_PP:.0f}pp for 2 straight years "
            f"(latest gap {gaps[-1]:.1f}pp) -- rising costs or provisions eating into NII gains"
        ),
        "values": {"latest_gap_pp": gaps[-1], "prior_gap_pp": gaps[0]},
    }


# --------------------------------------------------------------------------
# Insurance template
# --------------------------------------------------------------------------

_PREMIUM_GROWTH_MATERIALITY_PP = 5.0


def _rule_premium_growth_vs_median(metrics: dict, peer_values: dict) -> Signal | None:
    value = metrics.get("premium_growth")
    median = _peer_median(peer_values, "premium_growth")
    if value is None or median is None:
        return None
    gap = value - median
    if abs(gap) < _PREMIUM_GROWTH_MATERIALITY_PP:
        return None
    return {
        "type": "strength" if gap > 0 else "watch",
        "rule": "premium_growth_vs_median",
        "message": f"Premium growth {value:.1f}% vs sector median {median:.1f}% ({gap:+.1f}pp)",
        "values": {"premium_growth": value, "sector_median": median, "gap_pp": gap},
    }


def _rule_insurance_roe_extreme(metrics: dict, peer_values: dict) -> Signal | None:
    value = metrics.get("roe")
    if value is None:
        return None
    percentile = percentile_rank(value, peer_values.get("roe", []), higher_is_better=True)
    if percentile is None:
        return None
    if percentile >= 75:
        return {
            "type": "strength",
            "rule": "roe_top_quartile",
            "message": f"ROE {value:.1f}% (top quartile vs sector)",
            "values": {"roe": value, "percentile": percentile},
        }
    if percentile <= 25:
        return {
            "type": "watch",
            "rule": "roe_bottom_quartile",
            "message": f"ROE {value:.1f}% (bottom quartile vs sector)",
            "values": {"roe": value, "percentile": percentile},
        }
    return None


def _magnitude(signal: Signal) -> float:
    v = signal["values"]
    rule = signal["rule"]
    if rule in ("roce_top_quartile", "roa_top_quartile"):
        return v.get("percentile") or 0
    if rule == "debt_to_equity_rising":
        return v.get("change") or 0
    if rule == "cfo_to_pat_weak":
        return _PAT_QUALITY_THRESHOLD - (v.get("latest") or _PAT_QUALITY_THRESHOLD)
    if rule == "margin_expanding":
        return v.get("change_pp") or 0
    if rule == "interest_coverage_thin":
        return _INTEREST_COVERAGE_THRESHOLD - (v.get("interest_coverage") or _INTEREST_COVERAGE_THRESHOLD)
    if rule in ("nim_change", "cost_to_income_change"):
        return abs(v.get("change_pp") or 0)
    if rule == "roa_weak":
        return _ROA_WEAK_THRESHOLD - (v.get("roa") or _ROA_WEAK_THRESHOLD)
    if rule == "pat_lags_nii":
        return v.get("latest_gap_pp") or 0
    if rule == "premium_growth_vs_median":
        return abs(v.get("gap_pp") or 0)
    if rule in ("roe_top_quartile", "roe_bottom_quartile"):
        return abs((v.get("percentile") or 50) - 50)
    return 0


_MAX_PER_TYPE = 4

_FINANCIAL_TEMPLATES = ("bank", "nbfc", "insurance")


def strengths_and_watchouts(
    metrics: dict[str, float | None],
    history: dict[str, list[dict]],
    peer_values: dict[str, list[float | None]],
    template: str,
) -> list[Signal]:
    """All rule hits, capped at 4 strengths and 4 watch-outs, ranked by
    magnitude within type. Rule set is template-specific (§4.3 review):
    D/E, interest-coverage and the general profitability/quality rules
    don't apply to bank/NBFC/insurance business models, which get their
    own NIM/cost-to-income/ROA/PAT-vs-NII (bank/NBFC) or premium-growth/ROE
    (insurance) rules instead."""
    if template == "insurance":
        candidates = [
            _rule_premium_growth_vs_median(metrics, peer_values),
            _rule_insurance_roe_extreme(metrics, peer_values),
        ]
    elif template in ("bank", "nbfc"):
        candidates = [
            _rule_nim_change(history),
            _rule_cost_to_income_change(history),
            _rule_roa_extreme(metrics, peer_values),
            _rule_pat_lags_nii(history),
        ]
    else:
        candidates = [
            _rule_roce_top_quartile(metrics, peer_values),
            _rule_debt_to_equity_rising(history),
            _rule_cfo_to_pat_weak(history),
            _rule_margin_expanding(history),
            _rule_interest_coverage_thin(metrics),
        ]

    signals = [s for s in candidates if s is not None]
    strengths = sorted((s for s in signals if s["type"] == "strength"), key=_magnitude, reverse=True)
    watches = sorted((s for s in signals if s["type"] == "watch"), key=_magnitude, reverse=True)
    return strengths[:_MAX_PER_TYPE] + watches[:_MAX_PER_TYPE]

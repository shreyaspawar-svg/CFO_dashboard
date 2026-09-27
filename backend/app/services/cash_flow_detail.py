"""Cash-flow derived figures computed server-side (PLAN.md §4.5): FCF
margin, CFO/EBITDA, CFO/PAT, and a latest-year sources->uses Sankey that
reconciles to the actual change in cash (from consecutive balance sheets,
since Yahoo's cash-flow statement doesn't separately expose a "change in
cash" line in this app's mapped fields) via a labelled "Other" link for
whatever forex/rounding residual is left -- never silently dropped.
"""

from __future__ import annotations

_GAP_LABEL = "Other (FX/rounding)"


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_cash_flow_ratios(
    cfo: float | None, ebitda: float | None, net_income: float | None, fcf: float | None, revenue: float | None
) -> dict[str, float | None]:
    fcf_margin = _safe_div(fcf, revenue)
    return {
        "cfo_to_ebitda": _safe_div(cfo, ebitda),
        "cfo_to_pat": _safe_div(cfo, net_income),
        "fcf_margin_pct": fcf_margin * 100 if fcf_margin is not None else None,
    }


def compute_cash_flow_sankey(
    cfo: float | None,
    cfi: float | None,
    cff: float | None,
    actual_change_in_cash: float | None,
    fx_effect: float | None = None,
) -> dict:
    """One period's CFO/CFI/CFF (and, if reported, FX translation effect) as
    a sources->uses flow through a "Cash pool" node, plus a labelled gap
    link reconciling CFO+CFI+CFF(+FX) to the ACTUAL reported change in cash
    (EndCashPosition - BeginningCashPosition from the cash flow statement
    itself) -- never just presented as if they always matched exactly."""
    computed_change = None
    if cfo is not None and cfi is not None and cff is not None:
        computed_change = cfo + cfi + cff + (fx_effect or 0)

    gap = None
    if computed_change is not None and actual_change_in_cash is not None:
        gap = actual_change_in_cash - computed_change

    links: list[dict] = []

    def add(source: str, target: str, value: float | None) -> None:
        if value is None or value == 0:
            return
        links.append({"source": source, "target": target, "value": abs(value)})

    for label, value in (
        ("Operating activities", cfo),
        ("Investing activities", cfi),
        ("Financing activities", cff),
        ("FX translation effect", fx_effect),
    ):
        if value is None:
            continue
        if value > 0:
            add(label, "Cash pool", value)
        else:
            add("Cash pool", label, value)

    if gap is not None:
        if gap > 0:
            add(_GAP_LABEL, "Cash pool", gap)
        elif gap < 0:
            add("Cash pool", _GAP_LABEL, gap)

    return {
        "links": links,
        "computed_change_in_cash": computed_change,
        "reported_change_in_cash": actual_change_in_cash,
        "gap": gap,
    }

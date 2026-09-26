"""Which periods of a symbol's history are comparable for growth/CAGR/score
purposes (PLAN.md "Phase 1.5 review" item 2: TMPV's pre-demerger years and
JIOFIN's FY23 shell year must stay out of growth rates, health-radar scores
and valuation ranges).

Reuses `corporate_actions.json`'s `cutoff_period_end` (the same file that
drives the `notes` field on `/api/financials`): a period at or after the
cutoff is comparable, a period before it isn't.
"""

from __future__ import annotations

from datetime import date

from app.services.corporate_actions import get_action


def comparable_periods(symbol: str, periods: list[dict]) -> tuple[list[dict], str | None]:
    """Filter `periods` (each a dict with a `period_end` ISO-date string,
    e.g. the normalized FinancialPeriod shape) down to the comparable ones.

    Returns (comparable_periods, excluded_range_note). The note is None when
    nothing was excluded, and states the excluded range's start/end years
    otherwise -- the dashboard should surface this alongside any growth
    figure computed from the filtered periods.
    """
    action = get_action(symbol)
    cutoff = action.get("cutoff_period_end") if action else None
    if cutoff is None:
        return periods, None

    cutoff_date = date.fromisoformat(cutoff)
    kept = [p for p in periods if date.fromisoformat(p["period_end"]) >= cutoff_date]
    excluded = [p for p in periods if date.fromisoformat(p["period_end"]) < cutoff_date]

    if not excluded:
        return periods, None

    excluded_years = sorted(p["fiscal_year"] for p in excluded)
    note = (
        f"Growth/CAGR figures exclude {', '.join(excluded_years)} "
        f"(pre-corporate-action, not comparable -- see financials `notes`)"
    )
    return kept, note

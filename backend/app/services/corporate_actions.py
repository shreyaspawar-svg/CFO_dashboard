"""Known corporate actions (demergers, spinoffs, renames) that make part of
a symbol's Yahoo-reported history non-comparable or discontinuous.

This is a small hand-curated list (backend/data/corporate_actions.json), not
something derivable from the fundamentals data itself -- Yahoo doesn't flag
these breaks. Phase 2's growth/CAGR calculations should treat a period
before `cutoff_period_end` as a different reporting entity.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from typing import Any

from app.config import BASE_DIR

CORPORATE_ACTIONS_PATH = BASE_DIR / "data" / "corporate_actions.json"


@lru_cache
def _load() -> dict[str, dict[str, Any]]:
    return json.loads(CORPORATE_ACTIONS_PATH.read_text(encoding="utf-8"))


def get_action(symbol: str) -> dict[str, Any] | None:
    """The raw corporate-action record for a symbol (message + optional
    cutoff_period_end), or None if it has none."""
    return _load().get(symbol.upper())


def notes_for_symbol(symbol: str, period_ends: list[str]) -> list[str]:
    """Return the corporate-action note(s) applicable to this symbol.

    If the action has a `cutoff_period_end`, only surface the note when at
    least one of the given period-end dates (ISO strings) predates it;
    otherwise (cutoff is null) the note is always informational and always
    included.
    """
    action = get_action(symbol)
    if action is None:
        return []

    cutoff = action.get("cutoff_period_end")
    if cutoff is None:
        return [action["message"]]

    cutoff_date = date.fromisoformat(cutoff)
    has_pre_cutoff_period = any(
        date.fromisoformat(period_end) < cutoff_date for period_end in period_ends
    )
    return [action["message"]] if has_pre_cutoff_period else []

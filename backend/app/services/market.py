"""NSE market-hours check (IST, weekdays, 09:15-15:30). A holiday calendar
is out of scope for Phase 1 and is deferred to the frontend top bar (Phase 3)."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Literal

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
PRE_OPEN_START = time(9, 0)


def market_status(now: datetime | None = None) -> Literal["open", "closed", "pre_open"]:
    now_ist = (now or datetime.now(timezone.utc)).astimezone(IST)
    if now_ist.weekday() >= 5:  # Saturday, Sunday
        return "closed"
    current_time = now_ist.time()
    if PRE_OPEN_START <= current_time < MARKET_OPEN:
        return "pre_open"
    if MARKET_OPEN <= current_time <= MARKET_CLOSE:
        return "open"
    return "closed"

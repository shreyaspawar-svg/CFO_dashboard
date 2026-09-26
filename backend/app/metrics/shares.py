"""Adjusting a share count reported as of one date to match another date,
by applying any stock splits/bonus issues between them.

PLAN.md "Phase 1.5 review" item 1: share count comes from the last annual
(or quarterly) balance sheet, but price is live. After a split or bonus,
market cap and any per-share figure combining that stale share count with a
live price would be off by the split ratio unless adjusted. Yahoo reports
both splits and bonus issues the same way (a numerator:denominator
share-multiplication ratio), so one function handles both.
"""

from __future__ import annotations

from datetime import date


def adjust_shares_for_splits(
    shares: float, as_of_date: str, splits: list[dict], target_date: str
) -> float:
    """`shares` as reported at `as_of_date` (ISO date string), carried
    forward (or back) to `target_date` by multiplying (or dividing) through
    every split/bonus between the two dates.

    `splits` items are `{"date": ISO string, "numerator": float,
    "denominator": float}` (see `services.yahoo.fetch_splits`); a 2-for-1
    split is numerator=2, denominator=1, and multiplies the share count by
    2. Splits exactly on either boundary date are included.
    """
    as_of = date.fromisoformat(as_of_date)
    target = date.fromisoformat(target_date)

    if target == as_of:
        return shares

    if target > as_of:
        ratio = 1.0
        for split in splits:
            split_date = date.fromisoformat(split["date"])
            if as_of < split_date <= target:
                ratio *= split["numerator"] / split["denominator"]
        return shares * ratio

    # target < as_of: walk the adjustment backwards.
    ratio = 1.0
    for split in splits:
        split_date = date.fromisoformat(split["date"])
        if target < split_date <= as_of:
            ratio *= split["numerator"] / split["denominator"]
    return shares / ratio if ratio else shares

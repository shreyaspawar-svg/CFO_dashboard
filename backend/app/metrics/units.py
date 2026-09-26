"""Distinct types for the three units that flow through the metrics layer,
so mixing them is a type error, not a silent ~1e7x bug.

PLAN.md "Phase 3 review" / Phase 2.2 item 4: the Phase 2.1 book-value bug
was exactly this -- `total_equity` (₹ crore, this app's internal currency
convention) divided directly by `shares_outstanding` (a raw count), with no
conversion, understating book value per share by ~1e7x. `NewType` doesn't
enforce anything at runtime (these are still plain floats), but it makes
every conversion site an explicit, named function call instead of an
inline `* CRORE` a reader has to notice is even happening -- and a type
checker (mypy/pyright) run over this module WILL flag `Crore` passed where
`Rupees` is expected.
"""

from __future__ import annotations

from typing import NewType

Crore = NewType("Crore", float)
"""An amount in ₹ crore -- this app's internal currency convention (see
services/normalize.py). What `total_equity`, `revenue`, `market_cap`, etc.
are stored as everywhere in the metrics/financials layer."""

Rupees = NewType("Rupees", float)
"""An amount in absolute ₹ (i.e. crore x 1e7). What a live price, and any
per-share value, are naturally expressed in."""

Shares = NewType("Shares", float)
"""A raw share count (not crore-scaled, not a currency)."""

PerShare = NewType("PerShare", float)
"""A ₹-per-share value (book value/share, EPS, price) -- already in
absolute rupees, same as `Rupees`, but kept as a separate name since it's
conceptually "a rate", not "an amount"."""

CRORE_PER_UNIT = 10_000_000
"""1 crore, in absolute rupees. Exposed for callers that need the raw
conversion factor (e.g. plausibility checks comparing a crore-denominated
figure against a rupees-denominated one) rather than a single value."""


def crore_to_rupees(value: Crore) -> Rupees:
    return Rupees(value * CRORE_PER_UNIT)


def rupees_to_crore(value: Rupees) -> Crore:
    return Crore(value / CRORE_PER_UNIT)


def per_share_value(amount: Crore, shares: Shares) -> PerShare | None:
    """`amount` (₹ crore) divided by `shares` -- the one place this
    conversion should happen, rather than an inline `* CRORE` at each call
    site. None if `shares` is zero/falsy (never a division error, matching
    this codebase's null-over-crash convention elsewhere)."""
    if not shares:
        return None
    return PerShare(crore_to_rupees(amount) / shares)

"""Sanity checks across all 50 symbols for unit-scale mistakes (PLAN.md
"Phase 3 review" / Phase 2.2 item 4) -- the class of bug the Phase 2.1
book-value fix caught by accident (equity in crore divided by a raw share
count, understating book value ~1e7x). These checks don't know *which*
conversion was wrong, only that a result is implausible for a NIFTY 50
constituent, so they catch a *future* unit mistake even in a metric that
happens to have no live cross-check to compare against.

Every check returns `True` when nothing can be evaluated (missing inputs)
-- "no data" is not a plausibility violation, only an implausible value is.
"""

from __future__ import annotations

from app.metrics.units import CRORE_PER_UNIT

# A generous band, not a tight one: real NIFTY 50 book values per share
# range from single digits (e.g. a post-split, high-share-count company)
# to several thousand rupees (e.g. MRF-like high-face-value stocks) --
# this only needs to catch an off-by-1e7x-style scale error, not flag a
# genuinely unusual but real value.
_BOOK_VALUE_PER_SHARE_MIN = 0.5
_BOOK_VALUE_PER_SHARE_MAX = 500_000

_MARKET_CAP_TOLERANCE_PCT = 15.0

_PE_MIN = -1000.0
_PE_MAX = 1000.0


def book_value_per_share_is_plausible(value: float | None) -> bool:
    if value is None:
        return True
    return _BOOK_VALUE_PER_SHARE_MIN <= value <= _BOOK_VALUE_PER_SHARE_MAX


def market_cap_matches_price_times_shares(
    market_cap_crore: float | None,
    price: float | None,
    shares_outstanding: float | None,
    tolerance_pct: float = _MARKET_CAP_TOLERANCE_PCT,
) -> bool:
    """market_cap (Rs crore) should be within `tolerance_pct` of price x
    shares_outstanding (converted to crore) -- catches a market cap
    computed against the wrong share-count basis (e.g. this app's own
    Phase 1.5 split-double-counting bug, or a similar future mistake)."""
    if market_cap_crore is None or price is None or not shares_outstanding:
        return True
    implied_crore = price * shares_outstanding / CRORE_PER_UNIT
    if implied_crore == 0:
        return True
    divergence_pct = abs(market_cap_crore - implied_crore) / implied_crore * 100
    return divergence_pct <= tolerance_pct


def eps_price_ratio_is_plausible(
    eps: float | None, price: float | None, pe_min: float = _PE_MIN, pe_max: float = _PE_MAX
) -> bool:
    """The P/E implied by `eps` and `price` should fall in a wide but finite
    band -- catches EPS reported on a different per-unit basis than price
    (e.g. paise vs rupees, or a stale pre-split EPS against a post-split
    price) without needing a live cross-check to compare against."""
    if eps is None or price is None or eps == 0:
        return True
    implied_pe = price / eps
    return pe_min <= implied_pe <= pe_max


def pe_is_plausible(pe: float | None, pe_min: float = _PE_MIN, pe_max: float = _PE_MAX) -> bool:
    """Same band as `eps_price_ratio_is_plausible`, applied directly to an
    already-computed P/E -- use this on the value actually displayed
    (which may have taken a Yahoo fallback for a symbol whose own EPS is
    unit-inconsistent, e.g. INFY -- see docs/data-notes.md) rather than
    reconstructing a P/E from raw inputs that might not be what was
    shown."""
    if pe is None:
        return True
    return pe_min <= pe <= pe_max

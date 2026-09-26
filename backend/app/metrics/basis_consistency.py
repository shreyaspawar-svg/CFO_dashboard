"""Detects a symbol whose quarterly equity is inconsistently sourced across
periods -- alternating between two different reporting bases (e.g.
standalone vs. consolidated) rather than growing organically.

PLAN.md "Phase 4.1 review" item 1: HDFCBANK's own quarterly StockholdersEquity
alternates between a ~Rs5L Cr reading and a ~Rs7.8L Cr reading, quarter to
quarter -- something no real balance sheet does (see docs/data-notes.md for
the full write-up). Checked against real quarterly equity for all 50 NIFTY
symbols to calibrate the threshold below: every other symbol's adjacent-
quarter equity growth stays within an order of magnitude of organic (the
single largest one-off jump anywhere -- ADANIENT, a real equity raise -- is
+60.8%, but it doesn't *reverse*), while HDFCBANK repeatedly swings from
+53% to -29% and back. Only HDFCBANK trips this detector across the whole
universe, at thresholds from 10% to 15%.
"""

from __future__ import annotations

_SWING_THRESHOLD = 0.12
"""12%: comfortably above every real (non-oscillating) symbol's adjacent-
quarter equity swing in the calibration above, comfortably below HDFCBANK's
repeated +53%/-29%-class reversals."""


def _quarterly_growth_rates(equity_values: list[float | None]) -> list[float]:
    values = [v for v in equity_values if v is not None]
    rates: list[float] = []
    for prev, curr in zip(values, values[1:]):
        if prev == 0:
            continue
        rates.append((curr - prev) / prev)
    return rates


def equity_basis_oscillation_detected(quarterly_equity: list[float | None]) -> bool:
    """True if the quarterly equity series has at least one pair of
    adjacent, opposite-sign swings both exceeding `_SWING_THRESHOLD` in
    magnitude -- the signature of a free-data-source basis switch, not
    organic growth (which doesn't reverse direction by double digits from
    one quarter to the next). Needs at least 3 non-null quarters (2 growth
    rates) to evaluate; returns False with fewer, since there's nothing to
    compare a swing against."""
    rates = _quarterly_growth_rates(quarterly_equity)
    for prev, curr in zip(rates, rates[1:]):
        if (prev > _SWING_THRESHOLD and curr < -_SWING_THRESHOLD) or (
            prev < -_SWING_THRESHOLD and curr > _SWING_THRESHOLD
        ):
            return True
    return False

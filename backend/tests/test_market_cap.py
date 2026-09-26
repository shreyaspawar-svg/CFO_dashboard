"""Regression test for the split-adjustment bug found during the Phase 2
Screener.in spot-check: Yahoo's OrdinarySharesNumber is already the current
share count on every historical period for a company that's had a split
(confirmed empirically for TRENT and NESTLEIND), so multiplying by the
split ratio on top of it double-counts and overstates market cap by
exactly that ratio. `fetch_market_cap_detailed` must NOT apply
`adjust_shares_for_splits`, even when splits are present.
"""

from __future__ import annotations

import pytest

from app.services import yahoo


@pytest.mark.asyncio
async def test_market_cap_ignores_available_splits(monkeypatch):
    async def fake_shares_detailed(yf_ticker):
        return 1000.0, "2024-03-31"

    async def fake_splits(yf_ticker):
        # A 2:1 split between the share count's as-of date and today. If
        # this were (wrongly) applied, market cap would come out 2x.
        return [{"date": "2025-01-01", "numerator": 2.0, "denominator": 1.0}]

    async def fake_quote_summary_cross_check(yf_ticker):
        return None  # force reliance on price_x_shares, not the fallback

    monkeypatch.setattr(yahoo, "fetch_shares_outstanding_detailed", fake_shares_detailed)
    monkeypatch.setattr(yahoo, "fetch_splits", fake_splits)
    monkeypatch.setattr(yahoo, "_fetch_market_cap_via_quote_summary", fake_quote_summary_cross_check)

    market_cap, method, divergence = await yahoo.fetch_market_cap_detailed("FAKE.NS", last_price=50.0)

    assert market_cap == 50.0 * 1000.0  # NOT doubled
    assert method == "price_x_shares"
    assert divergence is None

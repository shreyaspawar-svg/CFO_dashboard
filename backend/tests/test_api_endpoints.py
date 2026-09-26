"""Schema tests for every Phase 1 endpoint, run against saved fixtures for
one company per business-model template. No test here calls Yahoo -- see
conftest.py's `_no_network` autouse fixture.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEMPLATE_SYMBOLS = {
    "TCS": "general",
    "HDFCBANK": "bank",
    "BAJFINANCE": "nbfc",
    "HDFCLIFE": "insurance",
    "BSE": "exchange",
}


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_universe_schema():
    resp = client.get("/api/universe")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sectors"]) == 14
    assert sum(len(s["companies"]) for s in body["sectors"]) == 50


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_quote_schema_and_market_cap_never_null(symbol):
    resp = client.get(f"/api/quote/{symbol}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert body["last_price"] is not None
    # Phase 1.5 fix: market cap must be derivable from price x shares
    # outstanding, without depending on a Yahoo crumb (which conftest.py's
    # _no_network fixture forces to be unavailable in every test).
    assert body["market_cap"] is not None
    assert body["market_cap"] > 0


def test_quotes_batch_schema():
    symbols = ",".join(TEMPLATE_SYMBOLS)
    resp = client.get(f"/api/quotes?symbols={symbols}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(TEMPLATE_SYMBOLS)
    assert all(q["market_cap"] is not None for q in body)


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_history_schema(symbol):
    resp = client.get(f"/api/history/{symbol}?range=1mo&interval=1d")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["bars"]) > 0
    assert len(body["benchmark_bars"]) > 0
    assert body["bars"][0]["close"] is not None


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
@pytest.mark.parametrize("period", ["annual", "quarterly"])
def test_financials_schema(symbol, period):
    resp = client.get(f"/api/financials/{symbol}?period={period}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert body["period"] == period
    assert len(body["income_statement"]) > 0


def test_tcs_receivables_present_regression():
    """Phase 1.5 fix: 'Receivables' was the wrong wire key (yfinance's
    display name, not Yahoo's actual field); the correct key is
    AccountsReceivable. Regression-guard against re-breaking this."""
    resp = client.get("/api/financials/TCS?period=annual")
    body = resp.json()
    latest = body["balance_sheet"][-1]
    assert latest["line_items"]["receivables"] is not None


def test_bank_interest_income_fields_present():
    """Phase 1.5 fix: banks need interest income/expense/NII for Phase 2's
    NIM, ROA and cost-to-income ratios."""
    resp = client.get("/api/financials/HDFCBANK?period=annual")
    body = resp.json()
    latest = body["income_statement"][-1]["line_items"]
    assert latest["interest_income"] is not None
    assert latest["interest_expense"] is not None
    assert latest["net_interest_income"] is not None


def test_insurer_premiums_and_interest_fields_present():
    resp = client.get("/api/financials/HDFCLIFE?period=annual")
    body = resp.json()
    latest = body["income_statement"][-1]["line_items"]
    assert latest["premiums_earned"] is not None
    assert latest["interest_income"] is not None


def test_general_company_lacks_bank_fields_and_has_ebitda():
    """Sanity check the template split: a non-financial company should have
    EBITDA and should NOT have bank-only fields fabricated as 0."""
    resp = client.get("/api/financials/TCS?period=annual")
    body = resp.json()
    latest = body["income_statement"][-1]["line_items"]
    assert latest["ebitda"] is not None
    assert latest["premiums_earned"] is None


def test_never_calls_real_yahoo(monkeypatch):
    """If a test ever forgets to use a fixtured symbol, the fake dispatcher
    raises AssertionError rather than silently falling through to a real
    HTTP call -- confirm that guard actually fires."""
    resp = client.get("/api/quote/RELIANCE")  # not in TEMPLATE_SYMBOLS' fixtures
    assert resp.status_code == 200
    body = resp.json()
    assert any("No fixture" in w or "AssertionError" in w for w in body["warnings"])

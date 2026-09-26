"""Schema tests for /api/overview (Phase 4 §4.1 backend additions: beta,
analyst target, relative performance vs NIFTY 50 and vs sector). Network
is blocked by conftest.py's autouse fixture, same as other endpoint tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEMPLATE_SYMBOLS = ["TCS", "HDFCBANK", "BAJFINANCE", "HDFCLIFE", "BSE"]


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_overview_schema(symbol):
    resp = client.get(f"/api/overview/{symbol}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert "beta" in body
    assert "analyst_target_mean" in body
    assert "relative_performance_vs_nifty50_pp" in body
    assert isinstance(body["warnings"], list)


def test_overview_unknown_symbol_404():
    resp = client.get("/api/overview/NOTREAL")
    assert resp.status_code == 404


def test_overview_degrades_gracefully_without_crumb_or_enough_history():
    """The fixture-mocked network never issues a crumb and only has ~20
    days of chart data -- beta and analyst target should come back None
    with warnings, not a 500."""
    resp = client.get("/api/overview/TCS")
    body = resp.json()
    assert body["beta"] is None
    assert body["analyst_target_mean"] is None
    assert any("Beta unavailable" in w for w in body["warnings"])
    assert any("Analyst target unavailable" in w for w in body["warnings"])

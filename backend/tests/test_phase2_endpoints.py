"""Schema tests for the Phase 2 endpoints (ratios, peers, valuation,
events), against the same 5 fixtured template symbols as Phase 1's
test_api_endpoints.py. Network is blocked by conftest.py's autouse fixture.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEMPLATE_SYMBOLS = ["TCS", "HDFCBANK", "BAJFINANCE", "HDFCLIFE", "BSE"]


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_ratios_schema(symbol):
    resp = client.get(f"/api/ratios/{symbol}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert body["peer_basis"] in ("sector", "template", "none")
    assert body["peer_count"] > 0
    assert set(body["health_radar"].keys()) == {
        "growth", "profitability", "leverage", "liquidity", "efficiency", "valuation",
    }
    assert "roe" in body["ratios"]


def test_ratios_bank_liquidity_axis_not_applicable():
    resp = client.get("/api/ratios/HDFCBANK")
    body = resp.json()
    assert body["health_radar"]["liquidity"]["score"] is None
    assert body["health_radar"]["liquidity"]["components"] == []


def test_ratios_general_has_leverage_and_valuation_axes_populated():
    resp = client.get("/api/ratios/TCS")
    body = resp.json()
    # TCS's own value is always in its peer set, so at minimum the metric
    # itself resolves even before considering unfixtured sector peers.
    assert body["ratios"]["debt_to_equity"]["value"] is not None
    assert body["ratios"]["pe"]["value"] is not None


def test_ratios_unknown_symbol_404():
    resp = client.get("/api/ratios/NOTREAL")
    assert resp.status_code == 404


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_peers_schema(symbol):
    resp = client.get(f"/api/peers/{symbol}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert len(body["peers"]) > 0
    assert any(p["symbol"] == symbol for p in body["peers"])


def test_peers_row_includes_metrics_dict():
    resp = client.get("/api/peers/HDFCBANK")
    body = resp.json()
    own_row = next(p for p in body["peers"] if p["symbol"] == "HDFCBANK")
    assert own_row["template"] == "bank"
    assert "roe" in own_row["metrics"]


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_valuation_schema(symbol):
    resp = client.get(f"/api/valuation/{symbol}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert "pe" in body["multiples"]
    assert set(body["dcf"].keys()) == {
        "enterprise_value", "equity_value", "intrinsic_value_per_share",
    }
    assert "growth_rate_pct" in body["dcf_inputs"]


def test_valuation_dcf_growth_override():
    resp = client.get("/api/valuation/TCS?growth_rate_pct=15&wacc_pct=13&terminal_growth_pct=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dcf_inputs"]["growth_rate_pct"] == 15.0
    assert body["dcf_inputs"]["wacc_pct"] == 13.0
    assert body["dcf_inputs"]["terminal_growth_pct"] == 5.0


def test_valuation_invalid_forecast_years_rejected():
    resp = client.get("/api/valuation/TCS?forecast_years=0")
    assert resp.status_code == 422


@pytest.mark.parametrize("symbol", TEMPLATE_SYMBOLS)
def test_events_schema(symbol):
    resp = client.get(f"/api/events/{symbol}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == symbol
    assert isinstance(body["dividends"], list)
    assert isinstance(body["splits"], list)
    # Documented, not silently absent.
    assert any("Shareholding" in w for w in body["warnings"])
    assert any("earnings date" in w for w in body["warnings"])

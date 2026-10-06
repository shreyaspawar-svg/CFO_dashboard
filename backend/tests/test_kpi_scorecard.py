"""Tests for the 20-KPI CFO scorecard (RIL single-company pivot). Uses the
existing TCS fixtures (same `general` template as RELIANCE; no RELIANCE-
specific fixtures exist, and nothing in this engine is template-aware) --
network is blocked by conftest.py's autouse patch, same as every other
endpoint test in this suite.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.metrics.kpi_scorecard import capex_return_pct, liquidity_runway_months
from app.services.kpi_scorecard_engine import compute_kpi_scorecard

client = TestClient(app)

_EXPECTED_GROUPS = [
    "Financial Performance",
    "Cash & Liquidity",
    "Working Capital Efficiency",
    "Operational Excellence",
    "Growth & Capital Allocation",
    "Risk, Compliance & Governance",
]

_UNAVAILABLE_KEYS = {
    "capacity_utilisation",
    "manufacturing_cost_per_unit",
    "oee",
    "audit_compliance",
    "safety_esg_cyber",
}


def test_scorecard_schema_and_group_shape():
    resp = client.get("/api/kpi-scorecard/TCS")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "TCS"
    assert [g["name"] for g in body["groups"]] == _EXPECTED_GROUPS
    assert sum(len(g["entries"]) for g in body["groups"]) == 20


def test_unknown_symbol_404():
    resp = client.get("/api/kpi-scorecard/NOTREAL")
    assert resp.status_code == 404


def test_operational_and_governance_kpis_are_honestly_unavailable():
    """5 of the 20 KPIs describe internal operational/audit/ESG data no
    public financial statement reports -- these must never carry a
    fabricated number, regardless of symbol or data availability."""
    resp = client.get("/api/kpi-scorecard/TCS")
    entries = {e["key"]: e for g in resp.json()["groups"] for e in g["entries"]}
    for key in _UNAVAILABLE_KEYS:
        assert entries[key]["method"] == "unavailable"
        assert entries[key]["value"] is None
        assert entries[key]["reason"]


def test_margin_kpis_report_delta_in_percentage_points_not_relative_pct():
    """EBITDA margin / PAT margin / ROCE / EBITDA-to-cash-conversion are
    rates -- their `qoq_delta` must be a plain point difference (current -
    prior), and `qoq_delta_pct` (a relative % change) must stay unset for
    them, since "the margin changed by X%" is ambiguous in a way "X
    percentage points" isn't."""
    resp = client.get("/api/kpi-scorecard/TCS")
    financial_performance = next(g for g in resp.json()["groups"] if g["name"] == "Financial Performance")
    for entry in financial_performance["entries"]:
        if entry["key"] == "revenue_growth_qoq":
            continue  # a growth rate itself, not a margin -- no prior_value to diff against
        if entry["value"] is not None and entry["prior_value"] is not None:
            assert entry["qoq_delta"] == entry["value"] - entry["prior_value"]
            assert entry["qoq_delta_pct"] is None


async def test_engine_runs_without_raising_for_every_fixture_symbol():
    """The step-lookup alignment and TTM-window logic must degrade to
    `None`/`unavailable`, never raise, across every template this suite has
    a fixture for -- a bank/NBFC/insurance/exchange template isn't
    expected to compute differently here (this engine isn't template-
    aware), but it must not crash on whatever quarterly coverage gaps that
    symbol happens to have."""
    for symbol in ("TCS", "HDFCBANK", "BAJFINANCE", "HDFCLIFE", "BSE"):
        result = await compute_kpi_scorecard(symbol)
        assert result["symbol"] == symbol
        assert sum(len(g["entries"]) for g in result["groups"]) == 20


def test_liquidity_runway_only_applies_when_burning_cash():
    assert liquidity_runway_months(1000, -300) == 1000 / 100
    assert liquidity_runway_months(1000, 300) is None  # FCF-positive quarter -- no runway to compute
    assert liquidity_runway_months(1000, 0) is None
    assert liquidity_runway_months(None, -300) is None


def test_capex_return_pct():
    assert capex_return_pct(50, -200) == 25.0  # abs() of a Yahoo-convention negative outflow
    assert capex_return_pct(50, 0) is None
    assert capex_return_pct(None, -200) is None

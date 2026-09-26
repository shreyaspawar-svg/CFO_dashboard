"""Global test fixtures. Autouse-patches the Yahoo HTTP layer so no test in
this suite ever makes a real network call -- all responses are served from
saved fixtures in tests/fixtures/<SYMBOL>/ (see tests/fixtures/_capture.py).

The `smoke` marker is the one deliberate exception: those tests are skipped
by this autouse patch via a marker check, since their entire point is to
exercise the live API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

TICKER_TO_SYMBOL = {
    "TCS.NS": "TCS",
    "HDFCBANK.NS": "HDFCBANK",
    "BAJFINANCE.NS": "BAJFINANCE",
    "HDFCLIFE.NS": "HDFCLIFE",
    "BSE.NS": "BSE",
}


def _load_fixture(relative_path: str) -> dict[str, Any]:
    path = FIXTURES_DIR / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_get_json_sync(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    from app.services.normalize import BALANCE_SHEET_MAP, CASH_FLOW_MAP, INCOME_STATEMENT_MAP
    from app.services.yahoo import _SHARES_OUTSTANDING_KEYS

    params = params or {}

    if "/chart/" in url:
        ticker = url.rsplit("/", 1)[-1]
        range_ = params.get("range")
        if ticker == "^NSEI":
            return _load_fixture("benchmark_chart_1mo.json")
        symbol = TICKER_TO_SYMBOL.get(ticker)
        if symbol is None:
            raise AssertionError(f"No fixture for chart ticker {ticker!r}")
        filename = "chart_5d.json" if range_ == "5d" else "chart_1mo.json"
        return _load_fixture(f"{symbol}/{filename}")

    if "fundamentals-timeseries" in url:
        ticker = params.get("symbol", "")
        symbol = TICKER_TO_SYMBOL.get(ticker)
        if symbol is None:
            raise AssertionError(f"No fixture for fundamentals ticker {ticker!r}")

        type_param = params.get("type", "")
        first_full_key = type_param.split(",")[0]
        timescale = "annual" if first_full_key.startswith("annual") else "quarterly"
        field = first_full_key[len(timescale):]

        if field in INCOME_STATEMENT_MAP:
            statement = "income"
        elif field in BALANCE_SHEET_MAP:
            statement = "balance"
        elif field in CASH_FLOW_MAP:
            statement = "cashflow"
        elif field in _SHARES_OUTSTANDING_KEYS:
            return _load_fixture(f"{symbol}/shares_quarterly.json")
        else:
            raise AssertionError(f"No fixture mapping for field {field!r}")

        return _load_fixture(f"{symbol}/{statement}_{timescale}.json")

    raise AssertionError(f"Test tried to hit a real, un-fixtured Yahoo URL: {url}")


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    if request.node.get_closest_marker("smoke"):
        yield  # smoke tests deliberately hit the live API
        return

    monkeypatch.setattr("app.services.yahoo._get_json_sync", _fake_get_json_sync)
    # Force the crumb-based cross-check to look "unavailable" rather than
    # make a real network call -- market cap must come from price x shares.
    monkeypatch.setattr("app.services.yahoo._get_crumb", lambda: None)
    yield


@pytest.fixture(autouse=True)
def _isolated_cache(request, tmp_path, monkeypatch):
    """Every test gets its own empty TTLCache on a temp sqlite file, so
    tests never read stale entries from (or pollute) the real dev cache at
    backend/.cache, and aren't order-dependent on each other."""
    if request.node.get_closest_marker("smoke"):
        yield
        return

    from app import config
    from app.services import cache as cache_module

    monkeypatch.setattr(
        config.get_settings(), "sqlite_cache_path", tmp_path / "cache.sqlite"
    )
    monkeypatch.setattr(cache_module, "_cache", None)
    yield
    monkeypatch.setattr(cache_module, "_cache", None)


@pytest.fixture(autouse=True)
def _reset_data_source(monkeypatch):
    from app.services import datasource

    monkeypatch.setattr(datasource, "_data_source", None)
    yield
    monkeypatch.setattr(datasource, "_data_source", None)

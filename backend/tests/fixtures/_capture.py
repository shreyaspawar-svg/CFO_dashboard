"""One-off script: captures real Yahoo Finance responses for 5 symbols (one
per business-model template) into JSON files under tests/fixtures/<SYMBOL>/.

Not part of the test suite itself -- run manually to (re)generate fixtures
when the response shape needs updating. Tests load these files and never
call Yahoo (see tests/conftest.py).

Usage:
    python -m tests.fixtures._capture
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.services import yahoo
from app.services.normalize import BALANCE_SHEET_MAP, CASH_FLOW_MAP, INCOME_STATEMENT_MAP

FIXTURES_DIR = Path(__file__).resolve().parent

SYMBOLS = {
    "TCS": "TCS.NS",  # general
    "HDFCBANK": "HDFCBANK.NS",  # bank
    "BAJFINANCE": "BAJFINANCE.NS",  # nbfc
    "HDFCLIFE": "HDFCLIFE.NS",  # insurance
    "BSE": "BSE.NS",  # exchange
}
BENCHMARK_TICKER = "^NSEI"

INCOME_KEYS = list(INCOME_STATEMENT_MAP.keys())
BALANCE_KEYS = list(BALANCE_SHEET_MAP.keys())
CASHFLOW_KEYS = list(CASH_FLOW_MAP.keys())
SHARES_KEYS = yahoo._SHARES_OUTSTANDING_KEYS


async def _capture_chart_raw(yf_ticker: str, range_: str, interval: str) -> dict:
    """Capture the RAW envelope (`{"chart": {"result": [...]}}`), i.e. what
    `_get_json_sync` returns -- NOT `fetch_chart`'s already-unwrapped
    `result[0]`. Fixtures stand in for `_get_json_sync`, so they must keep
    its exact response shape."""
    return await yahoo._run_throttled(
        yahoo._get_json_sync,
        yahoo._CHART_URL.format(ticker=yf_ticker),
        {"range": range_, "interval": interval},
    )


async def _capture_symbol(symbol: str, yf_ticker: str) -> None:
    out_dir = FIXTURES_DIR / symbol
    out_dir.mkdir(parents=True, exist_ok=True)

    chart_5d = await _capture_chart_raw(yf_ticker, "5d", "1d")
    (out_dir / "chart_5d.json").write_text(json.dumps(chart_5d, indent=2), encoding="utf-8")

    chart_1mo = await _capture_chart_raw(yf_ticker, "1mo", "1d")
    (out_dir / "chart_1mo.json").write_text(json.dumps(chart_1mo, indent=2), encoding="utf-8")

    for name, keys, timescale in (
        ("income", INCOME_KEYS, "annual"),
        ("income", INCOME_KEYS, "quarterly"),
        ("balance", BALANCE_KEYS, "annual"),
        ("balance", BALANCE_KEYS, "quarterly"),
        ("cashflow", CASHFLOW_KEYS, "annual"),
        ("cashflow", CASHFLOW_KEYS, "quarterly"),
    ):
        raw = await yahoo._run_throttled(
            yahoo._get_json_sync,
            yahoo._TIMESERIES_URL.format(ticker=yf_ticker),
            {
                "symbol": yf_ticker,
                "type": ",".join(f"{timescale}{k}" for k in keys),
                "period1": str(int(yahoo._FUNDAMENTALS_START.timestamp())),
                "period2": str(int(__import__("time").time())),
            },
        )
        suffix = "annual" if timescale == "annual" else "quarterly"
        (out_dir / f"{name}_{suffix}.json").write_text(
            json.dumps(raw, indent=2), encoding="utf-8"
        )

    shares_raw = await yahoo._run_throttled(
        yahoo._get_json_sync,
        yahoo._TIMESERIES_URL.format(ticker=yf_ticker),
        {
            "symbol": yf_ticker,
            "type": ",".join(f"quarterly{k}" for k in SHARES_KEYS),
            "period1": str(int(yahoo._FUNDAMENTALS_START.timestamp())),
            "period2": str(int(__import__("time").time())),
        },
    )
    (out_dir / "shares_quarterly.json").write_text(
        json.dumps(shares_raw, indent=2), encoding="utf-8"
    )
    print(f"Captured {symbol} -> {out_dir}")


async def main() -> None:
    benchmark_chart = await _capture_chart_raw(BENCHMARK_TICKER, "1mo", "1d")
    (FIXTURES_DIR / "benchmark_chart_1mo.json").write_text(
        json.dumps(benchmark_chart, indent=2), encoding="utf-8"
    )

    for symbol, yf_ticker in SYMBOLS.items():
        await _capture_symbol(symbol, yf_ticker)


if __name__ == "__main__":
    asyncio.run(main())

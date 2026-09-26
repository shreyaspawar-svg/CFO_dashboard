"""Beta vs a benchmark index, computed from historical daily returns --
Yahoo doesn't reliably expose this for NSE tickers (PLAN.md Phase 4 §4.1),
so it's computed here rather than fetched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_MIN_OBSERVATIONS = 30
"""Below this many paired daily returns, a beta estimate is too noisy to
be worth showing -- None instead of a number built on a handful of days."""


def daily_returns(closes: list[float | None]) -> list[float]:
    """Day-over-day % returns (as fractions, e.g. 0.01 for +1%) from a
    close-price series. Skips any pair where either side is missing or
    the prior close is zero, rather than raising.

    Only safe to use on a SINGLE series in isolation. Do not feed two
    series' outputs into `compute_beta` directly -- see `paired_daily_returns`
    for why (PLAN.md "Phase 4.1 review" item 2)."""
    returns: list[float] = []
    for prev, curr in zip(closes, closes[1:]):
        if prev is None or curr is None or prev == 0:
            continue
        returns.append((curr - prev) / prev)
    return returns


def _bar_date(bar: dict[str, Any]) -> str | None:
    raw = bar.get("Date") or bar.get("date")
    if raw is None:
        return None
    if hasattr(raw, "date"):
        return raw.date().isoformat()
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc).date().isoformat()
    return str(raw)[:10]


def _closes_by_date(bars: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for bar in bars:
        d = _bar_date(bar)
        close = bar.get("Close") if "Close" in bar else bar.get("close")
        if d is None or close is None:
            continue
        out[d] = close
    return out


def paired_daily_returns(
    symbol_bars: list[dict[str, Any]], benchmark_bars: list[dict[str, Any]]
) -> tuple[list[float], list[float]]:
    """Day-over-day returns for both series, paired by shared trading DATE
    rather than list position.

    `compute_beta` used to receive two independently-built return lists and
    zip them by trailing position. That's only safe if both series skip
    exactly the same days for exactly the same reason -- untrue in practice:
    a real check against live TCS/`^NSEI` data found `^NSEI`'s own chart
    feed has scattered null closes (5 in the last year) on days TCS trades
    fine. Each null drops two of `^NSEI`'s daily-return entries (the pair
    before and after it) without dropping any of TCS's, so from the first
    null onward every subsequent "same position" pair was actually comparing
    different calendar days -- washing out real covariance and producing
    the implausibly-low betas (~0.06-0.19x) flagged in PLAN.md "Phase 4.1
    review" item 2, across every symbol tested, not just one.

    This builds a date -> close map per series (silently dropping that
    series' own null days), keeps only dates present in both, and computes
    each series' return only across consecutive shared dates -- so a day
    dropped by one series can no longer shift the other series' pairing.
    """
    symbol_closes = _closes_by_date(symbol_bars)
    benchmark_closes = _closes_by_date(benchmark_bars)
    common_dates = sorted(set(symbol_closes) & set(benchmark_closes))

    symbol_returns: list[float] = []
    benchmark_returns: list[float] = []
    for prev, curr in zip(common_dates, common_dates[1:]):
        s_prev, s_curr = symbol_closes[prev], symbol_closes[curr]
        b_prev, b_curr = benchmark_closes[prev], benchmark_closes[curr]
        if s_prev == 0 or b_prev == 0:
            continue
        symbol_returns.append((s_curr - s_prev) / s_prev)
        benchmark_returns.append((b_curr - b_prev) / b_prev)
    return symbol_returns, benchmark_returns


def compute_beta(symbol_returns: list[float], benchmark_returns: list[float]) -> float | None:
    """Beta = Cov(symbol, benchmark) / Var(benchmark), over the longest
    common trailing window of the two return series (they may differ in
    length if one series has more gaps). None if there's too little
    overlapping data or the benchmark had zero variance (a degenerate,
    not a real, market)."""
    n = min(len(symbol_returns), len(benchmark_returns))
    if n < _MIN_OBSERVATIONS:
        return None

    sr = symbol_returns[-n:]
    br = benchmark_returns[-n:]
    mean_sr = sum(sr) / n
    mean_br = sum(br) / n

    covariance = sum((sr[i] - mean_sr) * (br[i] - mean_br) for i in range(n)) / n
    variance = sum((x - mean_br) ** 2 for x in br) / n
    if variance == 0:
        return None
    return covariance / variance

"""Direct Yahoo Finance HTTP client built on curl_cffi (browser TLS
impersonation), with concurrency throttling and retry.

We deliberately do NOT use yfinance's `Ticker` class for live requests: in
testing, yfinance's built-in cookie/crumb negotiation gets stuck reusing a
poisoned crumb value once Yahoo rate-limits it, so every subsequent call
fails with HTTP 429 for the rest of the process's life. curl_cffi's browser
impersonation avoids Yahoo's TLS-fingerprint blocking, and the chart and
fundamentals-timeseries endpoints work without a crumb at all; only
quote-summary (used only for market cap / news) needs one, fetched
best-effort with graceful fallback to `None`/`[]`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from curl_cffi import requests as cffi_requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger("app.services.yahoo")

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_TIMESERIES_URL = (
    "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{ticker}"
)
_QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
_COOKIE_SEED_URL = "https://fc.yahoo.com"

_FUNDAMENTALS_START = datetime(2016, 12, 31, tzinfo=timezone.utc)

_session: cffi_requests.Session | None = None
_crumb: str | None = None
_state_lock = Lock()
_semaphore: asyncio.Semaphore | None = None


class YahooError(Exception):
    """Raised for transient Yahoo failures (rate limit, 5xx, bad payload)."""


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().yahoo_max_concurrency)
    return _semaphore


def _get_session() -> cffi_requests.Session:
    global _session
    with _state_lock:
        if _session is not None:
            return _session
        session = cffi_requests.Session(impersonate="chrome")
        try:
            session.get(_COOKIE_SEED_URL, timeout=15)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to seed Yahoo cookie: %s", exc)
        _session = session
        return _session


def _get_crumb() -> str | None:
    global _crumb
    with _state_lock:
        if _crumb is not None:
            return _crumb
    session = _get_session()
    try:
        resp = session.get(_CRUMB_URL, timeout=15)
        text = resp.text.strip()
        looks_valid = (
            resp.status_code == 200
            and text
            and "Too Many Requests" not in text
            and "<html" not in text.lower()
        )
        if looks_valid:
            with _state_lock:
                _crumb = text
            return text
        logger.warning("Yahoo crumb fetch returned unusable payload: %r", text[:80])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch Yahoo crumb: %s", exc)
    return None


def _retry_decorator():
    settings = get_settings()
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.yahoo_retry_attempts),
        wait=wait_exponential(multiplier=settings.yahoo_retry_backoff_seconds),
        retry=retry_if_exception_type(YahooError),
    )


def _get_json_sync(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    session = _get_session()
    resp = session.get(url, params=params, timeout=20)
    if resp.status_code == 429:
        raise YahooError(f"429 rate-limited: {url}")
    if resp.status_code >= 500:
        raise YahooError(f"{resp.status_code} server error: {url}")
    try:
        return resp.json()
    except ValueError as exc:
        raise YahooError(
            f"Non-JSON response (status {resp.status_code}) from {url}: {exc}"
        ) from None


async def _run_throttled(fn, *args, **kwargs) -> Any:
    async with _get_semaphore():
        decorated = _retry_decorator()(fn)
        return await asyncio.to_thread(decorated, *args, **kwargs)


# --------------------------------------------------------------------------
# Chart endpoint: powers both quote (via `meta`) and history (via candles).
# Works without a crumb.
# --------------------------------------------------------------------------


def _chart_sync(
    yf_ticker: str, range_: str, interval: str, events: str | None = None
) -> dict[str, Any]:
    params = {"range": range_, "interval": interval}
    if events:
        params["events"] = events
    data = _get_json_sync(_CHART_URL.format(ticker=yf_ticker), params=params)
    chart = data.get("chart", {})
    error = chart.get("error")
    if error:
        raise YahooError(f"Yahoo chart error for {yf_ticker}: {error}")
    results = chart.get("result") or []
    if not results:
        return {}
    return results[0]


async def fetch_chart(
    yf_ticker: str, range_: str = "1y", interval: str = "1d", events: str | None = None
) -> dict[str, Any]:
    return await _run_throttled(_chart_sync, yf_ticker, range_, interval, events)


def _bars_from_chart(chart: dict[str, Any]) -> list[dict[str, Any]]:
    timestamps = chart.get("timestamp") or []
    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    bars: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        date = datetime.fromtimestamp(ts, tz=timezone.utc)
        bars.append(
            {
                "Date": date,
                "Open": opens[i] if i < len(opens) else None,
                "High": highs[i] if i < len(highs) else None,
                "Low": lows[i] if i < len(lows) else None,
                "Close": closes[i] if i < len(closes) else None,
                "Volume": volumes[i] if i < len(volumes) else None,
            }
        )
    return bars


async def fetch_history(
    yf_ticker: str, period: str = "1y", interval: str = "1d"
) -> list[dict[str, Any]]:
    chart = await fetch_chart(yf_ticker, range_=period, interval=interval)
    return _bars_from_chart(chart)


async def fetch_fast_info(yf_ticker: str) -> dict[str, Any]:
    """Quote-ish fields derived from the chart endpoint's `meta` block, plus
    today's open from the most recent daily bar. No crumb required."""
    chart = await fetch_chart(yf_ticker, range_="5d", interval="1d")
    meta = chart.get("meta") or {}
    bars = _bars_from_chart(chart)
    last_open = bars[-1]["Open"] if bars else None

    last_price = meta.get("regularMarketPrice")
    change = meta.get("fulldayChange")
    prev_close = (
        last_price - change if last_price is not None and change is not None else None
    )

    return {
        "last_price": last_price,
        "open": last_open,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "previous_close": prev_close,
        "volume": meta.get("regularMarketVolume"),
        "year_high": meta.get("fiftyTwoWeekHigh"),
        "year_low": meta.get("fiftyTwoWeekLow"),
        "market_cap": None,  # requires quoteSummary; see fetch_market_cap
        "currency": meta.get("currency"),
    }


_SHARES_OUTSTANDING_KEYS = ["OrdinarySharesNumber", "ShareIssued"]


async def fetch_shares_outstanding_detailed(
    yf_ticker: str,
) -> tuple[float | None, str | None]:
    """Most recent share count, preferring quarterly (fresher) over annual.
    Tries OrdinarySharesNumber then ShareIssued, per period, newest first.

    Returns (shares, as_of_date). `as_of_date` (the record's period-end) is
    kept for callers that want it, but `fetch_market_cap_detailed` does NOT
    use it to split-adjust the share count -- see that function's docstring
    for why (Yahoo's share count is already current, not point-in-time, for
    a company that's had a split).
    """
    for quarterly in (True, False):
        try:
            records = await _fetch_fundamentals(
                yf_ticker, _SHARES_OUTSTANDING_KEYS, quarterly
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "shares-outstanding fetch failed for %s (quarterly=%s): %s",
                yf_ticker,
                quarterly,
                exc,
            )
            continue
        for record in reversed(records):  # newest last per reshape's sort
            for key in _SHARES_OUTSTANDING_KEYS:
                value = record.get(key)
                if value is not None:
                    return float(value), record.get("index")
    return None, None


async def fetch_shares_outstanding(yf_ticker: str) -> float | None:
    shares, _as_of = await fetch_shares_outstanding_detailed(yf_ticker)
    return shares


async def _fetch_market_cap_via_quote_summary(yf_ticker: str) -> float | None:
    """Cross-check only: needs a working crumb, which Yahoo issues
    inconsistently. Returns None (never 0) on any failure."""
    crumb = _get_crumb()
    if crumb is None:
        return None
    try:
        data = await _run_throttled(
            _get_json_sync,
            _QUOTE_SUMMARY_URL.format(ticker=yf_ticker),
            {"modules": "price", "crumb": crumb},
        )
        result = (data.get("quoteSummary") or {}).get("result") or []
        if not result:
            return None
        market_cap = ((result[0].get("price") or {}).get("marketCap") or {}).get("raw")
        return float(market_cap) if market_cap is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("quoteSummary market cap cross-check failed for %s: %s", yf_ticker, exc)
        return None


async def fetch_key_statistics(yf_ticker: str) -> dict[str, float | None]:
    """Yahoo's own already-computed ROE/ROA/book-value/EPS, from the
    crumb-gated quoteSummary `financialData` + `defaultKeyStatistics`
    modules. PLAN.md "Phase 2 review": our own fundamentals-timeseries-
    derived book value for HDFCBANK (Rs530/share) diverged 36% from
    Screener.in (Rs390); this endpoint's `bookValue` (Rs393.81) and
    `returnOnEquity` (13.84%) match Screener almost exactly, and turned out
    to be the actual fix -- not a minority-interest mapping bug (Yahoo's
    StockholdersEquity already excludes it) and not the 2025 bonus issue
    (Yahoo's share count already reflects it). Best-effort: any/all fields
    come back None if the crumb isn't available or a module lacks data for
    this symbol (e.g. `returnOnEquity` is commonly absent even when
    `bookValue` is present)."""
    crumb = _get_crumb()
    if crumb is None:
        return {
            "roe_pct": None,
            "roa_pct": None,
            "book_value_per_share": None,
            "trailing_eps": None,
        }
    try:
        data = await _run_throttled(
            _get_json_sync,
            _QUOTE_SUMMARY_URL.format(ticker=yf_ticker),
            {"modules": "financialData,defaultKeyStatistics", "crumb": crumb},
        )
        result = (data.get("quoteSummary") or {}).get("result") or []
        if not result:
            return {
                "roe_pct": None,
                "roa_pct": None,
                "book_value_per_share": None,
                "trailing_eps": None,
            }
        financial_data = result[0].get("financialData") or {}
        key_stats = result[0].get("defaultKeyStatistics") or {}

        def _raw(module: dict, field: str) -> float | None:
            value = (module.get(field) or {}).get("raw")
            return float(value) if value is not None else None

        roe = _raw(financial_data, "returnOnEquity")
        roa = _raw(financial_data, "returnOnAssets")
        return {
            "roe_pct": roe * 100 if roe is not None else None,
            "roa_pct": roa * 100 if roa is not None else None,
            "book_value_per_share": _raw(key_stats, "bookValue"),
            "trailing_eps": _raw(key_stats, "trailingEps"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("key-statistics fetch failed for %s: %s", yf_ticker, exc)
        return {
            "roe_pct": None,
            "roa_pct": None,
            "book_value_per_share": None,
            "trailing_eps": None,
        }


_EMPTY_ANALYST_TARGET: dict[str, float | str | None] = {
    "target_mean_price": None,
    "target_high_price": None,
    "target_low_price": None,
    "number_of_analysts": None,
    "recommendation": None,
}


async def fetch_analyst_target(yf_ticker: str) -> dict[str, float | str | None]:
    """Analyst mean/high/low target price and consensus recommendation
    (PLAN.md Phase 4 §4.1), from the same crumb-gated `financialData`
    module `fetch_key_statistics` uses. Best-effort: all fields come back
    None if the crumb isn't available or the symbol has no analyst
    coverage."""
    crumb = _get_crumb()
    if crumb is None:
        return dict(_EMPTY_ANALYST_TARGET)
    try:
        data = await _run_throttled(
            _get_json_sync,
            _QUOTE_SUMMARY_URL.format(ticker=yf_ticker),
            {"modules": "financialData", "crumb": crumb},
        )
        result = (data.get("quoteSummary") or {}).get("result") or []
        if not result:
            return dict(_EMPTY_ANALYST_TARGET)
        financial_data = result[0].get("financialData") or {}

        def _raw(field: str) -> float | None:
            value = (financial_data.get(field) or {}).get("raw")
            return float(value) if value is not None else None

        return {
            "target_mean_price": _raw("targetMeanPrice"),
            "target_high_price": _raw("targetHighPrice"),
            "target_low_price": _raw("targetLowPrice"),
            "number_of_analysts": _raw("numberOfAnalystOpinions"),
            "recommendation": financial_data.get("recommendationKey"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("analyst-target fetch failed for %s: %s", yf_ticker, exc)
        return dict(_EMPTY_ANALYST_TARGET)


async def fetch_market_cap_detailed(
    yf_ticker: str, last_price: float | None
) -> tuple[float | None, str, float | None]:
    """Primary: price x shares outstanding, from fundamentals data (no crumb
    needed, so always available once a company has reported shares).

    We do NOT apply our own split/bonus adjustment here, despite PLAN.md
    "Phase 1.5 review" item 1 assuming (reasonably, but incorrectly) that
    the share count is a stale, period-end balance-sheet figure that goes
    out of sync with a live price after a split. Empirically it is not: for
    TRENT (a real 3:2 split on 2026-06-04) and NESTLEIND (a real 2:1 split
    on 2025-08-08), `OrdinarySharesNumber` is IDENTICAL across every annual
    period Yahoo returns, including years before either split -- Yahoo
    normalizes this field to the current, already-post-split count
    regardless of which period it's attached to (unlike a company with no
    recent split, e.g. RELIANCE or SHRIRAMFIN, whose share count genuinely
    varies period to period from buybacks/ESOPs/issuances). Multiplying by
    our own split ratio on top of an already-current count double-counted
    the split and overstated TRENT's and NESTLEIND's market cap by exactly
    their split ratio (50% and 100% -- caught via the >5% quoteSummary
    cross-check in Phase 2's Screener.in spot-check). `services.yahoo`
    still exposes `fetch_splits`/`metrics.shares.adjust_shares_for_splits`
    for a genuinely point-in-time share-count source (e.g. a future paid
    feed), just not for this one.

    quoteSummary is used only to cross-check -- it is NOT relied on, since
    Yahoo issues a working crumb inconsistently.

    Returns (market_cap, method, divergence_pct), where method is one of
    "price_x_shares", "quote_summary_fallback", "unavailable", and
    divergence_pct is how far the price x shares figure differs from
    quoteSummary's (None if either side is unavailable) -- surfaced so
    >5% divergences can be listed in the coverage report (item 5), not just
    logged.
    """
    shares, _shares_as_of = await fetch_shares_outstanding_detailed(yf_ticker)
    primary = last_price * shares if last_price is not None and shares is not None else None

    cross_check = await _fetch_market_cap_via_quote_summary(yf_ticker)
    divergence_pct = None
    if primary is not None and cross_check is not None and cross_check != 0:
        divergence_pct = abs(primary - cross_check) / cross_check * 100
        if divergence_pct > 5:
            logger.warning(
                "%s: market cap price*shares (%.0f) diverges %.1f%% from "
                "quoteSummary (%.0f)",
                yf_ticker,
                primary,
                divergence_pct,
                cross_check,
            )

    if primary is not None:
        return primary, "price_x_shares", divergence_pct
    if cross_check is not None:
        return cross_check, "quote_summary_fallback", divergence_pct
    return None, "unavailable", divergence_pct


async def fetch_market_cap(yf_ticker: str, last_price: float | None) -> float | None:
    market_cap, _method, _divergence = await fetch_market_cap_detailed(yf_ticker, last_price)
    return market_cap


async def fetch_splits(yf_ticker: str) -> list[dict[str, Any]]:
    """Stock splits and bonus issues (Yahoo represents both the same way:
    a numerator:denominator share-multiplication ratio), oldest first."""
    chart = await fetch_chart(yf_ticker, range_="10y", interval="1mo", events="splits")
    splits = ((chart.get("events") or {}).get("splits")) or {}
    out = []
    for point in splits.values():
        ts = point.get("date")
        numerator = point.get("numerator")
        denominator = point.get("denominator")
        if ts is None or numerator is None or denominator is None:
            continue
        out.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                "numerator": float(numerator),
                "denominator": float(denominator),
            }
        )
    out.sort(key=lambda s: s["date"])
    return out


async def fetch_dividends(yf_ticker: str) -> list[dict[str, Any]]:
    chart = await fetch_chart(yf_ticker, range_="10y", interval="1mo", events="div")
    dividends = ((chart.get("events") or {}).get("dividends")) or {}
    out = []
    for point in dividends.values():
        ts = point.get("date")
        amount = point.get("amount")
        if ts is None or amount is None:
            continue
        out.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                "amount": float(amount),
            }
        )
    out.sort(key=lambda d: d["date"])
    return out


_GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


def _google_news_rss_sync(company_name: str) -> list[dict[str, Any]]:
    """Google News RSS filtered by company name -- no crumb/auth needed.
    Fallback for the many NSE-listed symbols Yahoo's own search index has
    little or no news for (a live check found it returns 0 results for a
    literal ticker query, and for most company names too -- e.g. "Tata
    Consultancy Services" -- while a few return only US-ADR-flavoured
    global market chatter, not NSE-specific coverage)."""
    from email.utils import parsedate_to_datetime
    from xml.etree import ElementTree

    session = _get_session()
    params = {"q": company_name, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    resp = session.get(_GOOGLE_NEWS_RSS_URL, params=params, timeout=15)
    if resp.status_code != 200:
        raise YahooError(f"Google News RSS {resp.status_code} for {company_name!r}")

    root = ElementTree.fromstring(resp.text)
    items: list[dict[str, Any]] = []
    for item in root.findall("./channel/item")[:10]:
        title_raw = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title_raw or not link:
            continue
        source_el = item.find("source")
        publisher = source_el.text.strip() if source_el is not None and source_el.text else None
        # Google News titles are "<headline> - <publisher>"; strip the
        # trailing publisher tag so it isn't shown twice in the UI.
        title = title_raw
        if publisher and title_raw.endswith(f" - {publisher}"):
            title = title_raw[: -(len(publisher) + 3)].strip()
        publish_time: int | None = None
        pub_date_raw = item.findtext("pubDate")
        if pub_date_raw:
            try:
                publish_time = int(parsedate_to_datetime(pub_date_raw).timestamp())
            except (TypeError, ValueError):
                publish_time = None
        items.append(
            {"title": title, "link": link, "publisher": publisher, "providerPublishTime": publish_time}
        )
    return items


async def fetch_news(yf_ticker: str, company_name: str) -> list[dict[str, Any]]:
    """Best-effort headline search: Yahoo's own search/news endpoint first
    (same curl_cffi session as everything else, no crumb needed), falling
    back to Google News RSS filtered by company name whenever Yahoo comes
    back empty. Returns [] only if both sources fail/are empty -- news is
    a nice-to-have (Phase 4+ Events tab), never worth raising over."""
    try:
        data = await _run_throttled(
            _get_json_sync, _SEARCH_URL, {"q": company_name, "newsCount": 10, "quotesCount": 0}
        )
        news = list(data.get("news") or [])
        if news:
            return news
    except Exception as exc:  # noqa: BLE001
        logger.warning("Yahoo news search failed for %s: %s", yf_ticker, exc)

    try:
        return await _run_throttled(_google_news_rss_sync, company_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google News RSS fallback failed for %s: %s", yf_ticker, exc)
        return []


# --------------------------------------------------------------------------
# Fundamentals-timeseries: powers income statement / balance sheet / cash
# flow. Works without a crumb.
# --------------------------------------------------------------------------


def reshape_fundamentals_timeseries(
    data: dict[str, Any], keys: list[str], timescale: str
) -> list[dict[str, Any]]:
    """Flatten Yahoo's fundamentals-timeseries payload -- one entry per
    requested field, each holding its own list of {asOfDate, reportedValue}
    points -- into one record per period, keyed by field name."""
    result = ((data.get("timeseries") or {}).get("result")) or []

    by_date: dict[str, dict[str, Any]] = {}
    for entry in result:
        for full_key, series in entry.items():
            if full_key == "meta" or not series:
                continue
            if not full_key.startswith(timescale):
                continue
            field = full_key[len(timescale) :]
            if field not in keys:
                continue
            for point in series:
                if not point:
                    continue
                as_of_date = point.get("asOfDate")
                reported = (point.get("reportedValue") or {}).get("raw")
                if as_of_date is None:
                    continue
                by_date.setdefault(as_of_date, {"index": as_of_date})[field] = reported

    return [by_date[date] for date in sorted(by_date)]


def _fundamentals_timeseries_sync(
    yf_ticker: str, keys: list[str], timescale: str
) -> list[dict[str, Any]]:
    type_params = ",".join(f"{timescale}{key}" for key in keys)
    params = {
        "symbol": yf_ticker,
        "type": type_params,
        "period1": str(int(_FUNDAMENTALS_START.timestamp())),
        "period2": str(int(time.time())),
    }
    data = _get_json_sync(_TIMESERIES_URL.format(ticker=yf_ticker), params=params)
    return reshape_fundamentals_timeseries(data, keys, timescale)


async def _fetch_fundamentals(
    yf_ticker: str, keys: list[str], quarterly: bool
) -> list[dict[str, Any]]:
    timescale = "quarterly" if quarterly else "annual"
    return await _run_throttled(_fundamentals_timeseries_sync, yf_ticker, keys, timescale)


async def fetch_income_stmt(yf_ticker: str, quarterly: bool = False) -> list[dict[str, Any]]:
    from app.services.normalize import INCOME_STATEMENT_MAP

    return await _fetch_fundamentals(yf_ticker, list(INCOME_STATEMENT_MAP.keys()), quarterly)


async def fetch_balance_sheet(yf_ticker: str, quarterly: bool = False) -> list[dict[str, Any]]:
    from app.services.normalize import BALANCE_SHEET_MAP

    return await _fetch_fundamentals(yf_ticker, list(BALANCE_SHEET_MAP.keys()), quarterly)


async def fetch_cashflow(yf_ticker: str, quarterly: bool = False) -> list[dict[str, Any]]:
    from app.services.normalize import CASH_FLOW_MAP

    return await _fetch_fundamentals(yf_ticker, list(CASH_FLOW_MAP.keys()), quarterly)

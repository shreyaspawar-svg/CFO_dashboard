from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.metrics.ratios import dividend_yield
from app.models.schemas import DividendEvent, EventsResponse, SplitEvent
from app.services.cache import get_cache
from app.services.datasource import get_data_source
from app.services.nse import fetch_shareholding_pattern
from app.services.universe import get_company

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events/{symbol}", response_model=EventsResponse)
async def get_events(symbol: str) -> EventsResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    cache_key = f"events:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return EventsResponse(**cached)

    data_source = get_data_source()
    warnings: list[str] = []

    try:
        dividends_raw = await data_source.get_dividends(company.yf_ticker)
    except Exception as exc:  # noqa: BLE001
        dividends_raw = []
        warnings.append(f"Dividends fetch failed: {exc}")

    try:
        splits_raw = await data_source.get_splits(company.yf_ticker)
    except Exception as exc:  # noqa: BLE001
        splits_raw = []
        warnings.append(f"Splits fetch failed: {exc}")

    news_cache_key = f"news:{company.symbol}"
    news_raw = cache.get(news_cache_key)
    if news_raw is None:
        try:
            news_raw = await data_source.get_news(company.yf_ticker, company.name)
        except Exception as exc:  # noqa: BLE001
            news_raw = []
            warnings.append(f"News fetch failed: {exc}")
        cache.set(news_cache_key, news_raw, settings.ttl_news)

    try:
        fast_info = await data_source.get_fast_info(company.yf_ticker)
        current_price = fast_info.get("last_price")
    except Exception:  # noqa: BLE001
        current_price = None

    # PLAN.md §4 Task D.5: one attempt at NSE's public shareholding-pattern
    # endpoint (see app/services/nse.py) -- NSE blocks this deployment's IP
    # on every /api/ data endpoint tried (403 Access Denied), same as the
    # already-documented block on other NSE endpoints.
    shareholding = await fetch_shareholding_pattern(company.symbol)
    if shareholding is None:
        warnings.append("Shareholding (promoter/FII/DII) not available from free sources (NSE blocks this deployment's IP)")

    # Not available from this free data source (PLAN.md §3 "Shareholding &
    # Events" calls for the next earnings date; it needs a crumb-gated
    # Yahoo endpoint we don't rely on).
    warnings.append("Upcoming earnings date unavailable: requires a Yahoo crumb we don't rely on")

    response = EventsResponse(
        symbol=company.symbol,
        dividends=[
            DividendEvent(**d, yield_pct=dividend_yield(d.get("amount"), current_price)) for d in dividends_raw
        ],
        splits=[SplitEvent(**s) for s in splits_raw],
        news=news_raw[:10],
        shareholding=shareholding,
        next_earnings_date=None,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

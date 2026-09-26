from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import DividendEvent, EventsResponse, SplitEvent
from app.services.cache import get_cache
from app.services.datasource import get_data_source
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

    try:
        news_raw = await data_source.get_news(company.yf_ticker)
    except Exception as exc:  # noqa: BLE001
        news_raw = []
        warnings.append(f"News fetch failed: {exc}")

    # Not available from this free data source (PLAN.md §3 "Shareholding &
    # Events" calls for promoter/FII/DII trend and the next earnings date;
    # NSE would supply the former but blocks datacenter IPs with a 403, and
    # the latter needs a crumb-gated Yahoo endpoint we don't rely on).
    warnings.append("Shareholding (promoter/FII/DII) unavailable: NSE blocks this deployment's IP")
    warnings.append("Upcoming earnings date unavailable: requires a Yahoo crumb we don't rely on")

    response = EventsResponse(
        symbol=company.symbol,
        dividends=[DividendEvent(**d) for d in dividends_raw],
        splits=[SplitEvent(**s) for s in splits_raw],
        news=news_raw,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

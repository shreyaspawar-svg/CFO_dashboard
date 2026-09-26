from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.schemas import QuoteResponse
from app.services.cache import get_cache
from app.services.datasource import get_data_source
from app.services.market import market_status
from app.services.normalize import CRORE, clean_numeric
from app.services.universe import get_company

router = APIRouter(prefix="/api", tags=["quote"])


async def _build_quote(symbol: str) -> QuoteResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    status = market_status()
    ttl = (
        settings.ttl_quote_market_hours
        if status == "open"
        else settings.ttl_quote_closed
    )

    cache = get_cache()
    cache_key = f"quote:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return QuoteResponse(**cached)

    data_source = get_data_source()
    warnings: list[str] = []
    try:
        info = await data_source.get_fast_info(company.yf_ticker)
    except Exception as exc:  # noqa: BLE001 - surfaced as a warning, not a 500
        info = {}
        warnings.append(f"Yahoo fetch failed: {exc}")

    last_price = clean_numeric(info.get("last_price"))
    prev_close = clean_numeric(info.get("previous_close"))
    change = (
        last_price - prev_close if last_price is not None and prev_close is not None else None
    )
    change_pct = (
        (change / prev_close * 100)
        if change is not None and prev_close not in (None, 0)
        else None
    )

    market_cap_raw = await data_source.get_market_cap(company.yf_ticker, last_price)
    if market_cap_raw is None:
        warnings.append(
            "Market cap unavailable: no shares-outstanding data and no quoteSummary crumb"
        )
    market_cap = clean_numeric(market_cap_raw)

    response = QuoteResponse(
        symbol=company.symbol,
        yf_ticker=company.yf_ticker,
        last_price=last_price,
        change=change,
        change_pct=change_pct,
        open=clean_numeric(info.get("open")),
        day_high=clean_numeric(info.get("day_high")),
        day_low=clean_numeric(info.get("day_low")),
        prev_close=prev_close,
        volume=int(v) if (v := clean_numeric(info.get("volume"))) is not None else None,
        week52_high=clean_numeric(info.get("year_high")),
        week52_low=clean_numeric(info.get("year_low")),
        market_cap=market_cap / CRORE if market_cap is not None else None,
        market_status=status,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    cache.set(cache_key, response.model_dump(mode="json"), ttl)
    return response


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(symbol: str) -> QuoteResponse:
    return await _build_quote(symbol)


@router.get("/quotes", response_model=list[QuoteResponse])
async def get_quotes(symbols: str = Query(..., description="Comma-separated symbols")) -> list[QuoteResponse]:
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return [await _build_quote(symbol) for symbol in symbol_list]

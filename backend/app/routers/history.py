from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.models.schemas import HistoryResponse, OHLCVBar
from app.services.cache import get_cache
from app.services.datasource import get_data_source
from app.services.normalize import clean_numeric
from app.services.universe import get_company

router = APIRouter(prefix="/api", tags=["history"])

_VALID_RANGES = {"1d", "5d", "1mo", "6mo", "1y", "5y", "max"}
_INTRADAY_RANGES = {"1d", "5d"}
BENCHMARK_TICKER = "^NSEI"


def _bars_from_records(records: list[dict[str, Any]]) -> list[OHLCVBar]:
    bars: list[OHLCVBar] = []
    for record in records:
        date_raw = record.get("Date") or record.get("Datetime") or record.get("index")
        if date_raw is None:
            continue
        date_str = date_raw.isoformat() if hasattr(date_raw, "isoformat") else str(date_raw)
        volume = clean_numeric(record.get("Volume"))
        bars.append(
            OHLCVBar(
                date=date_str,
                open=clean_numeric(record.get("Open")),
                high=clean_numeric(record.get("High")),
                low=clean_numeric(record.get("Low")),
                close=clean_numeric(record.get("Close")),
                volume=int(volume) if volume is not None else None,
            )
        )
    return bars


@router.get("/history/{symbol}", response_model=HistoryResponse)
async def get_history(
    symbol: str,
    range: str = Query("1y", alias="range"),
    interval: str = Query("1d"),
) -> HistoryResponse:
    if range not in _VALID_RANGES:
        raise HTTPException(status_code=400, detail=f"Unsupported range: {range}")

    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    ttl = (
        settings.ttl_history_intraday
        if range in _INTRADAY_RANGES
        else settings.ttl_history_daily
    )
    cache = get_cache()
    cache_key = f"history:{company.symbol}:{range}:{interval}"
    cached = cache.get(cache_key)
    if cached is not None:
        return HistoryResponse(**cached)

    data_source = get_data_source()
    warnings: list[str] = []
    try:
        records = await data_source.get_history_bars(company.yf_ticker, range_=range, interval=interval)
    except Exception as exc:  # noqa: BLE001
        records = []
        warnings.append(f"Yahoo fetch failed: {exc}")

    benchmark_bars: list[OHLCVBar] = []
    try:
        benchmark_records = await data_source.get_history_bars(
            BENCHMARK_TICKER, range_=range, interval=interval
        )
        benchmark_bars = _bars_from_records(benchmark_records)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"NIFTY 50 benchmark fetch failed: {exc}")

    response = HistoryResponse(
        symbol=company.symbol,
        range=range,
        interval=interval,
        bars=_bars_from_records(records),
        benchmark_bars=benchmark_bars,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    cache.set(cache_key, response.model_dump(mode="json"), ttl)
    return response

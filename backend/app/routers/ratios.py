import statistics
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.metrics.scoring import METRIC_HIGHER_IS_BETTER, health_radar, percentile_rank
from app.models.schemas import AxisComponent, AxisResult, RatiosResponse, RatioValue
from app.services.cache import get_cache
from app.services.metrics_engine import compute_symbol_metrics
from app.services.peer_stats import compute_peer_metric_values
from app.services.universe import get_company

router = APIRouter(prefix="/api", tags=["ratios"])


@router.get("/ratios/{symbol}", response_model=RatiosResponse)
async def get_ratios(symbol: str) -> RatiosResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    cache_key = f"ratios:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return RatiosResponse(**cached)

    own = await compute_symbol_metrics(company.symbol)
    peer_data = await compute_peer_metric_values(company.symbol)
    peer_values = peer_data["peer_values"]

    ratios: dict[str, RatioValue] = {}
    for key, value in own["metrics"].items():
        values_list = peer_values.get(key, [])
        valid_values = [v for v in values_list if v is not None]
        median = statistics.median(valid_values) if valid_values else None
        higher_is_better = METRIC_HIGHER_IS_BETTER.get(key, True)
        percentile = percentile_rank(value, values_list, higher_is_better)
        ratios[key] = RatioValue(value=value, peer_median=median, percentile=percentile)

    radar = health_radar(company.template, own["metrics"], peer_values)
    health_radar_response = {
        axis: AxisResult(
            score=result["score"],
            components=[AxisComponent(**c) for c in result["components"]],
        )
        for axis, result in radar.items()
    }

    response = RatiosResponse(
        symbol=company.symbol,
        template=company.template,
        peer_basis=peer_data["basis"],
        peer_count=len(peer_data["peer_symbols"]),
        comparable_annual_years=own["comparable_annual_years"],
        growth_note=own["growth_note"],
        ratios=ratios,
        health_radar=health_radar_response,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=own["warnings"],
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

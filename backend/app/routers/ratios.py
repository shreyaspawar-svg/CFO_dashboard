import statistics
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.metrics.scoring import METRIC_HIGHER_IS_BETTER, health_radar, percentile_rank
from app.metrics.signals import strengths_and_watchouts
from app.models.schemas import (
    AxisComponent,
    AxisResult,
    QualityScores,
    RatioHistoryPoint,
    RatiosResponse,
    RatioValue,
    Signal,
)
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
        method = own["method"].get(key, "computed" if value is not None else "unavailable")
        quality_reason = own["data_quality"].get(key)
        ratios[key] = RatioValue(
            value=value,
            peer_median=median,
            peer_min=min(valid_values) if valid_values else None,
            peer_max=max(valid_values) if valid_values else None,
            percentile=percentile,
            method=method,
            data_quality="inconsistent" if quality_reason else "ok",
            data_quality_reason=quality_reason,
            reason=own["reasons"].get(key),
            direction="higher_better" if higher_is_better else "lower_better",
        )

    history_response = {
        key: [RatioHistoryPoint(**point) for point in points] for key, points in own["history"].items()
    }
    signals = [
        Signal(**s)
        for s in strengths_and_watchouts(own["metrics"], own["history"], peer_values, company.template)
    ]

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
        history=history_response,
        dupont_kind=own["dupont_kind"],
        dupont_reconciliation_gap_pp=own["dupont_reconciliation_gap_pp"],
        signals=signals,
        quality_scores=QualityScores(**own["quality_scores"]) if own["quality_scores"] else None,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=own["warnings"],
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

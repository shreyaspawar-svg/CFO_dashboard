"""The 20-KPI CFO scorecard, quarter-over-quarter (RIL single-company
pivot). See `app.services.kpi_scorecard_engine` for the computation and
which of the 20 KPIs are actually derivable from this free data source.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import KpiScorecardResponse
from app.services.cache import get_cache
from app.services.kpi_scorecard_engine import compute_kpi_scorecard
from app.services.universe import get_company

router = APIRouter(prefix="/api", tags=["kpi-scorecard"])


@router.get("/kpi-scorecard/{symbol}", response_model=KpiScorecardResponse)
async def get_kpi_scorecard(symbol: str) -> KpiScorecardResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    cache_key = f"kpi_scorecard:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return KpiScorecardResponse(**cached)

    result = await compute_kpi_scorecard(company.symbol)
    response = KpiScorecardResponse(**result)
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

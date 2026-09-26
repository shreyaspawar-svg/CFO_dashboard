import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import PeerRow, PeersResponse
from app.services.cache import get_cache
from app.services.metrics_engine import compute_symbol_metrics
from app.services.universe import get_company, peer_group_for_symbol

router = APIRouter(prefix="/api", tags=["peers"])


@router.get("/peers/{symbol}", response_model=PeersResponse)
async def get_peers(symbol: str) -> PeersResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    cache_key = f"peers:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return PeersResponse(**cached)

    peer_companies, basis = peer_group_for_symbol(company.symbol)
    warnings: list[str] = []

    results = await asyncio.gather(
        *(compute_symbol_metrics(c.symbol) for c in peer_companies)
    )

    rows: list[PeerRow] = []
    for peer_company, result in zip(peer_companies, results):
        quote = result.get("quote")
        last_price = quote.last_price if quote is not None else None
        market_cap = quote.market_cap if quote is not None else None

        rows.append(
            PeerRow(
                symbol=peer_company.symbol,
                name=peer_company.name,
                template=peer_company.template,
                last_price=last_price,
                market_cap=market_cap,
                metrics=result["metrics"],
            )
        )
        warnings.extend(f"{peer_company.symbol}: {w}" for w in result["warnings"])

    response = PeersResponse(
        symbol=company.symbol,
        peer_basis=basis,
        peers=rows,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_peer_stats)
    return response

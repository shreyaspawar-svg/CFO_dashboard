import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.metrics.beta import compute_beta, paired_daily_returns
from app.models.schemas import OverviewResponse
from app.services.cache import get_cache
from app.services.datasource import get_data_source
from app.services.universe import get_company, peer_group_for_symbol

router = APIRouter(prefix="/api", tags=["overview"])

_BENCHMARK_TICKER = "^NSEI"
# A sector can have up to 12 companies (Banks & Financial Services); the
# template fallback for undersized sectors can have dozens (PLAN.md "Phase
# 1.5 review" item 3). Relative-vs-sector performance only ever uses the
# symbol's own SECTOR peers (never the template fallback) and caps how many
# histories it fetches, so this stays a bounded, best-effort feature, not
# an N-way fan-out.
_MAX_SECTOR_PEERS_FOR_PERFORMANCE = 12


def _total_return_pct(closes: list[float | None]) -> float | None:
    valid = [c for c in closes if c is not None]
    if len(valid) < 2 or valid[0] == 0:
        return None
    return (valid[-1] - valid[0]) / valid[0] * 100


async def _one_year_return(data_source, yf_ticker: str) -> float | None:
    try:
        bars = await data_source.get_history_bars(yf_ticker, "1y", "1d")
    except Exception:  # noqa: BLE001
        return None
    return _total_return_pct([b.get("Close") for b in bars])


@router.get("/overview/{symbol}", response_model=OverviewResponse)
async def get_overview(symbol: str) -> OverviewResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    cache_key = f"overview:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return OverviewResponse(**cached)

    data_source = get_data_source()
    warnings: list[str] = []

    # --- Beta: computed from 1y daily history, not fetched (Yahoo doesn't
    # reliably expose this for NSE tickers) ---------------------------------
    beta = None
    try:
        symbol_bars, benchmark_bars = await asyncio.gather(
            data_source.get_history_bars(company.yf_ticker, "1y", "1d"),
            data_source.get_history_bars(_BENCHMARK_TICKER, "1y", "1d"),
        )
        symbol_returns, benchmark_returns = paired_daily_returns(symbol_bars, benchmark_bars)
        beta = compute_beta(symbol_returns, benchmark_returns)
        if beta is None:
            warnings.append("Beta unavailable: too few overlapping trading days")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Beta computation failed: {exc}")

    # --- Analyst target price (best-effort, crumb-gated) -------------------
    try:
        analyst = await data_source.get_analyst_target(company.yf_ticker)
    except Exception as exc:  # noqa: BLE001
        analyst = {}
        warnings.append(f"Analyst target fetch failed: {exc}")
    if not analyst.get("target_mean_price"):
        warnings.append("Analyst target unavailable (no coverage or Yahoo crumb not issued)")

    # --- Relative performance vs NIFTY 50 and vs sector peers ---------------
    symbol_return, benchmark_return = await asyncio.gather(
        _one_year_return(data_source, company.yf_ticker),
        _one_year_return(data_source, _BENCHMARK_TICKER),
    )
    relative_vs_nifty = (
        symbol_return - benchmark_return
        if symbol_return is not None and benchmark_return is not None
        else None
    )
    if relative_vs_nifty is None:
        warnings.append("Relative performance vs NIFTY 50 unavailable (insufficient history)")

    sector_peers, peer_basis = peer_group_for_symbol(company.symbol)
    relative_vs_sector = None
    sector_peer_count = 0
    if peer_basis == "sector":
        peer_symbols = [c.yf_ticker for c in sector_peers if c.symbol != company.symbol][
            :_MAX_SECTOR_PEERS_FOR_PERFORMANCE
        ]
        peer_returns = await asyncio.gather(
            *(_one_year_return(data_source, t) for t in peer_symbols)
        )
        valid_peer_returns = [r for r in peer_returns if r is not None]
        sector_peer_count = len(valid_peer_returns)
        if symbol_return is not None and valid_peer_returns:
            sector_avg_return = sum(valid_peer_returns) / len(valid_peer_returns)
            relative_vs_sector = symbol_return - sector_avg_return
    if relative_vs_sector is None:
        warnings.append(
            "Relative performance vs sector unavailable (small/fallback sector or insufficient history)"
        )

    response = OverviewResponse(
        symbol=company.symbol,
        beta=beta,
        analyst_target_mean=analyst.get("target_mean_price"),
        analyst_target_high=analyst.get("target_high_price"),
        analyst_target_low=analyst.get("target_low_price"),
        analyst_count=analyst.get("number_of_analysts"),
        analyst_recommendation=analyst.get("recommendation"),
        relative_performance_vs_nifty50_pp=relative_vs_nifty,
        relative_performance_vs_sector_pp=relative_vs_sector,
        sector_peer_count=sector_peer_count,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response

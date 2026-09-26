"""Peer-group metric values for sector/template medians, percentile ranks,
and the health-radar score -- cached, since computing it means fetching
financials for every company in the group (up to ~30 for the `general`
template fallback).
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import get_settings
from app.services.cache import get_cache
from app.services.metrics_engine import compute_symbol_metrics
from app.services.universe import get_company, peer_group_for_symbol


async def compute_peer_metric_values(symbol: str) -> dict[str, Any]:
    """Returns {"peer_values": dict[metric_key, list[float|None]], "basis":
    "sector"|"template"|"none", "peer_symbols": list[str]}.

    `peer_values` includes the requesting symbol's own value (it's a member
    of its own peer group) -- percentile_rank doesn't special-case that.
    """
    company = get_company(symbol)
    if company is None:
        return {"peer_values": {}, "basis": "none", "peer_symbols": []}

    peers, basis = peer_group_for_symbol(symbol)
    peer_symbols = sorted(c.symbol for c in peers)
    if not peer_symbols:
        return {"peer_values": {}, "basis": basis, "peer_symbols": []}

    cache = get_cache()
    cache_key = f"peer_metrics:{'-'.join(peer_symbols)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return {"peer_values": cached, "basis": basis, "peer_symbols": peer_symbols}

    results = await asyncio.gather(*(compute_symbol_metrics(s) for s in peer_symbols))

    peer_values: dict[str, list[float | None]] = {}
    for result in results:
        for key, value in result["metrics"].items():
            peer_values.setdefault(key, []).append(value)

    settings = get_settings()
    cache.set(cache_key, peer_values, settings.ttl_peer_stats)
    return {"peer_values": peer_values, "basis": basis, "peer_symbols": peer_symbols}

"""Pre-populate the TTL cache for all 50 NIFTY symbols (quote, 1y history,
annual + quarterly financials) so the first user request after a restart is
served from cache instead of hitting Yahoo cold.

Usage:
    python scripts/warm_cache.py
"""

from __future__ import annotations

import asyncio
import time

from app.routers.financials import get_financials
from app.routers.history import get_history
from app.routers.quote import get_quote
from app.services.universe import all_symbols


async def _warm_symbol(symbol: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    for label, coro in (
        ("quote", get_quote(symbol)),
        ("history", get_history(symbol, range="1y", interval="1d")),
        ("financials(annual)", get_financials(symbol, period="annual")),
        ("financials(quarterly)", get_financials(symbol, period="quarterly")),
    ):
        try:
            await coro
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: {exc}")
    return symbol, errors


async def main() -> None:
    started = time.monotonic()
    symbols = all_symbols()
    results = await asyncio.gather(*(_warm_symbol(s) for s in symbols))

    failed = [(s, e) for s, e in results if e]
    elapsed = time.monotonic() - started
    print(f"Warmed {len(symbols)} symbols in {elapsed:.1f}s")
    if failed:
        print(f"{len(failed)} symbol(s) had errors:")
        for symbol, errors in failed:
            for err in errors:
                print(f"  {symbol}: {err}")


if __name__ == "__main__":
    asyncio.run(main())

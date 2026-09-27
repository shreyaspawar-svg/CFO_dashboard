"""One attempt at NSE's public shareholding-pattern endpoint via
`curl_cffi` (impersonating a browser -- NSE requires a homepage visit
first to pick up cookies before any /api/ call succeeds).

PLAN.md Phase 4 Task D: live-tested 2026-09-27. The homepage and a few
generic pages return 200, but NSE's actual data APIs (`/api/quote-equity`,
and every shareholding-pattern path tried) come back `403 Access Denied`
from this deployment's IP -- the same class of block already documented
for other NSE endpoints. Exactly one attempt is made; any non-200 response
or exception returns `None` immediately, no retries.
"""

from __future__ import annotations

import asyncio
from typing import Any

from curl_cffi import requests as cffi_requests

_HOMEPAGE_URL = "https://www.nseindia.com/"
_SHAREHOLDING_URL = "https://www.nseindia.com/api/corporate-shareholding-pattern"


def _fetch_shareholding_pattern_sync(symbol: str) -> list[dict[str, Any]] | None:
    try:
        session = cffi_requests.Session(impersonate="chrome")
        session.get(_HOMEPAGE_URL, timeout=10)
        response = session.get(
            _SHAREHOLDING_URL,
            params={"index": "equities", "symbol": symbol},
            timeout=10,
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data if isinstance(data, list) else data.get("data")
    except Exception:  # noqa: BLE001
        return None


async def fetch_shareholding_pattern(symbol: str) -> list[dict[str, Any]] | None:
    return await asyncio.to_thread(_fetch_shareholding_pattern_sync, symbol)

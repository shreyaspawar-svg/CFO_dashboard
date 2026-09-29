"""One attempt at NSE's public shareholding-pattern endpoint via
`curl_cffi` (impersonating a browser -- NSE requires a homepage visit
first to pick up cookies before any /api/ call succeeds), then one bounded
fallback attempt at BSE's public site.

PLAN.md Phase 4 Task D: live-tested 2026-09-27. The homepage and a few
generic pages return 200, but NSE's actual data APIs (`/api/quote-equity`,
and every shareholding-pattern path tried) come back `403 Access Denied`
from this deployment's IP -- the same class of block already documented
for other NSE endpoints. Exactly one attempt is made; any non-200 response
or exception returns `None` immediately, no retries.

UI-exploration branch: added one bounded BSE fallback (2026-09-29). BSE's
scrip-code search API (`PeerSmartSearch`) works fine and resolves a symbol
to its numeric scrip code (e.g. TCS -> 532540), but the shareholding-
pattern API behind it (`ShPPercentageStackChart_1`) enters an infinite
redirect loop from this deployment's IP (`curl: (47) Maximum redirects
followed`) -- a different-shaped block than NSE's, but a block all the
same. Kept as a single try (short timeout, no retries): if BSE ever stops
blocking this IP range, this starts working with no other code changes;
until then it fails fast and the router falls back to the existing honest
"not available" state.
"""

from __future__ import annotations

import asyncio
from typing import Any

from curl_cffi import requests as cffi_requests

_HOMEPAGE_URL = "https://www.nseindia.com/"
_SHAREHOLDING_URL = "https://www.nseindia.com/api/corporate-shareholding-pattern"

_BSE_HOMEPAGE_URL = "https://www.bseindia.com/"
_BSE_SCRIP_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w"
_BSE_SHAREHOLDING_URL = "https://api.bseindia.com/BseIndiaAPI/api/ShPPercentageStackChart_1/w"


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


def _fetch_bse_shareholding_pattern_sync(symbol: str) -> list[dict[str, Any]] | None:
    try:
        session = cffi_requests.Session(impersonate="chrome")
        session.get(_BSE_HOMEPAGE_URL, timeout=10)
        search = session.get(
            _BSE_SCRIP_SEARCH_URL,
            params={"Text": symbol, "type": "EQ"},
            timeout=10,
            headers={"Accept": "application/json", "Referer": _BSE_HOMEPAGE_URL},
        )
        if search.status_code != 200:
            return None
        # Response is an HTML fragment of <li onclick="liclick('<scripcode>','<name>')">
        # entries, not JSON -- pull the first scrip code out of it.
        import re

        match = re.search(r"liclick\('(\d+)'", search.text)
        if match is None:
            return None
        scrip_code = match.group(1)

        response = session.get(
            _BSE_SHAREHOLDING_URL,
            params={"scripcode": scrip_code},
            timeout=10,
            headers={"Accept": "application/json", "Referer": _BSE_HOMEPAGE_URL},
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data if isinstance(data, list) else data.get("Table")
    except Exception:  # noqa: BLE001
        return None


async def fetch_shareholding_pattern(symbol: str) -> list[dict[str, Any]] | None:
    result = await asyncio.to_thread(_fetch_shareholding_pattern_sync, symbol)
    if result is not None:
        return result
    return await asyncio.to_thread(_fetch_bse_shareholding_pattern_sync, symbol)

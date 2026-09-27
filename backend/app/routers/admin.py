"""Operational endpoint for the scheduled refresh cron (PLAN.md Phase 8
Step 2/4): re-pulls the NSE constituent list (best-effort -- NSE blocks
most cloud/datacenter IPs with a 403, including Render's, so this is
expected to often fail from here; see docs/data-notes.md and DEPLOY.md)
and re-warms the quote/history/financials cache for all 50 symbols.

Protected by a shared-secret header rather than a real auth system --
this is a single-purpose internal endpoint for one GitHub Actions cron,
not a public API surface.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _refresh_constituents() -> dict[str, Any]:
    from scripts.refresh_constituents import (
        NIFTY50_JSON_PATH,
        fetch_constituents_csv,
        merge_with_existing,
        parse_csv,
    )
    import json

    existing = json.loads(NIFTY50_JSON_PATH.read_text(encoding="utf-8"))
    try:
        csv_text = fetch_constituents_csv()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"NSE fetch failed (likely a cloud-IP block): {exc}"}

    rows = parse_csv(csv_text)
    if len(rows) != 50:
        return {"ok": False, "error": f"Expected 50 constituents, got {len(rows)}"}

    updated = merge_with_existing(rows, existing)
    updated["generated_at"] = date.today().isoformat()
    # Render's free tier has an ephemeral filesystem -- this write survives
    # only until the next restart/redeploy, same as the TTL cache. Real
    # persistence needs a paid disk or an external store; see DEPLOY.md.
    NIFTY50_JSON_PATH.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"ok": True, "constituent_count": len(rows)}


async def _warm_cache() -> dict[str, Any]:
    from scripts.warm_cache import _warm_symbol
    from app.services.universe import all_symbols
    import asyncio

    symbols = all_symbols()
    results = await asyncio.gather(*(_warm_symbol(s) for s in symbols))
    failed = {s: errs for s, errs in results if errs}
    return {"ok": not failed, "symbols_warmed": len(symbols), "failed": failed}


@router.post("/refresh")
async def refresh(x_refresh_secret: str | None = Header(default=None)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.admin_refresh_secret:
        raise HTTPException(status_code=503, detail="ADMIN_REFRESH_SECRET not configured on this deployment")
    if x_refresh_secret != settings.admin_refresh_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Refresh-Secret header")

    constituents_result = _refresh_constituents()
    warm_result = await _warm_cache()
    return {"constituents": constituents_result, "cache_warm": warm_result}

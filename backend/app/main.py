from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import events, financials, history, peers, quote, ratios, universe, valuation
from app.services.cache import get_cache

settings = get_settings()

app = FastAPI(title="NIFTY 50 CFO Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(universe.router)
app.include_router(quote.router)
app.include_router(history.router)
app.include_router(financials.router)
app.include_router(ratios.router)
app.include_router(peers.router)
app.include_router(valuation.router)
app.include_router(events.router)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "cache": get_cache().get_stats(),
    }

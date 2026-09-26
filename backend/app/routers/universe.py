from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import UniverseResponse
from app.services.universe import load_universe

router = APIRouter(prefix="/api", tags=["universe"])


@router.get("/universe", response_model=UniverseResponse)
async def get_universe() -> UniverseResponse:
    return UniverseResponse(
        sectors=load_universe(),
        as_of=datetime.now(timezone.utc),
    )

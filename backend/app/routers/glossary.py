"""Serves backend/data/glossary.json (PLAN.md §4.3 item 2) -- a single
source for every ratio card's formula/meaning/"what good looks like"
tooltip, rather than duplicating that text in the frontend.
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import APIRouter

from app.config import BASE_DIR
from app.models.schemas import GlossaryEntry, GlossaryResponse

router = APIRouter(prefix="/api", tags=["glossary"])

_GLOSSARY_PATH = BASE_DIR / "data" / "glossary.json"


@lru_cache
def _load() -> dict[str, GlossaryEntry]:
    raw = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))
    return {key: GlossaryEntry(**entry) for key, entry in raw.items()}


@router.get("/glossary", response_model=GlossaryResponse)
async def get_glossary() -> GlossaryResponse:
    return GlossaryResponse(entries=_load())

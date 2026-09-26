from __future__ import annotations

import json
from functools import lru_cache

from app.config import get_settings
from app.models.schemas import CompanyRef, SectorGroup


@lru_cache
def load_universe() -> list[SectorGroup]:
    settings = get_settings()
    raw = json.loads(settings.nifty50_json_path.read_text(encoding="utf-8"))
    return [SectorGroup(**sector) for sector in raw["sectors"]]


@lru_cache
def company_by_symbol() -> dict[str, CompanyRef]:
    return {
        company.symbol: company
        for sector in load_universe()
        for company in sector.companies
    }


def get_company(symbol: str) -> CompanyRef | None:
    return company_by_symbol().get(symbol.upper())


def all_symbols() -> list[str]:
    return list(company_by_symbol().keys())


def peers_for_symbol(symbol: str) -> list[CompanyRef]:
    company = get_company(symbol)
    if company is None:
        return []
    for sector in load_universe():
        if any(c.symbol == company.symbol for c in sector.companies):
            return sector.companies
    return []

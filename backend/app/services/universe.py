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


@lru_cache
def companies_by_template() -> dict[str, list[CompanyRef]]:
    by_template: dict[str, list[CompanyRef]] = {}
    for sector in load_universe():
        for company in sector.companies:
            by_template.setdefault(company.template, []).append(company)
    return by_template


# Below this many companies, a sector's own median is statistically
# meaningless (PLAN.md "Phase 1.5 review" item 3: six sectors have only 1-2
# companies). Matches the plan's own count exactly: Power (2), Consumer
# Durables (2), Consumer Services & Retail (2), Transport & Logistics (2),
# Capital Goods & Defence (1), Telecom (1) all fall back; Construction &
# Materials (3) does not.
MIN_SECTOR_PEER_COUNT = 3


def peer_group_for_symbol(symbol: str) -> tuple[list[CompanyRef], str]:
    """The comparable set for sector-median/percentile/scoring purposes.

    Returns (peers, basis), where basis is "sector" when the symbol's own
    sector has enough companies to be meaningful, or "template" when it
    falls back to every company sharing the same business-model template
    (across all sectors) instead. The caller should surface `basis` in the
    response so the UI can say which fallback was used.
    """
    company = get_company(symbol)
    if company is None:
        return [], "none"

    sector_peers = peers_for_symbol(symbol)
    if len(sector_peers) >= MIN_SECTOR_PEER_COUNT:
        return sector_peers, "sector"

    template_peers = companies_by_template().get(company.template, [])
    return template_peers, "template"

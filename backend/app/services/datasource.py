"""Common interface for a market-data provider.

Routers depend on this interface, not on `services.yahoo` directly, so a
future NSE-native or paid-feed implementation can be swapped in via
`set_data_source()` without touching router code. `YahooDataSource` is the
only implementation today.
"""

from __future__ import annotations

from typing import Any, Protocol


class MarketDataSource(Protocol):
    async def get_chart(
        self, yf_ticker: str, range_: str, interval: str, events: str | None = None
    ) -> dict[str, Any]: ...

    async def get_history_bars(
        self, yf_ticker: str, range_: str, interval: str
    ) -> list[dict[str, Any]]: ...

    async def get_fast_info(self, yf_ticker: str) -> dict[str, Any]: ...

    async def get_market_cap(self, yf_ticker: str, last_price: float | None) -> float | None: ...

    async def get_key_statistics(self, yf_ticker: str) -> dict[str, float | None]: ...

    async def get_income_statement(
        self, yf_ticker: str, quarterly: bool = False
    ) -> list[dict[str, Any]]: ...

    async def get_balance_sheet(
        self, yf_ticker: str, quarterly: bool = False
    ) -> list[dict[str, Any]]: ...

    async def get_cash_flow(
        self, yf_ticker: str, quarterly: bool = False
    ) -> list[dict[str, Any]]: ...

    async def get_dividends(self, yf_ticker: str) -> list[dict[str, Any]]: ...

    async def get_splits(self, yf_ticker: str) -> list[dict[str, Any]]: ...

    async def get_news(self, yf_ticker: str) -> list[dict[str, Any]]: ...


class YahooDataSource:
    """Thin adapter over `services.yahoo`'s module-level functions."""

    async def get_chart(
        self, yf_ticker: str, range_: str, interval: str, events: str | None = None
    ) -> dict[str, Any]:
        from app.services import yahoo

        return await yahoo.fetch_chart(yf_ticker, range_, interval, events)

    async def get_history_bars(
        self, yf_ticker: str, range_: str, interval: str
    ) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_history(yf_ticker, range_, interval)

    async def get_fast_info(self, yf_ticker: str) -> dict[str, Any]:
        from app.services import yahoo

        return await yahoo.fetch_fast_info(yf_ticker)

    async def get_market_cap(self, yf_ticker: str, last_price: float | None) -> float | None:
        from app.services import yahoo

        return await yahoo.fetch_market_cap(yf_ticker, last_price)

    async def get_key_statistics(self, yf_ticker: str) -> dict[str, float | None]:
        from app.services import yahoo

        return await yahoo.fetch_key_statistics(yf_ticker)

    async def get_income_statement(
        self, yf_ticker: str, quarterly: bool = False
    ) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_income_stmt(yf_ticker, quarterly)

    async def get_balance_sheet(
        self, yf_ticker: str, quarterly: bool = False
    ) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_balance_sheet(yf_ticker, quarterly)

    async def get_cash_flow(
        self, yf_ticker: str, quarterly: bool = False
    ) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_cashflow(yf_ticker, quarterly)

    async def get_dividends(self, yf_ticker: str) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_dividends(yf_ticker)

    async def get_splits(self, yf_ticker: str) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_splits(yf_ticker)

    async def get_news(self, yf_ticker: str) -> list[dict[str, Any]]:
        from app.services import yahoo

        return await yahoo.fetch_news(yf_ticker)


_data_source: MarketDataSource | None = None


def get_data_source() -> MarketDataSource:
    global _data_source
    if _data_source is None:
        _data_source = YahooDataSource()
    return _data_source


def set_data_source(source: MarketDataSource) -> None:
    """Override the active data source. Used by tests to inject a fixture
    or fake implementation, and later by an NSE/paid-feed swap."""
    global _data_source
    _data_source = source

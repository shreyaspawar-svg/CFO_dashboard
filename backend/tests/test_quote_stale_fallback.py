"""PLAN.md Phase 5 §B.4: if the live upstream fetch fails, serve the last
known good quote marked `stale=True` rather than a broken/empty card."""

from app.routers.quote import _build_quote
from app.services.cache import get_cache
from app.services.datasource import set_data_source


class _FlakyDataSource:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def get_fast_info(self, yf_ticker: str) -> dict:
        if self.fail:
            raise RuntimeError("simulated upstream failure")
        return {
            "last_price": 100.0,
            "previous_close": 95.0,
            "open": 96.0,
            "day_high": 101.0,
            "day_low": 94.0,
            "volume": 1000,
            "year_high": 120.0,
            "year_low": 80.0,
        }

    async def get_market_cap(self, yf_ticker: str, last_price):
        return 1000.0 * 10_000_000  # crore, once divided by CRORE downstream


def _expire_cache_key(key: str) -> None:
    cache = get_cache()
    cache._mem.pop(key, None)  # noqa: SLF001 -- white-box: force the next read to miss
    cache._disk.delete(key)  # noqa: SLF001


async def test_quote_falls_back_to_last_known_good_on_upstream_failure():
    source = _FlakyDataSource(fail=False)
    set_data_source(source)
    try:
        first = await _build_quote("TCS")
        assert first.last_price == 100.0
        assert first.stale is False

        _expire_cache_key("quote:TCS")
        source.fail = True
        second = await _build_quote("TCS")

        assert second.last_price == 100.0  # served from the last-known-good copy
        assert second.stale is True
        assert any("last known quote" in w for w in second.warnings)
    finally:
        set_data_source(None)


async def test_quote_failure_with_no_prior_success_returns_nulls_not_a_crash():
    set_data_source(_FlakyDataSource(fail=True))
    try:
        result = await _build_quote("RELIANCE")
        assert result.last_price is None
        assert result.stale is False
        assert any("fetch failed" in w for w in result.warnings)
    finally:
        set_data_source(None)


async def test_quote_failure_response_is_not_cached_so_next_call_retries():
    source = _FlakyDataSource(fail=True)
    set_data_source(source)
    try:
        await _build_quote("HDFCBANK")
        assert get_cache().get("quote:HDFCBANK") is None
        source.fail = False
        recovered = await _build_quote("HDFCBANK")
        assert recovered.last_price == 100.0
    finally:
        set_data_source(None)

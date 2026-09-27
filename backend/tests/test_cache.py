import asyncio
import time

from app.services.cache import TTLCache


def test_cache_set_then_get_returns_value(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "sqlite_cache_path", tmp_path / "cache.sqlite")
    cache = TTLCache()
    cache.set("k", {"a": 1}, ttl_seconds=60)
    assert cache.get("k") == {"a": 1}


def test_cache_expires_after_ttl(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "sqlite_cache_path", tmp_path / "cache.sqlite")
    cache = TTLCache()
    cache.set("k", "v", ttl_seconds=0.05)
    assert cache.get("k") == "v"
    time.sleep(0.1)
    assert cache.get("k") is None


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "sqlite_cache_path", tmp_path / "cache.sqlite")
    cache = TTLCache()
    assert cache.get("nonexistent") is None


async def test_single_flight_coalesces_concurrent_callers_into_one_fetch(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "sqlite_cache_path", tmp_path / "cache.sqlite")
    cache = TTLCache()
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return "result"

    results = await asyncio.gather(*(cache.single_flight("k", fetch) for _ in range(5)))
    assert results == ["result"] * 5
    assert call_count == 1  # only one real upstream call, not 5


async def test_single_flight_does_not_cache_by_itself(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.get_settings(), "sqlite_cache_path", tmp_path / "cache.sqlite")
    cache = TTLCache()

    async def fetch():
        return "v"

    await cache.single_flight("k", fetch)
    assert cache.get("k") is None  # caching is the caller's responsibility


async def test_single_flight_sequential_calls_each_refetch():
    cache = TTLCache.__new__(TTLCache)
    cache._inflight = {}
    cache._inflight_lock = asyncio.Lock()
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return call_count

    first = await cache.single_flight("k", fetch)
    second = await cache.single_flight("k", fetch)
    assert (first, second) == (1, 2)  # not coalesced once the first has finished

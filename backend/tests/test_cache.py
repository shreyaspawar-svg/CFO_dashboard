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

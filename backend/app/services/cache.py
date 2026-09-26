"""Two-tier cache: an in-process dict for hot reads, backed by a SQLite-based
diskcache for persistence across restarts. Each entry carries its own TTL."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import diskcache

from app.config import get_settings


@dataclass
class _MemEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        settings = get_settings()
        settings.sqlite_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._disk = diskcache.Cache(str(settings.sqlite_cache_path.parent))
        self._mem: dict[str, _MemEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            entry = self._mem.get(key)
            if entry is not None:
                if entry.expires_at > now:
                    return entry.value
                del self._mem[key]

        value = self._disk.get(key, default=None)
        if value is None:
            return None
        payload, expires_at = value
        if expires_at <= now:
            self._disk.delete(key)
            return None

        with self._lock:
            self._mem[key] = _MemEntry(payload, expires_at)
        return payload

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._mem[key] = _MemEntry(value, expires_at)
        self._disk.set(key, (value, expires_at), expire=ttl_seconds)

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            mem_count = len(self._mem)
        return {"memory_entries": mem_count, "disk_entries": len(self._disk)}


_cache: TTLCache | None = None


def get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache()
    return _cache

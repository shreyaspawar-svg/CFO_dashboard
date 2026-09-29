from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / ".cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cors_origins: list[str] = ["http://localhost:3000"]

    # Shared secret for POST /api/admin/refresh (PLAN.md Phase 8 Step 2/4).
    # Empty (the default) disables the endpoint entirely -- set via the
    # ADMIN_REFRESH_SECRET env var on the deployed host, never committed.
    admin_refresh_secret: str = ""

    # Cache TTLs, in seconds
    ttl_universe: int = 24 * 3600
    ttl_quote_market_hours: int = 30
    ttl_quote_closed: int = 3600
    ttl_quotes_batch: int = 60
    ttl_history_intraday: int = 5 * 60
    ttl_history_daily: int = 6 * 3600
    ttl_financials: int = 12 * 3600
    ttl_peer_stats: int = 6 * 3600
    ttl_news: int = 25 * 60

    # Yahoo throttling
    yahoo_max_concurrency: int = 4
    yahoo_retry_attempts: int = 3
    yahoo_retry_backoff_seconds: float = 1.5

    nifty50_json_path: Path = DATA_DIR / "nifty50.json"
    sqlite_cache_path: Path = CACHE_DIR / "cache.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()

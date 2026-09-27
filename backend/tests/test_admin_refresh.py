"""PLAN.md Phase 8 Step 2/4: POST /api/admin/refresh is gated by a shared
secret (ADMIN_REFRESH_SECRET), never a real auth system -- this is a
single-purpose endpoint for one GitHub Actions cron. Network calls inside
it (NSE constituents fetch, per-symbol cache warm) are mocked here; that
plumbing itself is exercised elsewhere (test_universe_peers.py and
friends already cover `all_symbols`/fixture-backed fetches)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_refresh_without_configured_secret_is_503(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "admin_refresh_secret", "")
    resp = client.post("/api/admin/refresh")
    assert resp.status_code == 503


def test_refresh_missing_header_is_401(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "admin_refresh_secret", "s3cr3t")
    resp = client.post("/api/admin/refresh")
    assert resp.status_code == 401


def test_refresh_wrong_secret_is_401(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "admin_refresh_secret", "s3cr3t")
    resp = client.post("/api/admin/refresh", headers={"X-Refresh-Secret": "wrong"})
    assert resp.status_code == 401


def test_refresh_correct_secret_runs_both_steps(monkeypatch):
    monkeypatch.setattr(config.get_settings(), "admin_refresh_secret", "s3cr3t")

    async def fake_warm_cache():
        return {"ok": True, "symbols_warmed": 50, "failed": {}}

    def fake_refresh_constituents():
        return {"ok": False, "error": "NSE fetch failed (likely a cloud-IP block): 403"}

    monkeypatch.setattr("app.routers.admin._warm_cache", fake_warm_cache)
    monkeypatch.setattr("app.routers.admin._refresh_constituents", fake_refresh_constituents)

    resp = client.post("/api/admin/refresh", headers={"X-Refresh-Secret": "s3cr3t"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["cache_warm"]["ok"] is True
    assert body["constituents"]["ok"] is False  # honestly reported, not hidden

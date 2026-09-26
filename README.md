# NIFTY 50 CFO Dashboard

See [PLAN.md](PLAN.md) for the full design and phase breakdown, and
[CLAUDE.md](CLAUDE.md) for project conventions.

## Status

Phase 1 complete: FastAPI backend serving cached, normalised, template-aware
data for all 50 NIFTY constituents. See `data_coverage_report.md` for what's
missing per company.

## Running the backend locally

```bash
cd backend
py -3.12 -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
./.venv/Scripts/uvicorn app.main:app --reload      # .venv/bin/uvicorn on macOS/Linux
```

API docs: http://localhost:8000/docs

### Scripts

```bash
cd backend
./.venv/Scripts/python -m scripts.warm_cache          # pre-populate the cache for all 50 symbols
./.venv/Scripts/python scripts/refresh_constituents.py --dry-run   # pull latest NIFTY 50 list from NSE
```

`refresh_constituents.py` needs a normal (non-datacenter) network path — NSE
blocks a lot of cloud/CI IPs with a 403.

### Tests

```bash
cd backend
./.venv/Scripts/pytest                 # fixture-backed tests only, never touches the network (default)
./.venv/Scripts/pytest -m smoke -s     # hits live Yahoo Finance for all 50 symbols, regenerates data_coverage_report.md
```

Fixture-backed tests (`tests/test_api_endpoints.py` and friends) replay saved
real Yahoo responses for one company per template -- TCS (general), HDFCBANK
(bank), BAJFINANCE (nbfc), HDFCLIFE (insurance), BSE (exchange) -- from
`tests/fixtures/`. `tests/conftest.py` autouse-patches the Yahoo HTTP layer so
no test in the default run can reach the network; anything not in a fixture
raises `AssertionError` instead of silently falling through. To regenerate
fixtures after a schema/field-map change:

```bash
./.venv/Scripts/python -m tests.fixtures._capture
```

## Data-source abstraction

Routers depend on `app/services/datasource.get_data_source()` (a
`MarketDataSource` protocol), not on `app/services/yahoo` directly. Today the
only implementation is `YahooDataSource`. A future NSE-native or paid-feed
source can implement the same protocol and be swapped in via
`set_data_source()` without touching router code.

## A note on the Yahoo data source

`services/yahoo.py` does **not** use `yfinance`'s built-in `Ticker` class (or
`yfinance` at all -- it's not a dependency) for live requests. In testing,
yfinance's cookie/crumb negotiation got stuck reusing a poisoned crumb value
after a single rate-limited response, and then every subsequent call failed.
Instead, `services/yahoo.py` talks to Yahoo's chart and fundamentals-timeseries
endpoints directly through `curl_cffi` (which impersonates a real browser's
TLS fingerprint — plain `requests` gets blocked). Neither of those endpoints
needs a crumb. Market cap is computed as **price × shares outstanding** from
fundamentals data (also crumb-free); the crumb-gated `quoteSummary` endpoint
is used only as a best-effort cross-check, never as the primary source.

## Docker

`docker-compose.yml` is scaffolded for Phase 1, but the backend/frontend
Dockerfiles are a Phase 8 (deployment) deliverable. Until then, run each
service directly (see above).

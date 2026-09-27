# NIFTY 50 CFO Dashboard

A financial dashboard for all 50 NIFTY 50 constituents: income statement,
balance sheet, cash flow, ratios (with DuPont, quality scores and a
signals engine), valuation (multiples, historical bands, a DCF calculator),
peer comparables, and shareholding/events -- all computed from free Yahoo
Finance data, template-aware for banks/NBFCs/insurers vs general companies.

See [PLAN.md](PLAN.md) for the full design and phase-by-phase history, and
[CLAUDE.md](CLAUDE.md) for project conventions.

## Quick start

**Option A -- Docker Compose** (needs Docker Desktop running):

```bash
docker compose up --build
```

Frontend: http://localhost:3000 · Backend docs: http://localhost:8000/docs

**Option B -- `make dev`** (needs the backend venv and frontend deps already
installed once, see "Running locally" below):

```bash
make dev
```

Both start the backend (port 8000) and frontend (port 3000) together.

## Architecture

```
Browser
  |
  | same-origin requests only (no CORS): /api/*, /
  v
Next.js 16 frontend (App Router, TS strict, TanStack Query, Zustand)
  |
  | next.config.ts rewrites /api/* server-side to BACKEND_INTERNAL_URL
  | (the browser never calls the backend directly -- see backend/CLAUDE.md)
  v
FastAPI backend (Python 3.12, Pydantic v2)
  |-- app/routers/*        one router per resource, thin: I/O + response shaping
  |-- app/services/        I/O layer: yahoo.py (curl_cffi HTTP client), cache.py
  |                        (two-tier TTL + single-flight cache), metrics_engine.py
  |                        (bridges I/O to pure metrics), datasource.py (swappable
  |                        MarketDataSource protocol), universe.py, nse.py
  |-- app/metrics/         pure, unit-tested functions only: ratios.py, dcf.py,
  |                        signals.py, scoring.py, plausibility.py, units.py, ...
  |-- app/models/schemas.py   Pydantic response models (source of the OpenAPI
  |                        schema the frontend's types/api.ts is generated from)
  |
  v
Yahoo Finance (chart + fundamentals-timeseries endpoints, via curl_cffi
browser-TLS impersonation -- not the `yfinance` package; see below)
```

A metric's headline KPI value and any history/trend chart built from it
always call the *same* pure function over different periods -- never two
separate calculation paths for the same number (PLAN.md "Phase 3 review").

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness + cache stats |
| `GET /api/universe` | The 50 companies, grouped by sector |
| `GET /api/quote/{symbol}` | Live-ish quote (single-flight + stale fallback, see below) |
| `GET /api/quotes?symbols=A,B,C` | Batch quotes (ticker tape, sector peers) |
| `GET /api/history/{symbol}?range=&interval=` | OHLCV bars, incl. `1d`/intraday |
| `GET /api/financials/{symbol}?period=annual\|quarterly` | Income/balance/cash-flow statements + derived balance-sheet & cash-flow detail |
| `GET /api/ratios/{symbol}` | All ratios, DuPont, ratio history, quality scores, signals |
| `GET /api/valuation/{symbol}?growth_rate_pct=&wacc_pct=&terminal_growth_pct=&forecast_years=` | Multiples, P/E-P/B bands, DCF + sensitivity table, reverse DCF |
| `GET /api/peers/{symbol}` | Sector/template peer comparables, medians, percentiles |
| `GET /api/events/{symbol}` | Dividends, splits, news, shareholding attempt, earnings date |
| `GET /api/overview/{symbol}` | Beta, analyst targets, relative performance |
| `GET /api/glossary` | Metric definitions (formula, meaning, "what good looks like") |

Full interactive schema: http://localhost:8000/docs

## Data sources -- and a "delayed quotes" caveat

All data comes from Yahoo Finance's public chart and fundamentals-timeseries
endpoints (via `curl_cffi`, not the `yfinance` package -- see
`backend/app/services/yahoo.py`'s docstring for why). **Yahoo's own NSE
quotes are typically delayed, not real-time** -- this dashboard's "live"
polling (every 15s for a quote, 60s for peers/ticker batches, only while
the market is open and the browser tab is visible) keeps the UI as fresh as
its upstream source allows, but that source itself is not tick-by-tick
exchange data. Treat prices as indicative, not execution-grade.

## Running locally (without Docker)

```bash
cd backend
py -3.12 -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
./.venv/Scripts/uvicorn app.main:app --reload      # .venv/bin/uvicorn on macOS/Linux
```

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend && ./.venv/Scripts/pytest                 # fixture-backed, no network (default)
cd backend && ./.venv/Scripts/pytest -m smoke -s     # hits live Yahoo for all 50 symbols
cd frontend && npm test -- --run                     # Vitest
cd frontend && npm run test:e2e                      # Playwright, needs both dev servers running
```

### Scripts

```bash
cd backend && ./.venv/Scripts/python -m scripts.warm_cache
cd backend && ./.venv/Scripts/python scripts/refresh_constituents.py --dry-run
cd frontend && node scripts/qa_crawl.mjs   # crawls all 50 symbols x all tabs for console/API errors
```

## Data-source abstraction

Routers depend on `app/services/datasource.get_data_source()` (a
`MarketDataSource` protocol), not on `app/services/yahoo` directly. A future
NSE-native or paid-feed source can implement the same protocol and be
swapped in via `set_data_source()` without touching router code.

## Live-price plumbing (Phase 5)

- **Polling**: gated on the *backend's* `market_status` (open/closed/
  pre-open), not the browser clock -- quotes poll every 15s, peers/ticker
  batches every 60s, and TanStack Query's `refetchIntervalInBackground`
  default (`false`) already pauses all of it the moment the tab is hidden.
- **Single-flight**: `app/services/cache.py`'s `TTLCache.single_flight`
  coalesces concurrent requests for the same symbol into one upstream call.
- **Resilience**: a 429 retries with exponential backoff one level down in
  `services/yahoo.py` (tenacity); if the live fetch still fails, the quote
  router serves the last known good quote marked `stale: true` rather than
  a broken/empty card. The frontend also shows its own "Stale" badge if a
  quote's `as_of` is more than 5 minutes old during market hours.
- **Intraday chart**: the Overview tab's price chart has a 1D/1Y/5Y toggle;
  1D polls every 60s and updates the same chart instance in place (no
  remount/reload).

## Known limitations

- **HDFCBANK basis inconsistency**: its quarterly equity figures alternate
  between two reporting bases in Yahoo's feed. ROE/ROA fall back to
  annual, same-basis net income and are flagged data-quality-inconsistent
  rather than shown as a normal computed figure. See
  `backend/docs/data-notes.md`.
- **No NPA / CASA / solvency ratios**: this free data source doesn't expose
  the granular bank disclosures (gross/net NPA, CASA ratio, capital
  adequacy) needed for those -- bank/NBFC ratio cards are limited to what's
  actually reportable from Yahoo's fields (NIM, cost-to-income, ROA, etc.).
- **Shareholding pattern unavailable**: NSE's own data APIs return `403
  Access Denied` from this deployment's IP (confirmed live, not just
  assumed -- see `app/services/nse.py`). The Shareholding & Events tab shows
  this honestly rather than fabricating a chart.
- **~4 years of history**: Yahoo's fundamentals-timeseries typically returns
  4 annual periods and 5-6 quarters per symbol -- CAGRs, bands and charts
  are built over "available history," not a fixed 5-10y window.
- **Yahoo Finance is an unofficial, undocumented API**: field names,
  availability and scaling can change without notice (see the INFY
  income-statement/book-value scale mismatch in `docs/data-notes.md` for a
  concrete example this app had to detect and gate against). Not a
  substitute for a licensed exchange/vendor feed in production use.

## Backlog

- `manual_overrides.json`: a documented escape hatch for a small number of
  per-symbol corrections where the free source is simply wrong, instead of
  another `if symbol == "X"` special case.
- A broker API (or paid vendor feed) for genuinely real-time ticks, since
  Yahoo's own quotes are delayed.
- A "compare mode" (2+ companies side by side across tabs).
- PDF export of a company's dashboard.
- Production deployment (the Dockerfiles here are dev-mode; a production
  image, CI, and hosting target are not yet built).

# NIFTY 50 CFO Dashboard — Implementation Plan

> **How to use this file:** Drop it into the repo root as `PLAN.md`. Work through one phase at a time in Claude Code (VS Code). Each phase ends with a copy‑paste prompt and acceptance criteria. Don't start a phase until the previous one's criteria pass. Bring the result back to the planner (Claude Cowork) for review between phases.

---

## 0. Decisions locked in

| Area | Decision |
|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui |
| Charts | Apache ECharts (`echarts-for-react`) for financial charts; TradingView `lightweight-charts` for the price/candlestick chart |
| Data fetching (FE) | TanStack Query (caching, polling, stale‑while‑revalidate) |
| State | Zustand (selected sector/company, period, currency unit) + URL params (`?sector=it&symbol=TCS`) so views are shareable |
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| Market data | **Free:** `yfinance` (NSE tickers use the `.NS` suffix, e.g. `TCS.NS`) as primary; NSE public endpoints as fallback for quote/shareholding |
| Cache | Local: in‑memory TTL cache + SQLite (via `diskcache` or SQLModel) for fundamentals. Redis later if deployed |
| Run mode | Local first (`docker compose up` or two terminals); deployment in the final phase |

**Data caveat to keep visible in the UI:** Yahoo/NSE free data is unofficial and delayed (≈1–15 min). Label it "Delayed quote · Source: Yahoo Finance" and show a last‑updated timestamp. Don't market it as tick‑level live data.

---

## 1. Universe — NIFTY 50 (as of 30 Sep 2026)

The Sept 2026 rebalance (effective 30 Sep 2026) **adds BSE and removes Wipro**. Tata Motors now trades as **TMPV** (Tata Motors Passenger Vehicles) after its demerger.

**Rule:** don't hard‑code this forever. Store it in `backend/data/nifty50.json` and add a script (`scripts/refresh_constituents.py`) that pulls NSE's official list (`https://niftyindices.com/IndexConstituent/ind_nifty50list.csv`) and regenerates the JSON. Sector names below follow NSE's industry classification, grouped for the dropdown.

| Sector (dropdown 1) | Companies (NSE symbol) |
|---|---|
| Banks & Financial Services (12) | HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK, BAJFINANCE, BAJAJFINSV, SHRIRAMFIN, JIOFIN, HDFCLIFE, SBILIFE, BSE |
| Information Technology (4) | TCS, INFY, HCLTECH, TECHM |
| Oil, Gas & Energy (3) | RELIANCE, ONGC, COALINDIA |
| Automobiles (5) | MARUTI, M&M, TMPV, BAJAJ-AUTO, EICHERMOT |
| FMCG (4) | ITC, HINDUNILVR, NESTLEIND, TATACONSUM |
| Healthcare & Pharma (5) | SUNPHARMA, CIPLA, DRREDDY, APOLLOHOSP, MAXHEALTH |
| Metals & Mining (4) | TATASTEEL, JSWSTEEL, HINDALCO, ADANIENT |
| Power (2) | NTPC, POWERGRID |
| Construction & Materials (3) | LT, ULTRACEMCO, GRASIM |
| Consumer Durables (2) | TITAN, ASIANPAINT |
| Consumer Services & Retail (2) | ETERNAL, TRENT |
| Transport & Logistics (2) | ADANIPORTS, INDIGO |
| Capital Goods & Defence (1) | BEL |
| Telecom (1) | BHARTIARTL |

Ticker mapping gotchas for yfinance: `M&M` → `M&M.NS`, `BAJAJ-AUTO` → `BAJAJ-AUTO.NS`. Validate every symbol in Phase 1 with a smoke test.

---

## 2. Key design principle: sector‑aware metric templates

A single ratio set doesn't fit all 50 companies. EBITDA margin and inventory turns are meaningless for HDFC Bank; NIM and CASA matter instead. Build a **template per business model** and let the dashboard render the right KPI cards:

| Template | Applies to | Headline metrics |
|---|---|---|
| `bank` | HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK | NII growth, NIM (derived), Cost‑to‑income, ROA, ROE, P/B, Advances & deposits growth, Credit cost* , GNPA/NNPA* |
| `nbfc` | BAJFINANCE, SHRIRAMFIN, JIOFIN, BAJAJFINSV | AUM/loan growth*, NIM (derived), ROA, ROE, P/B, D/E |
| `insurance` | HDFCLIFE, SBILIFE | Premium growth, P/EV*, ROE, Solvency*, P/B |
| `exchange` | BSE | Revenue growth, EBITDA margin, PAT margin, ROE, P/E |
| `general` | everyone else | Revenue/EBITDA/PAT growth, margins, ROCE, ROE, D/E, Interest coverage, Working‑capital days, FCF, EV/EBITDA, P/E |

\* Not available from yfinance. Show as "—" with a tooltip "Not in free data source" rather than inventing numbers. These can be filled later from quarterly results PDFs or a paid feed.

---

## 3. Dashboard layout (what the finished product looks like)

Reference products to copy patterns from: **Screener.in** (financial tables, 10‑yr history), **Tickertape** (scorecards, peer comparison), **Koyfin** (clean dense dashboards), **TradingView** (price chart UX), **Tijori Finance** (segment visuals).

```
┌───────────────────────────────────────────────────────────────────────┐
│ Top bar: logo · [Sector ▼] → [Company ▼] · search (⌘K) · market status │
│          · theme toggle · units (₹ Cr / ₹ Lakh Cr) · last updated      │
├───────────────────────────────────────────────────────────────────────┤
│ Company header: name, symbol, sector, LTP (flashes on change), Δ, Δ%,  │
│ day range, 52w range bar, mkt cap, volume, sparkline                   │
├──────────┬──────────┬──────────┬──────────┬──────────┬───────────────┤
│ KPI cards (6–8, template‑driven, each with YoY Δ and a mini sparkline)│
├───────────────────────────────────────────────────────────────────────┤
│ Tabs: Overview | Income Statement | Balance Sheet | Cash Flow |        │
│       Ratios | Valuation | Peers | Shareholding & Events               │
└───────────────────────────────────────────────────────────────────────┘
```

### Tab contents

1. **Overview** — Candlestick + volume (1D/5D/1M/6M/1Y/5Y/MAX, SMA 50/200 toggle), price vs NIFTY 50 relative performance, returns table (1M–5Y, CAGR), financial health scorecard (radar: Growth, Profitability, Leverage, Liquidity, Efficiency, Valuation — each scored vs sector peers), analyst consensus & target price (from yfinance where available).
2. **Income Statement** — Annual/Quarterly toggle; revenue/EBITDA/PAT combo bar+line with margin % on secondary axis; YoY/QoQ growth bars; waterfall (Revenue → COGS → Opex → EBITDA → D&A → Interest → Tax → PAT); expandable table with CAGR column.
3. **Balance Sheet** — Stacked bar of assets vs liabilities+equity; composition treemap/sunburst; debt vs cash trend; net‑worth growth; working‑capital trend.
4. **Cash Flow** — CFO/CFI/CFF grouped bars; FCF trend; cash conversion (CFO/EBITDA, CFO/PAT); capex intensity; cash‑flow Sankey for latest year.
5. **Ratios** — Grid of ratio cards grouped by Profitability, Returns, Leverage, Liquidity, Efficiency, Per‑share. Each card: value, 5‑yr trend line, sector median marker, percentile badge. DuPont decomposition chart (ROE = margin × turnover × leverage).
6. **Valuation** — P/E, P/B, EV/EBITDA, EV/Sales, dividend yield, PEG, earnings yield; current vs own 5‑yr range (band chart); simple DCF calculator with sliders (growth, WACC, terminal growth) giving intrinsic value vs LTP; reverse DCF (implied growth).
7. **Peers** — Sortable comparables table (all companies in the sector, plus optional "add any NIFTY company"); scatter plot (e.g., ROE vs P/B, bubble = mkt cap, axes selectable); rank bars; heatmap of the sector's ratios with the selected company highlighted.
8. **Shareholding & Events** — Promoter/FII/DII/public trend (NSE fallback), dividends history, splits/bonuses, upcoming earnings date, recent news headlines (yfinance `news`).

### UI standards
- Dark mode default, light mode supported; consistent palette via CSS variables; semantic colours only for up/down (green/red) — not for categories.
- Indian formatting everywhere: `₹1,23,456.78`, crores/lakh crores, FY labels (FY24 = Apr 2023–Mar 2024).
- Skeleton loaders, no layout shift; toast on API failure with retry; every chart has tooltips, legend toggles, and "download PNG/CSV".
- Responsive: 3‑column desktop → 1‑column mobile; tables scroll horizontally inside their card only.
- Keyboard: ⌘K company search across all 50; arrow keys move between tabs.

---

## 4. Repository structure

```
cfo-dashboard/
├─ PLAN.md  CLAUDE.md  docker-compose.yml  README.md
├─ backend/
│  ├─ app/
│  │  ├─ main.py                # FastAPI app, CORS, routers
│  │  ├─ config.py              # settings (TTLs, source toggles)
│  │  ├─ routers/ universe.py quote.py history.py financials.py ratios.py peers.py valuation.py events.py
│  │  ├─ services/ yahoo.py nse.py cache.py normalize.py
│  │  ├─ metrics/ ratios.py templates.py scoring.py dcf.py
│  │  └─ models/ schemas.py     # Pydantic response models
│  ├─ data/nifty50.json
│  ├─ scripts/refresh_constituents.py  warm_cache.py
│  └─ tests/
└─ frontend/
   ├─ app/ (layout.tsx, page.tsx, [symbol]/page.tsx)
   ├─ components/ selectors/ header/ kpi/ charts/ tables/ tabs/ ui/
   ├─ lib/ api.ts format.ts (INR, crore) queries.ts store.ts
   └─ types/
```

---

## 5. API contract (backend → frontend)

| Endpoint | Returns | Cache TTL |
|---|---|---|
| `GET /api/universe` | sectors → companies (symbol, name, template) | 24 h |
| `GET /api/quote/{symbol}` | LTP, change, %, OHLC, volume, 52w, mkt cap, market status, `as_of` | 30 s (market hours), 1 h otherwise |
| `GET /api/quotes?symbols=…` | batch quotes for peers / ticker tape | 60 s |
| `GET /api/history/{symbol}?range=1y&interval=1d` | OHLCV array (+ NIFTY `^NSEI` for comparison) | 5 min intraday, 6 h daily |
| `GET /api/financials/{symbol}?period=annual\|quarterly` | normalised IS, BS, CF (₹, FY labels) | 12 h |
| `GET /api/ratios/{symbol}` | computed ratios + history + sector median + percentile | 12 h |
| `GET /api/peers/{symbol}` | comparables table for the sector | 1 h |
| `GET /api/valuation/{symbol}` | multiples, 5‑yr bands, DCF inputs | 6 h |
| `GET /api/events/{symbol}` | dividends, splits, earnings date, news, shareholding | 6 h |
| `GET /api/health` | source status, cache stats | — |

All responses include `source`, `as_of`, and a `warnings[]` array (e.g. "Quarterly cash flow unavailable").

---

## 6. Phases

### Phase 1 — Scaffold & data foundation (backend)
**Goal:** a FastAPI service that returns clean, cached, normalised data for all 50 companies.

Tasks
1. Monorepo scaffold, `CLAUDE.md` with conventions, `docker-compose.yml`, `.env.example`.
2. `nifty50.json` from the table in §1 (+ `template` field per §2) and `refresh_constituents.py`.
3. `services/yahoo.py`: wrappers around `yf.Ticker(...).fast_info`, `.history()`, `.income_stmt`, `.quarterly_income_stmt`, `.balance_sheet`, `.cashflow`, `.info`, `.dividends`, `.news`. Throttle calls (a simple semaphore + retry with backoff) — Yahoo rate‑limits aggressively.
4. `services/normalize.py`: map Yahoo line‑item names to a fixed schema; convert to ₹ crore; label Indian fiscal years; handle missing fields as `null`, never 0.
5. `services/cache.py`: TTL in memory + SQLite persistence so restarts don't refetch everything.
6. Routers: `universe`, `quote`, `history`, `financials`.
7. `scripts/warm_cache.py` and a pytest smoke test that hits all 50 symbols and reports which fields are missing per company (save as `data_coverage_report.md`).

Acceptance
- `GET /api/universe` returns 14 sectors / 50 companies.
- Every symbol returns a quote and ≥4 years of annual financials, or a documented warning.
- Second request for the same symbol is served from cache (<50 ms).
- Coverage report generated.

> **Prompt for Claude Code:** "Read PLAN.md. Implement Phase 1 only (§6 Phase 1, using §1, §2, §4, §5). Backend in Python 3.12/FastAPI with yfinance. Write tests. Finish by running the smoke test across all 50 symbols and producing `data_coverage_report.md`. Stop and summarise what's missing."

---

### Phase 1 review (Phase 1.5)

A review of the Phase 1 delivery surfaced seven issues before Phase 2 (the
metrics engine) could safely build on it. All were fixed; see
`data_coverage_report.md` for live-data confirmation.

1. **Market cap can't be null.** P/E, P/B, EV, peer rankings and
   "auto-select the largest company in a sector" all depend on it, and the
   crumb-gated `quoteSummary` endpoint that originally supplied it is
   unreliable. Fixed: market cap is now computed as **price × shares
   outstanding** (`OrdinarySharesNumber`/`ShareIssued` from
   fundamentals-timeseries, no crumb needed) and is the primary path for all
   50 symbols. `quoteSummary` is kept only as a cross-check, logged (not
   surfaced) if it disagrees by >5%.
2. **Missing `receivables` was a mapping bug**, not a data gap. The wire key
   is `AccountsReceivable`; `"Receivables"` (yfinance's own display-column
   name, not Yahoo's actual field) never matched anything. Fixed in
   `normalize.py`'s `BALANCE_SHEET_MAP`.
3. **Bank/insurer inputs confirmed present**: `InterestIncome`,
   `InterestExpense`, `NetInterestIncome` (banks, NBFCs, insurers),
   `NonInterestIncome`/`NonInterestExpense` (banks), `TotalPremiumsEarned`
   (insurers) all come back from fundamentals-timeseries and are now mapped
   in `INCOME_STATEMENT_MAP`. Phase 2's NIM/ROA/cost-to-income and P/EV can
   be built on real inputs.
4. **History is short**: Yahoo gives ~4 annual years and ~5-6 quarters (see
   the coverage report's "History depth per symbol" section), not 5-10
   years. **Phase 2 must default to 3-year CAGR (not 5-year), a valuation
   band "over available history" (not a fixed 5y band), and trailing
   multiples from the last 4 quarters.**
5. **Corporate actions**: `TMPV.NS` is Yahoo's continuation of the original
   (1991-listed) Tata Motors ticker -- periods before 2025-04-01 include the
   commercial-vehicle business and are not comparable to standalone TMPV.
   `JIOFIN.NS` listed 2023-08-21; its FY23 period is a pre-listing shell
   entity. `ETERNAL.NS` (renamed from Zomato in 2024) has continuous history
   -- no issue. All three are recorded in
   `backend/data/corporate_actions.json` and surfaced via a `notes` field on
   `/api/financials` (distinct from `warnings`, which is about missing data,
   not interpretation).
6. **Tests now run against saved fixtures, never live Yahoo.** Real
   responses for one company per template (TCS/general, HDFCBANK/bank,
   BAJFINANCE/nbfc, HDFCLIFE/insurance, BSE/exchange) are captured under
   `tests/fixtures/` (`tests/fixtures/_capture.py` regenerates them). Every
   endpoint has a schema test against these fixtures. The old network-hitting
   smoke test is now marker-gated (`pytest -m smoke`) and excluded from the
   default `pytest` run.
7. **Tidy-ups**: Yahoo access now sits behind a `MarketDataSource` protocol
   (`app/services/datasource.py`); routers depend on
   `get_data_source()`, not `services.yahoo` directly, so an NSE-native or
   paid-feed implementation can be swapped in later without touching router
   code. `curl_cffi` is pinned (`==0.16.3`). `yfinance` is removed from
   `requirements.txt` -- nothing imports it.

---

### Phase 2 — Metrics engine
**Goal:** all ratios, sector benchmarks, scores and valuation computed server‑side.

Tasks
1. `metrics/ratios.py` — pure functions, unit‑tested:
   - **Growth:** Revenue, EBITDA, PAT, EPS YoY & 3/5‑yr CAGR.
   - **Profitability:** Gross, EBITDA, EBIT, PAT margins.
   - **Returns:** ROE, ROA, ROCE, ROIC; DuPont (3‑step).
   - **Leverage:** D/E, Net debt/EBITDA, Interest coverage, Debt/Assets.
   - **Liquidity:** Current, Quick, Cash ratio.
   - **Efficiency:** Asset turnover, Inventory/Debtor/Payable days, Cash conversion cycle.
   - **Cash flow:** FCF, FCF margin, CFO/PAT, Capex/Revenue.
   - **Valuation:** P/E, P/B, EV/EBITDA, EV/Sales, PEG, Dividend yield, Earnings yield, Payout ratio.
   - **Bank/NBFC derived:** NII, NIM proxy (NII / avg interest‑earning assets proxy), Cost‑to‑income, ROA, ROE.
   - **Quality flags:** Altman Z (non‑financials), Piotroski F‑score.
2. `metrics/templates.py` — which metrics show as headline KPIs per template (§2).
3. Sector medians & percentile ranks; `scoring.py` for the 6‑axis health radar (0–100 vs sector).
4. `metrics/dcf.py` — FCFF DCF with inputs exposed; reverse DCF.
5. Routers: `ratios`, `peers`, `valuation`, `events`.

Acceptance
- Unit tests for every ratio with hand‑computed fixtures (incl. division‑by‑zero and negative‑equity cases).
- Spot‑check 3 companies (TCS, HDFCBANK, RELIANCE) against Screener.in; differences >5% explained in a note.

> **Prompt:** "Implement Phase 2 of PLAN.md. Keep ratio functions pure and fully unit‑tested. Then spot‑check TCS, HDFCBANK and RELIANCE against Screener.in values and list discrepancies."

---

### Phase 3 — Frontend shell & selectors
**Goal:** polished app frame with working cascading dropdowns.

Tasks
1. Next.js + Tailwind + shadcn/ui; theme tokens (dark/light); Inter/Geist font; INR/crore formatters in `lib/format.ts`.
2. **Cascading selectors:** Sector combobox → Company combobox filtered by sector (shows logo initial, name, symbol, live % change). Changing sector auto‑selects the largest company by mkt cap. Selection syncs to URL and Zustand.
3. ⌘K global search (all 50 companies).
4. Top bar: market status pill (Open / Closed / Pre‑open based on IST 09:15–15:30, Mon–Fri, NSE holidays list), last‑updated time, units toggle.
5. Scrolling NIFTY 50 ticker tape (batch quotes).
6. Company header with animated LTP flash, 52‑week range bar, sparkline.
7. Skeletons, error boundary, empty states.

Acceptance
- Choosing a sector updates the company list instantly; choosing a company updates URL and header with no full page reload.
- Lighthouse ≥90 on performance and accessibility for the shell.

> **Prompt:** "Implement Phase 3 of PLAN.md (frontend shell only, §3 layout and UI standards). Use TanStack Query against the Phase 1/2 API. Don't build tabs yet beyond placeholders."

---

### Phase 4 — Dashboard modules (the core)
Build tab by tab, in this order, each as its own PR/commit: **Overview → Income Statement → Ratios → Balance Sheet → Cash Flow → Valuation → Peers → Shareholding & Events.**

Per tab: charts listed in §3, annual/quarterly toggle where relevant, CSV/PNG export, tooltips with formatted INR, sector median overlays, and template‑aware KPI cards.

Acceptance (per tab)
- Works for one company from each template (e.g. TCS, HDFCBANK, BAJFINANCE, HDFCLIFE, BSE).
- No chart shows fake zeros for missing data; gaps are visible and explained.
- Switching companies re‑renders in <1 s from cache.

> **Prompt (repeat per tab):** "Implement the <TAB NAME> tab from PLAN.md §3. Use ECharts. Make it template‑aware (§2). Test with TCS, HDFCBANK, BAJFINANCE, HDFCLIFE and BSE and screenshot each."

---

### Phase 5 — Live data layer
**Goal:** prices feel live without abusing the free source.

Tasks
1. During market hours, poll `/api/quote/{symbol}` every 15–30 s and batch peers every 60 s; stop polling when the tab is hidden or the market is closed.
2. Optional upgrade: backend pushes quotes over WebSocket/SSE (one upstream fetch shared by all browser tabs).
3. Intraday chart (1D, 5‑min candles) appends new points live.
4. Price‑change flash animation; "stale" badge if data is older than 5 min during market hours.
5. Circuit breaker: if Yahoo fails, fall back to NSE quote endpoint; if both fail, serve last cached value marked stale.

Acceptance
- Leaving the dashboard open for 30 min during market hours triggers no rate‑limit errors.
- Killing network access shows stale badges, not a broken page.

---

### Phase 6 — Power features & polish
1. **Compare mode:** pin 2–4 companies side by side (overlay price, ratios, financials).
2. Custom scatter/peer chart builder (pick any two metrics).
3. Watchlist and alerts (price or ratio thresholds, stored locally).
4. "Download CFO pack" — one‑click PDF of the current company's dashboard.
5. Micro‑interactions (Framer Motion), chart animations, count‑up numbers.
6. Glossary tooltips on every metric (formula + what "good" looks like).

---

### Phase 7 — QA & hardening
- Backend: pytest coverage ≥80% on `metrics/`; contract tests for every endpoint.
- Frontend: Playwright E2E — select sector → company → visit every tab, for 5 template companies; visual regression screenshots.
- Test every one of the 50 companies loads without a console error (scripted loop).
- Accessibility pass (keyboard navigation, contrast, chart aria labels).

---

### Phase 8 — Deployment (later)
- Dockerfiles for both services; `docker compose up` locally.
- Frontend → Vercel; backend → Render/Railway/Fly.io (Mumbai/Singapore region for latency); Redis for shared cache.
- Nightly cron: `refresh_constituents.py` + `warm_cache.py`; alert if NIFTY constituents changed.
- Basic auth or Clerk if it shouldn't be public.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Yahoo rate‑limits / breaks yfinance | Aggressive caching, throttling, nightly warm‑up, NSE fallback, pin yfinance version and upgrade deliberately |
| Missing/odd line items for Indian companies (esp. banks, insurers) | Template system, `null` over 0, coverage report, tooltips explaining gaps |
| Index constituents change (every Mar/Sep) | Config‑driven universe + refresh script |
| Numbers differ from Screener/annual reports | Spot‑check in Phase 2; show source and as‑of on every card |
| Scope creep | Ship Phases 1–4 as the MVP before touching 5–6 |

---

## 8. `CLAUDE.md` starter (paste into repo root)

```md
# Project: NIFTY 50 CFO Dashboard
- Always read PLAN.md first; implement only the phase requested.
- Backend: Python 3.12, FastAPI, Pydantic v2, yfinance. Frontend: Next.js 15 App Router, TS strict, Tailwind, shadcn/ui, ECharts, TanStack Query, Zustand.
- Money in ₹ crore internally; format with Indian digit grouping in the UI. Fiscal year = Apr–Mar, label "FY24".
- Missing data is null, never 0. Surface warnings to the UI.
- All ratio logic lives in backend/app/metrics as pure, tested functions. No financial maths in React components.
- Every API response includes source, as_of, warnings[].
- Run tests before declaring a task done. Summarise changes and open questions at the end of each phase.
```

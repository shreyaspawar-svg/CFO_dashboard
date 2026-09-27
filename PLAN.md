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

#### Phase 1.5 review

A second review, done after Phase 1.5 landed, found five more things Phase 2
must account for before it can trust the numbers it's computing:

1. **Stock splits and bonus issues.** Share count comes from the last annual
   balance sheet, but price is live. After a split or bonus, market cap and
   per-share numbers (EPS, book value per share, etc.) would be off by the
   split ratio unless the share count is adjusted to match the price's
   as-of date.
   > **Resolved differently than assumed.** Building the fix (fetch splits,
   > multiply the share count forward) actually *introduced* a 2x/1.5x
   > overstatement for TRENT and NESTLEIND, caught by item 5's own
   > cross-check. Investigating showed Yahoo's `OrdinarySharesNumber` is
   > already the CURRENT share count on every historical period row for a
   > company that's had a split (identical across periods spanning the
   > split date), not a point-in-time figure -- unlike a company with no
   > recent split (RELIANCE, SHRIRAMFIN), whose share count genuinely
   > varies period to period from buybacks/issuances. So no adjustment is
   > applied for market cap; `fetch_splits`/`adjust_shares_for_splits`
   > remain available (and unit-tested) for a future data source where the
   > share count really is point-in-time.
2. **Periods that aren't comparable.** TMPV's pre-demerger years and
   JIOFIN's FY23 shell year (§"Phase 1 review" item 5) must stay out of
   growth rates, health-radar scores and valuation ranges. Every response
   that reports a growth rate or CAGR must state which years it actually
   covers, and the dashboard must visibly mark the break rather than
   silently smoothing over it.
3. **Sector averages when a sector is small.** Six sectors have only 1-2
   companies (Power, Consumer Durables, Consumer Services & Retail,
   Transport & Logistics, Capital Goods & Defence, Telecom) — a "sector
   median" of 1-2 companies is meaningless. Those fall back to the median of
   companies sharing the same **template** (e.g. all `general` companies
   across sectors), and the response must say which fallback was used.
4. **Explainable scores.** Each axis of the health radar (Growth,
   Profitability, Leverage, Liquidity, Efficiency, Valuation) must return
   the underlying metrics and their weights alongside the 0-100 score, so a
   tooltip can show *why* a company scored what it scored, not just the
   number.
5. **Market-cap cross-check.** Companies where price×shares diverges from
   Yahoo's own `quoteSummary` market cap by more than 5% (already logged as
   a warning per §"Phase 1 review" item 1) must be listed in
   `data_coverage_report.md` so a bad share count or a just-happened
   split/bonus is caught, not buried in a log line.
   > **This is what caught item 1's bug.** After fixing it, two genuine
   > (not a bug) divergences remain -- SHRIRAMFIN (~20%) and ADANIENT
   > (~9%) -- both companies whose share count changes every period from
   > real issuances, where our balance-sheet-sourced count can lag
   > `quoteSummary`'s figure by up to a quarter. Documented in the coverage
   > report, not hidden.

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

### Phase 2 review

TCS and RELIANCE matched Screener.in closely. HDFCBANK didn't: ROE 8.9% vs
Screener's 13.6%, book value ₹530.58/share vs Screener's ₹393.81 -- a ~35%
gap, too large to wave off as methodology, especially for the index's
largest company. Five things came out of investigating it:

1. **ROE, book value and P/B use equity belonging to the parent company's
   shareholders only. EV adds minority interest instead.**
   > **Investigated, root cause was different than expected.** Yahoo's
   > `StockholdersEquity` already excludes minority interest by its own
   > schema (confirmed: `TotalEquityGrossMinorityInterest` -
   > `MinorityInterest` = `StockholdersEquity` exactly, for HDFCBANK,
   > BAJAJFINSV, GRASIM and TCS alike) -- so this wasn't a mapping bug. The
   > real fix was preferring Yahoo's own crumb-gated `financialData`/
   > `defaultKeyStatistics` cross-check (ROE, book value, trailing EPS)
   > over our fundamentals-timeseries-derived figures when available,
   > since it reflects a more current/correctly-scoped snapshot than an
   > annual filing ever can. `enterprise_value()` now takes
   > `minority_interest` as a fourth term, added (not netted into equity),
   > backed by a newly-mapped `MinorityInterest` balance-sheet field.
2. **EPS and P/E use profit belonging to the parent company's shareholders
   only.** Same finding: `NetIncome` already equals
   `NetIncomeCommonStockholders` in Yahoo's data (checked across 4
   companies) -- already parent-only. Fixed by the same key-statistics
   preference as item 1 (`trailingEps` over our TTM-summed diluted EPS).
3. **Check HDFC Bank's 2025 1:1 bonus issue is reflected in the share
   count.** Investigated and ruled out: `fetch_splits` does show a real
   2025-08-26 bonus, but Yahoo's `OrdinarySharesNumber` (15.39B) already
   matches `quoteSummary`'s live `sharesOutstanding` (15.42B) within 0.2%
   -- the bonus was a red herring, not the cause.
4. **A check across all 50 companies comparing our book value per share and
   EPS with Yahoo's own figures, flagging any over 10% apart.** Built (see
   `data_coverage_report.md`'s "Book value / EPS cross-check" section).
   Building it caught a second, unrelated bug it was never aimed at: our
   `book_value_per_share` calculation divided `total_equity` (stored in ₹
   crore) directly by `shares_outstanding` (a raw count) with no unit
   conversion, understating book value by ~1e7x and showing a spurious
   ~100% "divergence" for nearly every symbol. Fixed by re-expanding equity
   to raw rupees first. After that fix, the remaining >10% rows are (a)
   entries where our figure legitimately differs from Yahoo's own and the
   override already prefers Yahoo's (HDFCBANK/HDFCLIFE ROE, HDFCBANK/BSE
   book value), which is the mechanism working as intended, not an
   unresolved error, and (b) EPS divergences explained by our naive
   "sum the last 4 quarters" TTM approach differing from Yahoo's own
   `trailingEps` methodology (exceptional items, ADR-share-count quirks for
   INFY specifically -- confirmed INFY's own quarterly EPS and annual
   equity figures are inconsistently scaled in Yahoo's data, unrelated to
   our code) -- again, already using Yahoo's more-authoritative figure via
   the same override.
5. **Re-run the Screener comparison for HDFC Bank, adding Bajaj Finserv and
   Grasim.** See below.

**Spot-check after the fix:**

| Metric | HDFCBANK (ours) | HDFCBANK (Screener) | BAJAJFINSV (ours) | BAJAJFINSV (Screener) | GRASIM (ours) | GRASIM (Screener) |
|---|---|---|---|---|---|---|
| ROE | 13.84% | 13.6% | 13.50% | 13.2-13.8% | 6.53% | 5.21% (3y avg) |
| ROCE | n/a (bank) | n/a | n/a (NBFC) | n/a | 4.61% | 8.01% |
| D/E | 0.81 | -- | 4.64 | -- | 2.20 | ~2.19 |
| P/E | 16.08 | 14.4 | 27.85 | 27.6 | 38.02 | 37.8 |
| P/B | 1.87 | 1.87 (₹736 / ₹393.81 book value) | 3.63 | 3.64 | 2.09 | 2.10 |
| 3y revenue CAGR | 9.54%* | -- | 22.91% | 22% | 14.30% | 14% |

\* HDFCBANK's CAGR now correctly excludes its pre-merger FY23 (§"Phase 1
review" item 5), so it's a 2-year span dated FY24→FY26, not a 3-year one.

BAJAJFINSV matches on every metric within ~1%. GRASIM's P/E, P/B, D/E and
CAGR all match within ~1%; its ROE/ROCE gap is a basis difference (Screener
shows a 3-year average ROE, not latest-year) compounded with a capital-
employed definition difference, the same class of gap already accepted for
TCS's ROCE -- not a repeat of the HDFCBANK bug.

**Gate: HDFCBANK ROE is 0.24pp from Screener (well inside the ~1.5pp bar).
Phase 2 and 2.1 committed and tagged `phase-2`.**

---

### Phase 3 — Frontend shell & selectors
**Goal:** polished app frame with working cascading dropdowns, built against
the real Phase 1/2 API. Tab *contents* are placeholders -- Phase 4 fills
them in, one tab at a time.

Tasks

**3.1 Setup.** Next.js 15 (App Router) + TypeScript (strict) + Tailwind CSS
+ shadcn/ui, per §0. TanStack Query for data fetching/caching/polling.
Zustand for selection state (sector/company/period/unit). API types are
generated from the backend's OpenAPI schema (FastAPI serves one at
`/openapi.json` for free) via `openapi-typescript` into `types/api.ts`, run
as a script (`npm run gen:api-types`) -- not hand-maintained, so the two
sides of the stack can't silently drift apart.

**3.2 Design system.** CSS custom properties for colour tokens, dark mode
default with a light mode variant, both defined up front (not
dark-only-then-retrofitted). Numbers that update in place (price, %change)
must not reflow or shift layout -- fixed-width tabular figures. Every
gain/loss shows a ▲/▼ glyph *and* colour, never colour alone (accessibility:
colourblind users can't rely on green/red).

**3.3 Indian formatting (`lib/format.ts`).** Digit grouping
(`₹12,34,567`, not `₹1,234,567`); crore/lakh-crore unit conversion and
suffixing (`₹ Cr`, `₹ L Cr`); FY labels (`FY24` for the year ending March
2024, matching `backend`'s own convention exactly); every formatter takes
`null`/`undefined` and renders `"—"`, never `0` or `NaN`.

**3.4 Cascading selectors.** Sector combobox → company combobox filtered to
that sector (row shows a logo-initial avatar, name, symbol, live %change).
Changing sector auto-selects that sector's largest company by market cap.
Selection is the source of truth in the URL (`?sector=...&symbol=...`) via
Zustand kept in sync, not the other way around -- so a shared link
reproduces the exact view.

**3.5 ⌘K global search.** All 50 companies, fuzzy-matched on symbol, full
name, *and* common/former names -- "Zomato" must find ETERNAL, "Tata
Motors" must find TMPV (a small alias table, since neither is derivable
from the API alone).

**3.6 Top bar.** Market-status pill (Open/Closed/Pre-open; IST
09:15-15:30, Mon-Fri -- an NSE holiday calendar is out of scope per Phase
1's own note, so holidays show as "Closed" same as a weekend); units toggle
(₹ Cr / ₹ L Cr, persisted); theme toggle; a scrolling, clickable NIFTY 50
ticker tape (batch `/api/quotes`) that jumps to that company on click.

**3.7 Company header + KPI row.** LTP with a brief flash/pulse on change
(not a jarring repaint); 52-week range bar (low---LTP---high, positioned
proportionally); template-aware KPI cards (§2 -- a bank's cards are not a
general company's cards) each showing its value *and* the sector median
from `/api/ratios`; a warning banner when `/api/financials`' `notes` is
non-empty (TMPV, JIOFIN, HDFCBANK's pre-merger note) -- visible, not buried
in a tooltip.

**3.8 Placeholder tabs.** Overview / Income Statement / Balance Sheet /
Cash Flow / Ratios / Valuation / Peers / Shareholding & Events as empty-state
tab shells (title + "coming in Phase 4") -- routing and layout only.

**3.9 Loading & error states.** Skeleton loaders sized to match their
eventual content (no layout shift when data arrives); an error boundary per
data-fetching region (one endpoint failing shouldn't blank the page);
explicit empty states.

**3.10 Responsive layout.** Desktop (3-column), tablet, and phone
breakpoints for the shell (top bar, header, KPI row, tab bar) -- verified at
1440px and 390px, not just designed for them.

Acceptance
- Choosing a sector updates the company list instantly; choosing a company updates URL and header with no full page reload.
- ⌘K finds ETERNAL for "Zomato" and TMPV for "Tata Motors".
- No `0`/`NaN` rendered anywhere data is missing -- `"—"` instead.
- Vitest (formatters, store logic) and a Playwright smoke test (load → pick
  sector → pick company → URL updates) both pass.
- Screenshots at 1440px and 390px, dark and light, for TCS/HDFCBANK/TMPV
  (12 total) reviewed before Phase 4 starts.
- Lighthouse ≥90 on performance and accessibility for the shell.

> **Prompt:** "Implement Phase 3 of PLAN.md exactly as specified (tasks 3.1-3.10). Use TanStack Query against the real Phase 1/2 API. Don't build tab contents beyond placeholders."

---

### Phase 3 review

Phase 3 itself passed review (screenshots looked right on both themes and both
breakpoints). Two housekeeping items and one substantive concern about Phase
2.1's fix came out of it:

- **Housekeeping:** disable Next.js's dev-mode indicator badge (it overlapped
  KPI card text in a couple of the review screenshots) and update CLAUDE.md,
  which still says "Next.js 15" -- the registry's current release when this
  was scaffolded was 16.
- **The Phase 2.1 concern.** Phase 2.1 fixed HDFCBANK's ROE by displaying
  Yahoo's own ready-made `financialData.returnOnEquity` instead of our
  fundamentals-timeseries-derived figure -- closing the gap to Screener, but
  without pinning down *why* our own number was off. That's fine for one KPI
  card in isolation. It stops being fine the moment Phase 4 builds a
  **history chart** for the same metric (an "ROE over time" trend) from our
  own calculation: the KPI card would show Yahoo's number and the chart's
  latest point would show ours, disagreeing on the same screen for the same
  metric. Yahoo's key-statistics endpoint is also crumb-gated and fails
  silently to our own (different) number when the crumb isn't issued --
  meaning the metric a viewer sees can depend on request-to-request crumb
  luck, not just on the data.

#### Phase 2.2 — One method per metric, with its provenance

1. **Find the actual root cause and write it down.** (Superseding Phase
   2.1's "minority interest" and "2025 bonus" hypotheses -- both investigated
   there and ruled out.) HDFCBANK's own `StockholdersEquity` **oscillates
   between quarters in a way no real bank's balance sheet does**:
   Dec-24 ₹5.02L Cr → Mar-25 ₹7.68L Cr → Jun-25 ₹5.43L Cr → Sep-25 ₹7.90L Cr
   → Mar-26 ₹8.17L Cr. Revenue and NII show a matching Mar-quarter anomaly.
   The annual filings we use happen to land consistently on the *high*
   (post-mega-merger-conglomerate, consolidated-looking) reading every year,
   while Screener.in's figure sits close to the *low* reading. Most likely
   cause: Yahoo's free feed inconsistently sources standalone vs.
   consolidated statements per quarter for HDFC Bank specifically -- a
   conglomerate that, post the 2023 HDFC Ltd merger, consolidates large
   insurance/AMC/NBFC subsidiaries whose capital structure differs sharply
   from the standalone bank's. This is a data-quality property of the free
   source for this one (large, structurally unusual) company, not a mapping
   bug in our code. Full writeup: `backend/docs/data-notes.md`.
2. **One calculation method per metric.** Stop silently overriding our own
   computed ROE/ROA/book-value/EPS with Yahoo's key-statistics value: a KPI
   card and its trend chart must be the *same function call* over different
   periods, or they can disagree. Yahoo's key-statistics endpoint becomes a
   **fallback only** (used when our own calculation is impossible, e.g. too
   few periods) and a **cross-check** (flagged if it disagrees with our own
   by >10%, per Phase 2.1 item 4) -- never a silent substitute for a value we
   were able to compute ourselves.
3. **Method provenance on every ratio.** Each `RatioValue` in `/api/ratios`
   now carries `method`: `"computed"` (our own calculation succeeded --
   the common case), `"yahoo_fallback"` (ours was `None`; Yahoo's
   crumb-gated figure filled in), or `"unavailable"` (neither worked).
4. **Stop crore/share-count/per-share amounts from being mixed up.** The
   Phase 2.1 book-value bug (equity in ₹ crore divided by a raw share count,
   understating book value ~1e7x) happened because unit conversions were
   ad-hoc `* CRORE` multiplications scattered at call sites. `metrics/units.py`
   makes the three units (`Crore`, `Rupees`, `Shares`) distinct types with
   one explicit conversion function each, so a future mixing mistake is a
   type error, not a silent 1e7x bug. A **plausibility check across all 50
   symbols** (book value per share in a sane ₹ band; market-cap ÷ shares ≈
   live price; EPS in a sane band relative to price) catches anything
   implausible that slips through anyway.

**Gate:** for HDFCBANK, the KPI card's ROE and the latest point of its
computed ROE history must agree within 1.5pp (they're now the same
calculation, so this should hold exactly, not approximately) -- and the
plausibility check must pass for all 50 symbols. If not, stop and report
before Phase 4 starts.

**Gate result: passed.** HDFCBANK's KPI ROE is `method: "computed"` =
8.9% (0pp gap from itself, by construction). Building the plausibility
check surfaced two more real, non-HDFCBANK findings before it passed
cleanly: INFY's own EPS is unit-inconsistent at the source in both its
annual and quarterly Yahoo data (not just quarterly, as first suspected),
and INDIGO's naive TTM-summed EPS (+56, +14, -66, -6) net out near zero,
implying a P/E in the thousands even though each quarter's figure is
individually correct. Both are now handled by the same general mechanism:
an implausible-but-non-`None` own-value is treated like a missing one
(falls back to Yahoo, or to `None`), never displayed as-is. Full
writeup: `backend/docs/data-notes.md`. All 50 symbols pass the
plausibility check; `data_coverage_report.md`'s divergence table is
otherwise unchanged (HDFCBANK/HDFCLIFE's ROE and HDFCBANK/BSE's book value
still show, by design, per item 3's `method` tagging).

> **Prompt:** "Read PLAN.md → 'Phase 3 review', then Phase 4 §4.0/§4.1.
> Step A: disable the dev indicator, update CLAUDE.md for Next.js 16, commit
> Phase 3, tag phase-3. Step B (Phase 2.2): items 1-4, gated as above -- stop
> and report if the gate fails. Step C: build §4.0 and §4.1. Don't commit
> Phase 2.2 or Phase 4; stop and summarise."

---

### Phase 4 — Dashboard modules (the core)
Build tab by tab, in this order, each as its own PR/commit: **Overview → Income Statement → Ratios → Balance Sheet → Cash Flow → Valuation → Peers → Shareholding & Events.**

Per tab: charts listed in §3, annual/quarterly toggle where relevant, CSV/PNG export, tooltips with formatted INR, sector median overlays, and template‑aware KPI cards.

#### 4.0 Chart foundation

Built once, before any tab uses it, so every chart gets the same for free:
- PNG/CSV export on every chart.
- One shared colour theme, defined for both dark and light mode (reusing the
  design tokens from Phase 3, not a second palette).
- Gaps for missing data points, never a zero standing in for "no data".
- **Break markers** at a corporate-action cutoff (TMPV's demerger, JIOFIN's
  listing, HDFCBANK's merger -- the same `corporate_actions.json` cutoffs
  already driving `/api/financials`' `notes` and the growth-figure exclusion)
  so a viewer sees *why* a series jumps, not just that it does.

#### 4.1 Overview tab

- Price chart with 50/200-day moving averages and dividend-payment markers.
- Performance vs. the NIFTY 50 index and vs. the sector (relative return,
  not just absolute price).
- Returns table (1M/3M/6M/1Y/3Y/5Y or whatever span the data supports --
  per PLAN.md "Phase 1 review" item 4, don't imply history that isn't there).
- The health radar (`/api/ratios`' 6-axis score), rendered so it explains
  *why* each axis scored what it did (the metrics/weights already returned
  by the API), not just a bare 0-100 number.
- Financial snapshot that changes by business-model template (§2) -- a
  bank's snapshot is not a general company's snapshot.
- Key stats row including **beta** (a new backend addition -- see below).
- News headlines and analyst target price (also new backend additions).

Backend additions §4.0/§4.1 need: beta (vs `^NSEI`, computed from historical
returns -- Yahoo doesn't reliably expose this for NSE tickers), analyst
target price (best-effort via the same crumb-gated key-statistics path,
`null` when unavailable), moving averages (computed from `/api/history`,
not fetched), and relative-performance series (symbol return vs. `^NSEI`
and vs. sector-peer-average return, both already fetchable).

Acceptance (per tab)
- Works for one company from each template (e.g. TCS, HDFCBANK, BAJFINANCE, HDFCLIFE, BSE).
- No chart shows fake zeros for missing data; gaps are visible and explained.
- Switching companies re‑renders in <1 s from cache.

> **Prompt (repeat per tab):** "Implement the <TAB NAME> tab from PLAN.md §3. Use ECharts. Make it template‑aware (§2). Test with TCS, HDFCBANK, BAJFINANCE, HDFCLIFE and BSE and screenshot each."

---

### Phase 4.1 review

The Overview tab itself rendered correctly (charts, exports, break marker, template-aware
snapshot all worked against live data), but two numbers were wrong, so it wasn't approved
for commit yet.

1. **HDFCBANK's ROE is consistent now, but consistently wrong.** Phase 2.2 made the KPI
   card and its trend chart agree with each other (8.9% everywhere) -- but neither agrees
   with Screener's 13.6%. The Phase 2.2 gate only checked internal agreement, so it passed
   while missing the actual point: agreement with a wrong number is still wrong. Per
   `docs/data-notes.md`, the root cause is that Yahoo's quarterly equity for HDFCBANK
   alternates between two different reporting bases (~₹5L Cr and ~₹7.8L Cr) quarter to
   quarter. Fix required (Phase 2.3 item 1, below): detect that alternation generically
   across all 50 symbols (not a HDFCBANK-specific check), use annual-only figures with
   profit and equity on the same basis for any symbol it's detected on, and if the number
   still doesn't reconcile, show it with an amber "source data inconsistent" badge rather
   than presenting it as clean.
2. **The beta figures are almost certainly a bug.** Large NIFTY constituents typically run
   0.6-1.3x; HDFCBANK (a tenth of the index by weight) coming in near 0.2x isn't
   believable. `compute_beta`'s own unit tests pass, but they only ever fed it synthetic,
   already-aligned arrays -- they never exercised the part of the pipeline that produces
   the two return series from real bars. The likely cause: `daily_returns` strips dates
   and returns a bare list of floats, and the two series (symbol vs `^NSEI`) get zipped
   together by **list position** in `compute_beta`. If the two instruments' bar lists ever
   have a different set of trading dates (a stock-specific halt, a gap the free feed drops
   for one ticker but not the other), every return after that point is paired against the
   wrong day -- which washes out real covariance without raising an error. The performance-
   vs-NIFTY chart pairs its two series by array index the same way, so it's suspect too.
   Fix required (Phase 2.3 item 2): pair returns by shared trading date, not position, on
   both sides. Verify with a test built from **real** TCS + `^NSEI` daily bars (not
   synthetic data), and a side-by-side table of our beta vs Yahoo's own reported beta for
   HDFCBANK, RELIANCE, TCS, ICICIBANK and TMPV.
3. **Minor: the frontend keeps its own copy of demerger/merger cutoff dates**
   (`lib/corporate-action-cutoffs.ts`), duplicating `backend/data/corporate_actions.json`.
   That copy will silently drift the next time a corporate action is added or a date is
   corrected backend-side. Fix required (Phase 2.3 item 3): expose the cutoff as a
   structured field on `/api/financials` (`comparable_from` date + a short
   `comparable_from_label` for the chart) and have `price-chart.tsx` read it from there;
   delete the local mirror file.

#### Phase 2.3 — Fix the basis mismatch, the alignment bug, and the duplicated dates

1. **Detect equity-basis oscillation generically, across all 50 symbols.** A new
   `app/metrics/basis_consistency.py` flags a symbol whose quarterly `total_equity`
   series shows alternating large-magnitude swings that revert (not a monotonic trend --
   real organic equity growth doesn't zig-zag double digits quarter over quarter). For a
   flagged symbol, compute ROE/ROA from **annual** net income over **annual** average
   equity (both from the same filing, hence the same basis) instead of TTM-quarterly-summed
   net income over annual average equity -- eliminating the numerator/denominator basis
   mismatch that let a same-report-consistent-looking figure still be wrong. If, after
   that fix, the result still diverges materially from Yahoo's independent key-statistics
   cross-check (the existing >10% divergence mechanism from Phase 2 review item 4), tag the
   ratio with a `data_quality: "inconsistent"` flag and a reason string instead of
   presenting it as a clean number -- surfaced in the UI as an amber badge with the reason
   in a tooltip, not silently swapped for a different value (that would reintroduce the
   exact KPI-vs-chart disagreement Phase 2.2 was built to close).
2. **Pair return series by trading date, not list position.** A new
   `paired_daily_returns(symbol_bars, benchmark_bars)` in `metrics/beta.py` builds a
   date -> close map for each series, intersects the dates, and computes both series'
   day-over-day returns only over that common, sorted date set. `compute_beta` itself is
   unchanged (the covariance/variance math was always correct) -- the fix is entirely in
   how the two return series are produced before reaching it. The same date-keyed join
   replaces the positional zip in `performance-chart.tsx`. A new test loads real captured
   TCS + `^NSEI` 1-year daily bars (`tests/fixtures/beta/`) and asserts the resulting beta
   falls in a plausible band, plus a regression assertion that the old positional pairing
   on the same real data would have produced a materially different (lower) result --
   proving the fix isn't a no-op on real data, not just on synthetic arrays.
3. **`comparable_from` / `comparable_from_label` on `/api/financials`.** Sourced from
   `corporate_actions.json`'s existing `cutoff_period_end`, plus a new short `label` field
   per entry (e.g. "Demerger from Tata Motors") for the chart marker text.
   `lib/corporate-action-cutoffs.ts` is deleted; `price-chart.tsx` reads the cutoff from
   `useFinancials(symbol)` (already fetched elsewhere in the app, same cache) instead.

**Gate:** HDFCBANK's ROE is within ~1.5pp of Screener's 13.6%, **or** amber-badged with a
documented reason -- **and** the real-bar-data beta test passes (plausible value, and
demonstrably different from the old positional-pairing result). If both hold, commit
Phase 2.2 + 2.3 + 4.0/4.1 and tag `phase-4.1`. If not, stop and report before touching 4.2.

---

### 4.2 Income Statement tab

Second tab built on the Phase 4.0 chart foundation, per §3 tab 2 and §2's template
awareness -- same rigor as 4.1: real data, gaps not zeros, comparable-period exclusion,
`method`-tagged figures wherever a metric can be computed two ways.

- **Annual/Quarterly toggle**, backed by `/api/financials?period=annual|quarterly`
  (already exists) -- switching doesn't refetch the other period if it's already cached.
- **Revenue / EBITDA / PAT combo chart**: bars for the three absolute figures, a secondary
  right-hand axis with EBITDA-margin and PAT-margin lines. Pre-corporate-action periods
  (per `comparable_from`) are visually distinguished (the same break-marker convention
  from 4.0), not silently included in a trend line they'd distort.
- **YoY/QoQ growth bars** for revenue, EBITDA and PAT, computed only over comparable
  periods (reuses the backend's existing `comparable_periods` filtering -- no new growth
  math, just charting what `/api/ratios`' growth figures already are, plus a per-period
  breakdown the KPI card doesn't show).
- **Waterfall** (latest comparable annual period): Revenue → COGS → Opex → EBITDA → D&A →
  Interest → Tax → PAT. Template-aware: a bank/NBFC/insurer template has no COGS/Opex
  split in the way a `general` company does (§2) -- show NII/NIM-based line items instead
  of forcing the general-company waterfall shape onto a business model it doesn't fit, and
  label a step "—" (not 0) when the underlying line item is genuinely absent from the free
  data source.
- **Expandable table**: all mapped income-statement line items across every comparable
  period, plus a CAGR column (using the same span-plausibility guard already in
  `lib/technical.ts`'s `computeReturnsTable` -- don't imply a 5-year CAGR from 3 years of
  data here either).
- Every chart gets PNG/CSV export via the existing `ChartCard` (4.0); no new export
  mechanism.

Acceptance
- Works for one company per template (TCS, HDFCBANK, BAJFINANCE, HDFCLIFE, BSE) plus a
  corporate-action symbol (TMPV or HDFCBANK) to confirm the break marker/exclusion shows
  correctly on a real discontinuity.
- No fabricated growth/CAGR figures for spans the data doesn't support.
- All tests green (backend pytest, frontend vitest, Playwright e2e).

> **Prompt:** "Read PLAN.md → 'Phase 4.1 review' and section 4.2.
> Step A (Phase 2.3): fix items 1-3, gated as above -- report the basis-oscillation hits
> across all 50 symbols, the new HDFCBANK ROE with method/badge status, and a beta table
> (ours vs Yahoo) for HDFCBANK, RELIANCE, TCS, ICICIBANK and TMPV. If the gate passes,
> commit Phase 2.2 + 2.3 + 4.0/4.1 and tag phase-4.1. If not, stop and report.
> Step B: build 4.2. Run all tests. Screenshot it at 1440px (dark) for TCS, HDFCBANK,
> HDFCLIFE and INDIGO, and at 390px (light) for TCS. Copy those screenshots plus the 4.1
> Overview ones for TCS and HDFCBANK into review/ at the repo root. Don't commit 4.2; stop
> and summarise."

---

### Phase 4.2 review (planner): accepted
- Phase 2.3 accepted: date-keyed beta fix verified; HDFCBANK ROE/ROA amber-badged with data_quality "inconsistent". Drop Yahoo's beta as a cross-check (unreliable for NSE) and note that in docs/data-notes.md.
- Distinguish "missing" from "not meaningful" everywhere: growth from a non-positive base (e.g. INDIGO PAT −₹306 Cr → +₹8,172 Cr) shows "n.m." with the tooltip "Not meaningful: prior-period value ≤ 0", not "—". The API returns `reason: "not_meaningful"` vs `reason: "missing"`. Apply this to tables, tooltips and KPI cards.
- Backlog (Phase 6): add `manual_overrides.json` for annual-report figures with a source citation (first candidate: HDFCBANK equity and PAT), shown with method "manual_override".

#### 4.3 Ratios tab

**Layout:** a "Strengths & watch-outs" panel at the top, then ratio card groups, then a DuPont chart, a ratio-history heatmap, a peer strip plot, and quality scores.

**1. Ratio card groups (template-aware)**
- General: Profitability (Gross, EBITDA, EBIT, PAT margin), Returns (ROE, ROCE, ROIC, ROA), Leverage (D/E, Net debt/EBITDA, Interest coverage, Debt/Assets), Liquidity (Current, Quick, Cash), Efficiency (Asset turnover, Inventory/Debtor/Payable days, Cash conversion cycle), Cash flow (FCF margin, CFO/PAT, Capex/Revenue), Per share (EPS, BVPS, DPS, payout).
- Bank/NBFC: NIM (proxy), Cost-to-income, ROA, ROE, Leverage (Assets/Equity), NII growth, PAT growth, P/B. Also show GNPA, NNPA, CASA and credit cost as "—", with the tooltip "Not in free data source".
- Insurance: Premium growth, PAT margin, ROE, P/B. P/EV and solvency as "—" (not in free data source).
- Exchange: General minus inventory/debtor days.

**2. Ratio card spec**
- Latest (TTM where applicable) value and a 4-year sparkline with a break marker at `comparable_from`.
- A sector/template median tick on a small horizontal range bar (sector min → max).
- Percentile badge, e.g. "Top 20% in sector" / "Bottom quartile vs template".
- Every ratio has a `direction` field in the API (`higher_better` | `lower_better` | `neutral`, e.g. D/E lower_better, CCC lower_better). Badge colour uses direction, so a low D/E is shown as good.
- `method` and `data_quality` badges, as on the KPI cards.
- Glossary tooltip: formula, plain-English meaning, and what "good" typically looks like. The glossary lives in `backend/data/glossary.json` (single source), served at `/api/glossary`. Include the ROCE definition: EBIT ÷ (equity + total debt), average of opening and closing.
- No percentile badge if there are fewer than 3 peers. Show "vs template" when `benchmark == "template"`.

**3. DuPont decomposition**
- General: ROE = PAT margin × Asset turnover × Equity multiplier, one grouped chart across years plus a latest-year "equation" strip showing the three factors and the result.
- Bank/NBFC: ROE = ROA × Leverage.
- The product must reconcile to the ROE shown on the card within 0.5 pp; otherwise show a note explaining the gap (average vs closing balances).

**4. Ratio-history heatmap:** rows are key ratios, columns are fiscal years. Colour each cell by the company's position vs the sector median that year (diverging palette, direction-aware), with the value printed in each cell. Accessible: values are always printed, colour is secondary.

**5. Peer strip plot:** a dropdown to pick any ratio; a dot for every sector (or template) peer on one axis, the selected company highlighted and labelled, a median line, and clicking a dot navigates to that company.

**6. Quality scores**
- Altman Z with its 5 components and zones (safe / grey / distress).
- Piotroski F (0–9) with a checklist of all 9 tests, each pass/fail with its numbers.
- Hidden for bank/NBFC/insurance templates with "Not applicable to financial companies".

**7. Strengths & watch-outs (rule-based, not AI)**
- Rules live in `backend/app/metrics/signals.py`, returned by `/api/ratios` as `signals[]` with `{type: strength|watch, rule, message, values}`.
- Example rules:
  - ROCE > sector p75 → strength
  - D/E rising 3 years in a row → watch
  - CFO/PAT < 0.8 for 2+ years → watch
  - Margin expanding 3 years in a row → strength
  - Interest coverage < 3 → watch
- Every message cites its numbers (e.g. "ROCE 56.5% vs sector median 28.1%"). At most 4 strengths and 4 watch-outs, ranked by magnitude.
- Unit-test every rule.

**Acceptance**
- Works for TCS, HDFCBANK, BAJFINANCE, HDFCLIFE, BSE and TMPV.
- Percentiles and medians match what the Peers tab will use (same backend function).
- DuPont reconciles or explains; a direction test proves low D/E renders as favourable.
- No 0/NaN anywhere; "—" vs "n.m." is used correctly.

4.3 fixes (materiality floors, template-aware signals, DuPont labelling) — done, see commit `phase-4.3`.

4.5 fixes (investments/loan/deposit mapping, minority-interest balance check, FX-aware Sankey) — done, Other-current/non-current split added, accepted as free-source gap — done, see commit `phase-4.5`.

4.6 Valuation tab, 4.7 Peers tab, 4.8 Shareholding & Events tab, plus INFY multiple-plausibility and negative-balance-sheet-bucket fixes — done, see commit `phase-4`.

Phase 5 (live-price polling/single-flight/stale fallback, 1D intraday chart, 50x8-tab QA crawl clean, Lighthouse, README) — done, see tag `v1.0`.

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

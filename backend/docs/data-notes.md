# Data-source notes

Known quirks in the free Yahoo Finance data source, how each was found, and
what this app does about it. Check here before re-investigating something
that looks like a bug -- it may already be a documented, deliberate
tradeoff. See also `backend/data/corporate_actions.json` for the narrower
case of demergers/spinoffs/mergers that make part of a symbol's history
non-comparable.

## HDFCBANK: `StockholdersEquity` oscillates between quarters (Phase 2.2)

**Symptom.** Our own book value per share for HDFCBANK (₹530.58, from
`total_equity / shares_outstanding` on the latest annual balance sheet)
diverged ~35% from Screener.in's (₹393.81/₹390). ROE showed the same
pattern: ours 8.9%, Screener's 13.6%.

**Investigated and ruled out:**
- *Minority interest folded into equity.* Checked `StockholdersEquity` vs
  `TotalEquityGrossMinorityInterest` vs `MinorityInterest` directly: for
  HDFCBANK, TCS, BAJAJFINSV and GRASIM alike, `StockholdersEquity` +
  `MinorityInterest` = `TotalEquityGrossMinorityInterest` exactly.
  `StockholdersEquity` already excludes minority interest, as its name and
  Yahoo's schema both promise. Not the bug.
- *The 2025 HDFC Bank bonus issue not reflected in the share count.*
  `fetch_splits` does show a real 2025-08-26 bonus on HDFCBANK.NS. But
  Yahoo's `OrdinarySharesNumber` (15.39B) already matches its own
  `quoteSummary.sharesOutstanding` (15.42B) within 0.2% -- the share count
  is fine. Not the bug. (This is a *different* mechanism from the actual
  Phase 1.5 split bug below -- HDFCBANK's share count is simply current,
  not stale.)

**Actual root cause.** Pulling HDFCBANK's quarterly `StockholdersEquity`
directly:

| Quarter end | Equity (₹ Cr) |
|---|---|
| 2024-12-31 | 5,02,190 |
| 2025-03-31 | 7,67,689 |
| 2025-06-30 | 5,42,634 |
| 2025-09-30 | 7,90,362 |
| 2026-03-31 | 8,16,740 |

No real bank's book equity swings ±30-50% quarter to quarter and back --
this is a data artifact, not economics. `TotalRevenue` and
`NetInterestIncome` show a matching anomaly concentrated in the March
quarter. The most likely explanation: Yahoo's free feed inconsistently
sources **standalone vs. consolidated** financial statements per quarter
for HDFC Bank specifically -- a company that, post the 2023 HDFC Ltd
merger, consolidates large insurance/AMC/NBFC subsidiaries (HDFC Life,
HDFC AMC, HDB Financial, HDFC Ergo) whose combined capital structure
differs sharply from the standalone bank's. The annual filings we use
happen to land consistently on the *high* (consolidated-looking) reading
every year (FY25 ₹7,67,689 Cr, FY26 ₹8,16,740 Cr -- a sensible ~6.4% YoY
step, so internally consistent), while Screener.in's displayed figure sits
close to the *low* reading. Yahoo's own `defaultKeyStatistics.bookValue`
(₹393.81) and `financialData.returnOnEquity` (13.84%) also sit close to
the low/Screener reading -- consistent with Yahoo's own summary-stats
pipeline sourcing a different quarter or basis than its
fundamentals-timeseries pipeline for this company.

**What this app does about it (Phase 2.2).** Per "one calculation method
per metric" (PLAN.md "Phase 3 review"), a KPI card and any history/trend
chart for the same metric must be the same function call over different
periods -- so silently substituting Yahoo's snapshot value (as Phase 2.1
did) was the wrong fix, even though it happened to match Screener more
closely. Instead:
- `/api/ratios` always prefers **our own** fundamentals-timeseries-derived
  calculation. HDFCBANK's ROE therefore shows **8.9%**, not 13.6-13.84%,
  and is tagged `method: "computed"`.
- Yahoo's key-statistics figure is used only as a **fallback** (when our
  own calculation is `None`, e.g. too few periods) and as a **cross-check**
  (flagged in `data_coverage_report.md` when it disagrees with ours by
  >10% -- HDFCBANK's ROE and book value both do, by design, since this
  writeup exists precisely because they disagree).
- The gap vs. Screener for HDFCBANK (and structurally, for any other
  large-conglomerate bank/NBFC with sizeable consolidated subsidiaries) is
  a **known, documented, accepted limitation** of this free data source,
  not a bug to keep chasing. A future paid data source with reliable
  standalone-vs-consolidated tagging would resolve it properly.

**Update (Phase 2.3): the "one method per metric" gate above passed while
missing the actual point.** It checked that the KPI card and its trend
chart *agree with each other* -- they did (8.9% everywhere) -- not whether
either agrees with reality. `app/metrics/basis_consistency.py` now detects
the oscillation generically (checked against real quarterly equity for all
50 symbols; only HDFCBANK's swings -- e.g. +53% then -29% the next quarter
-- exceed the 12% same-direction-reversal threshold, everyone else's
adjacent-quarter equity growth stays well clear of it even for one-off real
events like ADANIENT's +60.8% capital raise, which doesn't *reverse*).

For a flagged symbol, ROE/ROA are computed from **annual** net income over
**annual** average equity, so numerator and denominator are guaranteed to
come from the same filing. For HDFCBANK specifically this turned out to be
a no-op on the *number* -- it was already falling back to annual net income
for an unrelated reason (fewer than 4 comparable TTM quarters) -- which is
itself informative: it confirms the gap isn't a numerator/denominator
mismatch *within* our own calculation, it's that the annual filings
themselves consistently land on the wrong (high/consolidated) basis, as
already documented above. Annual-basis alignment fixes the class of bug
where our own two inputs disagree on basis; it cannot fix a source that's
internally consistent but wrong.

So HDFCBANK's ROE and ROA now carry `data_quality: "inconsistent"` with a
reason string (surfaced as an amber badge in the UI, tooltip has the
reason) instead of being presented as a clean 8.9% -- an honest signal that
the source data disagreement is real and unresolved, rather than another
attempt to force reconciliation to Screener's number that would just
reintroduce the Phase 2.1/2.2 problem in a new shape.

## INFY: quarterly EPS and annual equity look inconsistently scaled

Phase 2.1's 50-symbol book-value/EPS divergence check flagged INFY's own
EPS calculation at ~99% off Yahoo's `trailingEps` (ours ~₹0.80 vs Yahoo's
₹77.52) and book value similarly (~₹2.42 vs ₹227.86). INFY's quarterly
`DilutedEPS` values from Yahoo are anomalously tiny (~0.18-0.23) relative to
its annual figure (~₹136+), while `StockholdersEquity` (₹978.6 Cr, absurdly
low for a company of INFY's real size) shows a similar scale mismatch.
Likely related to INFY's dual listing (NSE ordinary shares + US ADR) and
Yahoo's feed occasionally reporting a per-ADR-equivalent figure inconsistent
with the plain share count elsewhere in the same feed. The `method`
fallback (Yahoo's key-statistics figure, which is correctly scaled) already
protects the displayed P/E and P/B for INFY from this; flagged for
visibility, not fixed at the source (we don't control Yahoo's feed).

## INDIGO: summing volatile quarterly EPS can net out near zero

A second, more general problem the item-4 plausibility check found (not
specific to any one symbol's data quality): INDIGO's last 4 quarterly
diluted EPS were +56.24, +14.20, -65.62, -6.15 -- individually plausible
figures for a cyclical airline, but **summed** for a naive TTM figure they
net out to -1.33. Dividing INDIGO's ₹4,940 price by -1.33 implies a P/E of
**-3,714x**, wildly implausible, even though nothing in the underlying
per-quarter data is wrong. (INFY's issue above is different: its own data
*is* wrong at the source, at both the annual and quarterly grain.)

**Fix:** `compute_symbol_metrics` gates the TTM-summed EPS (and, by the
same reasoning, the fundamentals-derived book value per share) through
`app.metrics.plausibility` before using it. An implausible-but-real value
is now treated the same as a missing one: fall back to Yahoo's
`trailingEps`/`bookValue` if available, else `None` (`method:
"unavailable"`) -- never displayed as-is. This is the general mechanism
that also protects against INFY's issue and the Phase 2.1 book-value bug
recurring in a new symbol, per PLAN.md Phase 2.2 item 4.

## TRENT / NESTLEIND: share count is already current, not point-in-time

Phase 1.5 review assumed `OrdinarySharesNumber` was a point-in-time,
per-period balance-sheet figure that would go stale relative to a live
price after a stock split, and built logic to carry it forward through any
splits in between. Building it *introduced* a bug: for TRENT (a real 3:2
split on 2026-06-04) and NESTLEIND (a real 2:1 split on 2025-08-08), the
share count is **identical across every historical period Yahoo returns**,
including years before either split -- Yahoo normalizes this field to the
*current*, already-post-split count regardless of which period it's
attached to. Applying a split-ratio adjustment on top of an already-current
count double-counted the split, overstating market cap by exactly that
ratio (100% for NESTLEIND, 50% for TRENT) -- caught by the market-cap
cross-check. Fix: `fetch_market_cap_detailed` does not adjust the share
count for splits. (Confirmed this is specific to a post-split company: a
company with genuine mid-cadence issuance/buybacks, e.g. RELIANCE or
SHRIRAMFIN, shows its share count varying naturally period to period, as
expected of real point-in-time data.)

## SHRIRAMFIN / ADANIENT: residual market-cap cross-check divergence

After the above fix, two symbols still show a >5% market-cap divergence
between price×shares and `quoteSummary`'s figure in most smoke-test runs:
SHRIRAMFIN (~20%) and ADANIENT (~9%). Both have share counts that
genuinely change every period (real issuances, not a split artifact) --
our figure is sourced from the latest **annual or quarterly balance
sheet**, which can lag `quoteSummary`'s live figure by up to a quarter.
This is an inherent freshness limitation of a balance-sheet-anchored share
count, not a bug -- documented in `data_coverage_report.md`'s divergence
table each run, not hidden.

## Beta: two independently-null-padded return series can't be zipped by position (Phase 2.3)

**Symptom.** Every computed beta (vs `^NSEI`) came back implausibly low --
TCS 0.07x, HDFCBANK 0.06x, TMPV 0.19x, ICICIBANK 0.008x, RELIANCE 0.06x --
against typical NIFTY-constituent betas of roughly 0.6-1.3x.

**Investigated: the two instruments' trading-day sets were assumed to be
the problem, but weren't.** A live check of TCS/HDFCBANK/TMPV/ICICIBANK/
RELIANCE vs `^NSEI`'s 1-year daily chart found every pair had **identical**
bar counts (252) and **identical** date sequences -- individual NSE stocks
never have a session `^NSEI` doesn't, at least not over a clean 1-year
window. So the bug wasn't "different trading calendars" as first
suspected.

**Actual root cause: `^NSEI`'s own chart feed has scattered null closes
that the stocks don't share.** `^NSEI`'s 1-year series had 5 null closes
(2026-01-15, 2026-05-01, 2026-05-28, 2026-06-26, 2026-09-14) on days every
stock checked had a normal close. The old `daily_returns` dropped any pair
touching a null *independently per series* -- each of `^NSEI`'s 5 nulls
drops 2 of *its own* return entries (the pair before and the pair after)
without dropping any of the stock's, so `^NSEI`'s return list ends up 10
entries shorter, spread across 5 different points in the year.
`compute_beta` then zipped `symbol_returns[-n:]` against
`benchmark_returns[-n:]` by **trailing list position**: from the first
null onward, "same position" stopped meaning "same day," which washes out
real covariance without raising an error (it degrades silently to noise,
not a crash) -- exactly the failure mode a synthetic-array unit test can
never catch, since synthetic arrays don't have this kind of gap.

**Fix.** `paired_daily_returns` (`app/metrics/beta.py`) builds a
date -> close map per series and computes both series' returns only over
their **shared, sorted dates** -- so a null in one series can no longer
shift which day the other series' return is compared against.
`compute_beta` itself needed no change; the bug was entirely upstream of
it. `performance-chart.tsx`'s symbol-vs-benchmark chart had the identical
positional-zip bug (same two independently-fetched bar arrays) and got the
same date-keyed fix (`lib/technical.ts`'s `alignByDate`).

**Verified on real data, not just synthetic arrays.** Real 1-year TCS/
`^NSEI` bars (`tests/fixtures/beta/`) reproduce the exact null-close
condition; a regression test pins the old code's result on this fixture
(beta ≈ 0.07) against the fixed code's result (≈ 0.79) to prove the fix
isn't a no-op on real data.

**Cross-check against Yahoo's own reported beta (`defaultKeyStatistics.beta`):**

| Symbol | Ours (fixed) | Yahoo's own |
|---|---|---|
| TCS | 0.79 | 0.17 |
| HDFCBANK | 1.26 | 0.40 |
| TMPV | 1.45 | 0.78 |
| ICICIBANK | 0.92 | 0.26 |
| RELIANCE | 0.92 | 0.15 |

Yahoo's own figures are *also* implausibly low for every symbol checked --
consistent with this app's existing design note that "Yahoo doesn't
reliably expose beta for NSE tickers" (most likely computed against a
different/global benchmark, not `^NSEI`, for non-US listings). This is why
beta is computed here rather than fetched; Yahoo's figure isn't a
trustworthy cross-check target for this specific field the way
`returnOnEquity`/`bookValue`/`trailingEps` are.

## TMPV / JIOFIN / HDFCBANK: non-comparable history

Handled structurally via `backend/data/corporate_actions.json`, not
documented here -- see that file and PLAN.md "Phase 1 review" item 5 /
"Phase 1.5 review" item 2 for the demerger/listing/merger details.

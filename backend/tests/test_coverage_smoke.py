"""Phase 1 acceptance: hit every NIFTY 50 symbol for a quote and >=4 years of
annual financials, and write a coverage report of what's missing per company.

Network-dependent and slow (~50 symbols x ~7 Yahoo calls each), so it's
excluded from the default test run (see pytest.ini's `addopts`):

    pytest -m smoke -s
"""

from __future__ import annotations

import asyncio

import pytest

from app.config import BASE_DIR
from app.metrics.plausibility import (
    book_value_per_share_is_plausible,
    multiple_is_plausible,
    market_cap_matches_price_times_shares,
    pe_is_plausible,
)
from app.services import yahoo
from app.services.balance_sheet import compute_balance_sheet_detail
from app.services.corporate_actions import notes_for_symbol
from app.services.metrics_engine import compute_symbol_metrics
from app.services.normalize import (
    BALANCE_SHEET_MAP,
    CASH_FLOW_MAP,
    INCOME_STATEMENT_MAP,
    missing_fields,
    normalize_balance_sheet,
    normalize_cash_flow,
    normalize_income_statement,
)
from app.services.universe import all_symbols, get_company, load_universe

REPORT_PATH = BASE_DIR.parent / "data_coverage_report.md"

# Fields Phase 2's ratio engine needs per template (PLAN.md §2). Checked
# against the *annual* income statement; a field missing here means the
# corresponding ratio can't be computed from this free data source at all
# (not just "this company happens to lack a recent value").
TEMPLATE_REQUIRED_FIELDS: dict[str, list[str]] = {
    "bank": ["interest_income", "interest_expense", "net_interest_income"],
    "nbfc": ["interest_income", "interest_expense", "net_interest_income"],
    "insurance": ["premiums_earned", "interest_income"],
    "exchange": ["revenue", "ebitda"],
    "general": ["revenue", "ebitda", "cogs"],
}


async def _check_symbol(symbol: str) -> dict:
    company = get_company(symbol)
    result: dict = {"symbol": symbol, "yf_ticker": company.yf_ticker, "template": company.template}

    try:
        fast_info = await yahoo.fetch_fast_info(company.yf_ticker)
        result["quote_ok"] = fast_info.get("last_price") is not None
        result["quote_warning"] = None if result["quote_ok"] else "No last_price returned"
        result["last_price"] = fast_info.get("last_price")
    except Exception as exc:  # noqa: BLE001
        result["quote_ok"] = False
        result["quote_warning"] = str(exc)
        result["last_price"] = None

    market_cap, method, divergence_pct = await yahoo.fetch_market_cap_detailed(
        company.yf_ticker, result["last_price"]
    )
    result["market_cap"] = market_cap
    result["market_cap_method"] = method
    result["market_cap_divergence_pct"] = divergence_pct

    async def _annual_and_quarterly(fetch_fn):
        try:
            annual = await fetch_fn(company.yf_ticker, quarterly=False)
        except Exception:  # noqa: BLE001
            annual = []
        try:
            quarterly = await fetch_fn(company.yf_ticker, quarterly=True)
        except Exception:  # noqa: BLE001
            quarterly = []
        return annual, quarterly

    income_annual_raw, income_quarterly_raw = await _annual_and_quarterly(
        yahoo.fetch_income_stmt
    )
    balance_raw, _ = await _annual_and_quarterly(yahoo.fetch_balance_sheet)
    cashflow_raw, _ = await _annual_and_quarterly(yahoo.fetch_cashflow)

    income = normalize_income_statement(income_annual_raw)
    income_q = normalize_income_statement(income_quarterly_raw)
    balance = normalize_balance_sheet(balance_raw)
    cashflow = normalize_cash_flow(cashflow_raw)

    result["annual_periods"] = len(income)
    result["quarterly_periods"] = len(income_q)
    result["has_4yr_history"] = len(income) >= 4
    result["missing_income"] = sorted(missing_fields(income, INCOME_STATEMENT_MAP))
    result["missing_balance"] = sorted(missing_fields(balance, BALANCE_SHEET_MAP))
    result["missing_cashflow"] = sorted(missing_fields(cashflow, CASH_FLOW_MAP))

    # Phase 4 Task A.2: the buckets THIS APP COMPUTES (rather than passing
    # through a single already-signed reported line item) should never be
    # negative -- "Investments" (resolved from overlapping parent/sub
    # keys) and the residual "Other" (total minus every mapped bucket) are
    # both supposed to represent a real, non-negative amount of assets or
    # liabilities+equity; a negative value there means a mapped sub-item
    # double-counted past its own total (RELIANCE's/ICICIBANK's investments
    # overlap was exactly this -- see app.services.balance_sheet). This is
    # the across-all-50-symbols regression guard for that class of bug.
    # Every OTHER bucket here (Equity, Minority interest, "Other current",
    # "Other non-current", etc.) is a direct pass-through of one Yahoo
    # field and can be legitimately negative in real filings (e.g.
    # INDIGO's reported negative equity, or a small reported contra-liability
    # under "OtherNonCurrentLiabilities") -- not checked here.
    # A materiality floor, not a hard zero: "Other" reconciles by
    # construction (sum of a side's buckets always equals its reported
    # total), so a *tiny* negative Other reflects ordinary free-data-source
    # noise in the OTHER mapped buckets (e.g. BAJAJ-AUTO: "Other current
    # liabilities" overlapping ~0.66% into "Payables"), not the same class
    # of bug as a large one (e.g. the pre-fix ICICIBANK case, ~12-18% of
    # total assets) -- flag only the latter.
    _COMPUTED_BUCKETS = {"Investments", "Other"}
    _MATERIALITY_PCT = 1.0
    negative_buckets: list[str] = []
    for period in compute_balance_sheet_detail(balance, company.template):
        for side_name, side in (("assets", period["assets"]), ("liabilities_equity", period["liabilities_equity"])):
            side_total = sum(v for v in side.values() if v is not None)
            for bucket_name, value in side.items():
                if bucket_name not in _COMPUTED_BUCKETS or value is None or value >= 0:
                    continue
                if side_total and abs(value) / abs(side_total) * 100 > _MATERIALITY_PCT:
                    negative_buckets.append(f"{period['fiscal_year']} {side_name}.{bucket_name}={value}")
    result["negative_balance_sheet_buckets"] = negative_buckets

    required = TEMPLATE_REQUIRED_FIELDS.get(company.template, [])
    missing_required = [f for f in required if f in result["missing_income"]]
    result["template_inputs_ok"] = not missing_required
    result["template_inputs_missing"] = missing_required

    period_ends = [p["period_end"] for p in income]
    result["corporate_action_notes"] = notes_for_symbol(symbol, period_ends)

    # Phase 2.1 item 4: cross-check our own book-value-per-share and EPS
    # against Yahoo's own key statistics across all 50 symbols, to catch
    # the whole class of bug the HDFCBANK case revealed, not just HDFCBANK.
    try:
        metrics_result = await compute_symbol_metrics(symbol)
        result["cross_check_divergences"] = metrics_result["cross_check_divergences"]
    except Exception as exc:  # noqa: BLE001
        metrics_result = None
        result["cross_check_divergences"] = []
        result["cross_check_error"] = str(exc)

    # Phase 2.2 item 4: unit-scale plausibility checks across all 50
    # symbols -- catches a *future* crore/share-count/per-share mixing
    # mistake even where there's no live cross-check to compare against
    # (see app.metrics.plausibility's docstring). Checked against the
    # DISPLAYED values (post method-fallback), not raw intermediate ones --
    # INFY's own raw EPS is known unit-inconsistent (docs/data-notes.md),
    # but its *displayed* P/E already correctly falls back to Yahoo's
    # figure, so that's what should be judged plausible or not.
    plausibility_failures: list[str] = []
    if metrics_result is not None:
        quote = metrics_result["quote"]
        latest_balance = metrics_result["latest_balance"]
        pb = metrics_result["metrics"].get("pb")
        pe = metrics_result["metrics"].get("pe")

        displayed_bvps = quote.last_price / pb if pb not in (None, 0) and quote.last_price else None
        if not book_value_per_share_is_plausible(displayed_bvps):
            plausibility_failures.append(f"book_value_per_share={displayed_bvps} (from displayed pb={pb})")

        if not market_cap_matches_price_times_shares(
            quote.market_cap, quote.last_price, latest_balance.get("shares_outstanding")
        ):
            plausibility_failures.append(
                f"market_cap={quote.market_cap} vs price*shares implied"
            )

        if not pe_is_plausible(pe):
            plausibility_failures.append(f"pe={pe}")

        # Phase 4 Task A.1: the final-value check on every valuation
        # multiple, not just P/E -- catches a scale error on EITHER side of
        # the ratio (e.g. INFY: income statement AND book value per share
        # each individually ~80-100x too small, blowing up P/B/EV/EBITDA).
        for multiple_key in ("pe", "pb", "ev_ebitda", "ev_sales", "dividend_yield"):
            multiple_value = metrics_result["metrics"].get(multiple_key)
            if not multiple_is_plausible(multiple_key, multiple_value):
                plausibility_failures.append(f"{multiple_key}={multiple_value}")

    result["plausibility_failures"] = plausibility_failures

    # Phase 2.3 item 1: equity-basis-oscillation detector, across all 50
    # symbols -- reported here rather than just spot-checked on HDFCBANK, so
    # a future symbol tripping the same free-data-source quirk is caught
    # the same way HDFCBANK was.
    result["data_quality_flags"] = (
        dict(metrics_result["data_quality"]) if metrics_result is not None else {}
    )

    return result


def _render_report(results: list[dict]) -> str:
    total = len(results)
    quote_ok = sum(1 for r in results if r["quote_ok"])
    four_yr_ok = sum(1 for r in results if r["has_4yr_history"])
    market_cap_ok = sum(1 for r in results if r["market_cap"] is not None)
    template_ok = sum(1 for r in results if r["template_inputs_ok"])

    lines = [
        "# NIFTY 50 Data Coverage Report",
        "",
        f"Generated by `tests/test_coverage_smoke.py` against {total} symbols.",
        "",
        "## Summary",
        "",
        f"- Quotes returned a live last price: **{quote_ok}/{total}**",
        f"- Market cap resolved (price x shares, or quoteSummary fallback): **{market_cap_ok}/{total}**",
        f"- >=4 years of annual financials: **{four_yr_ok}/{total}**",
        f"- Template-required inputs present (see below): **{template_ok}/{total}**",
        "",
        "## Data availability by symbol",
        "",
        "| Symbol | Template | Quote | Annual yrs | Missing (Income) | Missing (Balance) | Missing (Cash flow) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: x["symbol"]):
        quote_cell = "OK" if r["quote_ok"] else f"MISSING ({r.get('quote_warning', '')})"
        lines.append(
            "| {symbol} | {template} | {quote} | {yrs} | {mi} | {mb} | {mc} |".format(
                symbol=r["symbol"],
                template=r["template"],
                quote=quote_cell,
                yrs=r["annual_periods"],
                mi=", ".join(r["missing_income"]) or "—",
                mb=", ".join(r["missing_balance"]) or "—",
                mc=", ".join(r["missing_cashflow"]) or "—",
            )
        )

    lines += [
        "",
        "## History depth per symbol",
        "",
        "Yahoo typically returns ~4 annual periods and ~5-6 quarters -- not",
        "the 5-10 years a paid feed would give. Phase 2's metrics engine",
        "should default to 3-year CAGR (not 5-year), a valuation band \"over",
        "available history\" (not a fixed 5y band), and trailing multiples",
        "from the last 4 quarters.",
        "",
        "| Symbol | Annual periods | Quarterly periods |",
        "|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: x["symbol"]):
        lines.append(f"| {r['symbol']} | {r['annual_periods']} | {r['quarterly_periods']} |")

    lines += [
        "",
        "## Template-specific inputs",
        "",
        "Fields Phase 2's ratio engine needs per business-model template",
        "(PLAN.md §2), checked against the annual income statement.",
        "",
        "| Symbol | Template | Required fields | Status |",
        "|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: x["symbol"]):
        required = TEMPLATE_REQUIRED_FIELDS.get(r["template"], [])
        status = "OK" if r["template_inputs_ok"] else f"MISSING: {', '.join(r['template_inputs_missing'])}"
        lines.append(
            f"| {r['symbol']} | {r['template']} | {', '.join(required) or '—'} | {status} |"
        )

    lines += [
        "",
        "## Market-cap method",
        "",
        "`price_x_shares` = last price x shares outstanding (from",
        "fundamentals-timeseries, no crumb needed) -- the primary, reliable",
        "path. `quote_summary_fallback` = only the crumb-gated quoteSummary",
        "endpoint returned a value. `unavailable` = neither worked.",
        "",
        "| Symbol | Method | Market cap (₹ Cr) |",
        "|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: x["symbol"]):
        cap = f"{r['market_cap'] / 1e7:,.0f}" if r["market_cap"] is not None else "—"
        lines.append(f"| {r['symbol']} | {r['market_cap_method']} | {cap} |")

    divergent_rows = [
        r for r in results if (r["market_cap_divergence_pct"] or 0) > 5
    ]
    lines += [
        "",
        "## Market-cap cross-check divergences (>5%)",
        "",
        "Phase 1.5 review item 5: symbols where price x shares outstanding",
        "disagrees with Yahoo's own quoteSummary market cap by more than 5%",
        "-- worth investigating (stale share count, a just-happened",
        "split/bonus not yet reflected, or a quoteSummary anomaly).",
        "",
    ]
    if divergent_rows:
        lines += ["| Symbol | Divergence |", "|---|---|"]
        for r in sorted(divergent_rows, key=lambda x: -x["market_cap_divergence_pct"]):
            lines.append(f"| {r['symbol']} | {r['market_cap_divergence_pct']:.1f}% |")
    else:
        lines.append("None -- every symbol with both figures available agrees within 5%.")

    action_rows = [r for r in results if r["corporate_action_notes"]]
    if action_rows:
        lines += [
            "",
            "## Corporate-action notes",
            "",
        ]
        for r in sorted(action_rows, key=lambda x: x["symbol"]):
            for note in r["corporate_action_notes"]:
                lines.append(f"- **{r['symbol']}**: {note}")

    lines += [
        "",
        "## Book value / EPS cross-check (Phase 2.1 item 4)",
        "",
        "Our fundamentals-timeseries-derived book value per share and EPS,",
        "compared against Yahoo's own key-statistics figures (bookValue,",
        "trailingEps), across all 50 symbols -- catches the whole class of",
        "bug HDFCBANK revealed (our figure diverging from a more-current",
        "or correctly-scoped source), not just that one company.",
        "",
        "IMPORTANT (updated Phase 2.2): `pb`/`pe`/`roe`/`roa` always prefer",
        "OUR OWN calculation now, never Yahoo's, as long as ours succeeded --",
        "see backend/docs/data-notes.md. A row here means EITHER our own",
        "figure is the one actually shown and it genuinely differs from",
        "Yahoo's (HDFCBANK's ROE/book-value rows are exactly this, by",
        "design -- see data-notes.md for why), OR our own calculation was",
        "unavailable and Yahoo's crumb-gated figure filled in as a tagged",
        "fallback (check the `method` field on the ratio in question).",
        "",
    ]
    divergence_rows = [
        (r["symbol"], d)
        for r in results
        for d in r.get("cross_check_divergences", [])
    ]
    if divergence_rows:
        lines += ["| Symbol | Metric | Ours | Yahoo | Divergence |", "|---|---|---|---|---|"]
        for symbol, d in sorted(divergence_rows, key=lambda x: -x[1]["divergence_pct"]):
            lines.append(
                f"| {symbol} | {d['metric']} | {d['ours']:.2f} | {d['yahoo']:.2f} | {d['divergence_pct']:.1f}% |"
            )
    else:
        lines.append("None -- every symbol with both figures available agrees within 10%.")

    lines += [
        "",
        "## Unit-scale plausibility check (Phase 2.2 item 4)",
        "",
        "Sanity bands on book value/share, market-cap-vs-price-times-shares,",
        "and EPS-vs-price -- catches a *future* crore/share-count/per-share",
        "unit mistake (the class of bug that produced the Phase 2.1 book-value",
        "and Phase 1.5 market-cap regressions) even in a symbol with no live",
        "cross-check to compare against.",
        "",
    ]
    failing_symbols = [r for r in results if r.get("plausibility_failures")]
    if failing_symbols:
        lines += ["| Symbol | Failure |", "|---|---|"]
        for r in sorted(failing_symbols, key=lambda x: x["symbol"]):
            for failure in r["plausibility_failures"]:
                lines.append(f"| {r['symbol']} | {failure} |")
    else:
        lines.append("None -- all 50 symbols pass every plausibility check.")

    lines += [
        "",
        "## Equity-basis oscillation check (Phase 2.3 item 1)",
        "",
        "Symbols whose quarterly equity alternates between two reporting",
        "bases (see `app.metrics.basis_consistency` and",
        "backend/docs/data-notes.md) -- their ROE/ROA are computed from",
        "annual, same-basis figures and carry `data_quality: \"inconsistent\"`",
        "on `/api/ratios` (an amber badge in the UI) rather than being shown",
        "as a clean number.",
        "",
    ]
    quality_rows = [(r["symbol"], r["data_quality_flags"]) for r in results if r.get("data_quality_flags")]
    if quality_rows:
        lines += ["| Symbol | Metric | Reason |", "|---|---|---|"]
        for symbol, flags in sorted(quality_rows, key=lambda x: x[0]):
            for metric, reason in sorted(flags.items()):
                lines.append(f"| {symbol} | {metric} | {reason} |")
    else:
        lines.append("None -- no symbol's equity shows a basis-oscillation pattern.")

    lines.append("")
    return "\n".join(lines)


@pytest.mark.smoke
def test_universe_has_50_companies_across_14_sectors():
    sectors = load_universe()
    assert len(sectors) == 14
    assert sum(len(s.companies) for s in sectors) == 50


@pytest.mark.smoke
def test_coverage_report_all_symbols():
    symbols = all_symbols()
    assert len(symbols) == 50

    async def _run():
        return await asyncio.gather(*(_check_symbol(s) for s in symbols))

    results = asyncio.run(_run())

    REPORT_PATH.write_text(_render_report(results), encoding="utf-8")

    no_quote_no_warning = [
        r["symbol"] for r in results if not r["quote_ok"] and not r.get("quote_warning")
    ]
    assert not no_quote_no_warning, (
        f"Symbols with no quote and no documented warning: {no_quote_no_warning}"
    )

    no_market_cap = [r["symbol"] for r in results if r["market_cap"] is None]
    assert not no_market_cap, f"Symbols with no market cap by any method: {no_market_cap}"

    # Phase 2.2 gate: the plausibility check must pass for all 50 symbols.
    implausible = {r["symbol"]: r["plausibility_failures"] for r in results if r["plausibility_failures"]}
    assert not implausible, f"Symbols failing a plausibility check: {implausible}"

    # Phase 4 Task A.2 gate: no balance-sheet composition bucket may be
    # negative for any of the 50 symbols.
    negative_buckets = {
        r["symbol"]: r["negative_balance_sheet_buckets"] for r in results if r["negative_balance_sheet_buckets"]
    }
    assert not negative_buckets, f"Symbols with a negative balance-sheet bucket: {negative_buckets}"


@pytest.mark.smoke
def test_hdfcbank_kpi_roe_matches_own_computation_not_yahoos():
    """Phase 2.2 gate: HDFCBANK's KPI ROE must be OUR OWN computed figure
    (method='computed'), not a Yahoo fallback -- since Phase 4 will build an
    ROE-over-time chart from the same computation, and the two must always
    agree by construction (same function, same data), not by luck."""
    result = asyncio.run(compute_symbol_metrics("HDFCBANK"))
    assert result["method"]["roe"] == "computed"
    assert result["metrics"]["roe"] is not None


@pytest.mark.smoke
def test_hdfcbank_roe_is_badged_inconsistent_not_silently_wrong():
    """Phase 2.3 gate: HDFCBANK's ROE still doesn't reconcile with Screener
    within 1.5pp after the annual-basis fix (the annual filings themselves
    sit on the wrong basis, not just a numerator/denominator mismatch within
    our own calculation -- see backend/docs/data-notes.md). The gate's other
    branch applies instead: it must be tagged `data_quality: "inconsistent"`
    with a documented reason, not presented as a clean figure."""
    result = asyncio.run(compute_symbol_metrics("HDFCBANK"))
    assert "roe" in result["data_quality"]
    assert result["data_quality"]["roe"]  # non-empty reason string


@pytest.mark.smoke
def test_indigo_pat_growth_headline_is_real_when_previous_period_is_positive():
    """INDIGO's latest two comparable annual periods (FY25 positive ->
    FY26 negative) have a POSITIVE prior value, so the headline pat_growth
    is a real, meaningful (if steep) decline -- not everything touching a
    sign change is "n.m.", only a computation whose PRIOR value is
    non-positive is (PLAN.md "Phase 4.2 review"). The actual sign-crossing
    "n.m." case in INDIGO's history is FY23 (-Rs305.79 Cr) -> FY24
    (+Rs8,172.50 Cr); metrics_engine's headline only ever looks at the
    latest two periods so it can't reach that pair, but
    `test_ratios.py::test_yoy_growth_sign_crossing_negative_to_positive_is_none_not_meaningful`
    pins that exact real case down directly."""
    result = asyncio.run(compute_symbol_metrics("INDIGO"))
    assert result["metrics"]["pat_growth"] is not None
    assert result["metrics"]["pat_growth"] < 0
    assert "pat_growth" not in result["reasons"]


@pytest.mark.smoke
def test_equity_basis_oscillation_only_flags_symbols_with_real_evidence():
    """Guards against the detector becoming noisy over time: as of this
    run, only HDFCBANK's real quarterly equity shows the basis-switching
    signature (see data_coverage_report.md's "Equity-basis oscillation
    check" section for the full 50-symbol scan). A newly-flagged symbol
    here is worth investigating (a genuine new instance of the bug, or the
    detector's threshold needs revisiting), not silently accepted."""
    symbols = all_symbols()

    async def _run():
        return await asyncio.gather(*(compute_symbol_metrics(s) for s in symbols))

    results = asyncio.run(_run())
    flagged = {r["company"].symbol for r in results if r["data_quality"]}
    assert flagged == {"HDFCBANK"}

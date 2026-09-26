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
from app.services import yahoo
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
        result["cross_check_divergences"] = []
        result["cross_check_error"] = str(exc)

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
        "IMPORTANT: a row appearing here does NOT mean the displayed metric",
        "is wrong -- `pb`/`pe`/`roe`/`roa` always prefer Yahoo's figure over",
        "ours when both exist, so a row is either (a) the override doing",
        "its job (ours differs, Yahoo's more-authoritative figure is what's",
        "actually shown), or (b) neither side was overridden and our own",
        "TTM-summed EPS differs from Yahoo's `trailingEps` methodology",
        "(exceptional items, or -- confirmed for INFY -- a Yahoo data-scale",
        "inconsistency in ITS OWN quarterly figures, not our calculation).",
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

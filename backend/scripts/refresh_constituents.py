"""Refresh backend/data/nifty50.json from NSE's official constituent list.

NSE aggressively blocks non-browser / datacenter traffic (expect 403s from
CI or cloud sandboxes) -- this is meant to be run from an environment with
normal residential/office network access, ideally on a schedule (Phase 8).

Existing `template` and sector-grouping assignments are preserved for
symbols we already know about; brand-new symbols are added under a
"Uncategorised (needs review)" sector with template="general" and must be
hand-classified per PLAN.md §2 before shipping.

Usage:
    python scripts/refresh_constituents.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from curl_cffi import requests as cffi_requests

NSE_CONSTITUENTS_URL = "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv"
NIFTY50_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "nifty50.json"
REVIEW_SECTOR = "Uncategorised (needs review)"


def fetch_constituents_csv() -> str:
    session = cffi_requests.Session(impersonate="chrome")
    resp = session.get(NSE_CONSTITUENTS_URL, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        name = (row.get("Company Name") or "").strip()
        if symbol:
            rows.append({"symbol": symbol, "name": name})
    return rows


def merge_with_existing(new_rows: list[dict[str, str]], existing: dict) -> dict:
    known: dict[str, dict] = {
        company["symbol"]: {**company, "sector": sector["name"]}
        for sector in existing["sectors"]
        for company in sector["companies"]
    }

    sectors_by_name: dict[str, list[dict]] = {
        sector["name"]: [] for sector in existing["sectors"]
    }
    review_bucket: list[dict] = []

    new_symbols = {row["symbol"] for row in new_rows}
    removed = set(known) - new_symbols
    added = new_symbols - set(known)

    for row in new_rows:
        symbol = row["symbol"]
        if symbol in known:
            company = known[symbol]
            sectors_by_name[company["sector"]].append(
                {
                    "symbol": symbol,
                    "yf_ticker": company["yf_ticker"],
                    "name": row["name"] or company["name"],
                    "template": company["template"],
                }
            )
        else:
            review_bucket.append(
                {
                    "symbol": symbol,
                    "yf_ticker": f"{symbol}.NS",
                    "name": row["name"],
                    "template": "general",
                }
            )

    sectors = [
        {"name": name, "companies": companies}
        for name, companies in sectors_by_name.items()
        if companies
    ]
    if review_bucket:
        sectors.append({"name": REVIEW_SECTOR, "companies": review_bucket})

    if removed:
        print(f"Removed from index: {sorted(removed)}", file=sys.stderr)
    if added:
        print(
            f"New symbols added under '{REVIEW_SECTOR}' -- classify by hand: {sorted(added)}",
            file=sys.stderr,
        )

    return {
        "generated_at": existing.get("generated_at"),
        "source": NSE_CONSTITUENTS_URL,
        "sectors": sectors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = json.loads(NIFTY50_JSON_PATH.read_text(encoding="utf-8"))

    try:
        csv_text = fetch_constituents_csv()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch NSE constituent list: {exc}", file=sys.stderr)
        print(
            "NSE frequently blocks non-browser/datacenter IPs with 403; "
            "retry from a normal network connection.",
            file=sys.stderr,
        )
        sys.exit(1)

    rows = parse_csv(csv_text)
    if len(rows) != 50:
        print(f"Expected 50 constituents, got {len(rows)}. Aborting.", file=sys.stderr)
        sys.exit(1)

    updated = merge_with_existing(rows, existing)

    if args.dry_run:
        print(json.dumps(updated, indent=2, ensure_ascii=False))
        return

    from datetime import date

    updated["generated_at"] = date.today().isoformat()
    NIFTY50_JSON_PATH.write_text(
        json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {NIFTY50_JSON_PATH}")


if __name__ == "__main__":
    main()

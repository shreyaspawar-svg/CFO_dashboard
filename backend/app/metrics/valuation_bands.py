"""Historical P/E and P/B bands: daily price divided by a trailing EPS /
BVPS figure that only updates ("steps") on each quarterly report date --
never interpolated or backfilled, so a chart never implies knowledge the
market didn't have yet on a given day.

Pure functions -- no I/O.
"""

from __future__ import annotations

_TRAILING_QUARTERS = 4


def trailing_eps_series(quarterly_eps: list[dict]) -> list[dict]:
    """`quarterly_eps`: [{"period_end": str, "eps_diluted": float | None}],
    sorted ascending by period_end. Returns [{"period_end", "trailing_eps"}]
    -- a rolling sum of the last 4 quarters' diluted EPS, `None` until 4
    consecutive non-null quarters are available."""
    out: list[dict] = []
    window: list[float | None] = []
    for point in quarterly_eps:
        window.append(point.get("eps_diluted"))
        if len(window) > _TRAILING_QUARTERS:
            window.pop(0)
        trailing = (
            sum(window)  # type: ignore[arg-type]
            if len(window) == _TRAILING_QUARTERS and all(v is not None for v in window)
            else None
        )
        out.append({"period_end": point["period_end"], "trailing_eps": trailing})
    return out


def _step_lookup(checkpoints: list[tuple[str, float | None]], query_date: str) -> float | None:
    """The latest checkpoint value whose date is <= `query_date`, else
    None if `query_date` is before the first checkpoint. `checkpoints`
    must already be sorted ascending by date."""
    result: float | None = None
    for date, value in checkpoints:
        if date > query_date:
            break
        result = value
    return result


def compute_pe_pb_band(
    price_bars: list[dict],
    trailing_eps_points: list[dict],
    bvps_points: list[dict],
) -> list[dict]:
    """`price_bars`: [{"date", "close"}]. `trailing_eps_points`:
    [{"period_end", "trailing_eps"}]. `bvps_points`: [{"period_end",
    "bvps"}]. Returns one {"date", "pe", "pb"} per price bar, each ratio
    `None` whenever the price, the trailing EPS/BVPS as of that date, or
    the EPS/BVPS itself (loss-making or non-positive book value) doesn't
    support a meaningful ratio."""
    # Filter out null-valued points before sorting: a null checkpoint is a
    # reporting gap, not a value to step to, and mixing null/non-null
    # values at the same date (e.g. quarterly-trailing merged with an
    # annual fallback -- see valuation.py) breaks tuple sort ordering
    # (None isn't orderable against float).
    eps_checkpoints = sorted(
        (p["period_end"], p["trailing_eps"]) for p in trailing_eps_points if p["trailing_eps"] is not None
    )
    bvps_checkpoints = sorted((p["period_end"], p["bvps"]) for p in bvps_points if p["bvps"] is not None)

    out: list[dict] = []
    for bar in price_bars:
        date = bar["date"]
        price = bar.get("close")
        eps = _step_lookup(eps_checkpoints, date)
        bvps = _step_lookup(bvps_checkpoints, date)
        pe = price / eps if price is not None and eps is not None and eps > 0 else None
        pb = price / bvps if price is not None and bvps is not None and bvps > 0 else None
        out.append({"date": date, "pe": pe, "pb": pb})
    return out


def band_summary(band: list[dict], key: str) -> dict:
    """min/median/max/current over the non-null `key` values in `band`."""
    import statistics

    values = [point[key] for point in band if point.get(key) is not None]
    current = next((point[key] for point in reversed(band) if point.get(key) is not None), None)
    if not values:
        return {"min": None, "median": None, "max": None, "current": None}
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "current": current,
    }

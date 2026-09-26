from datetime import datetime, timezone

from app.services.market import market_status


def _ist_naive_as_utc(y, mo, d, h, mi):
    # IST = UTC+5:30; construct the equivalent UTC instant.
    from datetime import timedelta

    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime(y, mo, d, h, mi, tzinfo=ist).astimezone(timezone.utc)


def test_market_open_during_trading_hours_on_a_weekday():
    # Wed 2026-03-25, 10:00 IST
    assert market_status(_ist_naive_as_utc(2026, 3, 25, 10, 0)) == "open"


def test_market_pre_open_before_915_ist():
    assert market_status(_ist_naive_as_utc(2026, 3, 25, 9, 5)) == "pre_open"


def test_market_closed_after_hours():
    assert market_status(_ist_naive_as_utc(2026, 3, 25, 16, 0)) == "closed"


def test_market_closed_on_weekend():
    # 2026-03-28 is a Saturday
    assert market_status(_ist_naive_as_utc(2026, 3, 28, 10, 0)) == "closed"

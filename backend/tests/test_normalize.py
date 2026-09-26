from datetime import datetime

from app.services.normalize import (
    CRORE,
    INCOME_STATEMENT_MAP,
    _fiscal_year_label,
    clean_numeric,
    missing_fields,
    normalize_income_statement,
)


def test_fiscal_year_label_march_end():
    assert _fiscal_year_label(datetime(2024, 3, 31)) == "FY24"


def test_fiscal_year_label_calendar_year_end():
    # A period ending after March belongs to the FY that closes next March.
    assert _fiscal_year_label(datetime(2023, 12, 31)) == "FY24"


def test_clean_numeric_handles_nan_and_none():
    assert clean_numeric(None) is None
    assert clean_numeric(float("nan")) is None
    assert clean_numeric("123.5") == 123.5


def test_normalize_income_statement_converts_to_crore_but_not_eps():
    records = [
        {
            "index": "2024-03-31",
            "TotalRevenue": 10 * CRORE,
            "DilutedEPS": 42.5,
        }
    ]
    periods = normalize_income_statement(records)
    assert len(periods) == 1
    period = periods[0]
    assert period["fiscal_year"] == "FY24"
    assert period["line_items"]["revenue"] == 10.0
    assert period["line_items"]["eps_diluted"] == 42.5
    assert period["line_items"]["ebitda"] is None


def test_missing_fields_reports_fields_absent_in_every_period():
    periods = normalize_income_statement(
        [{"index": "2024-03-31", "TotalRevenue": 100.0}]
    )
    missing = missing_fields(periods, INCOME_STATEMENT_MAP)
    assert "revenue" not in missing
    assert "ebitda" in missing


def test_missing_fields_empty_periods_returns_everything_missing():
    missing = missing_fields([], INCOME_STATEMENT_MAP)
    assert missing == set(INCOME_STATEMENT_MAP.values())

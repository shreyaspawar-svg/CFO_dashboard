from app.metrics.comparability import comparable_periods
from app.services.corporate_actions import get_action, notes_for_symbol


def test_get_action_known_symbol():
    action = get_action("TMPV")
    assert action is not None
    assert action["cutoff_period_end"] == "2025-04-01"


def test_get_action_unknown_symbol_is_none():
    assert get_action("TCS") is None


def test_notes_for_symbol_no_action_is_empty():
    assert notes_for_symbol("TCS", ["2024-03-31"]) == []


def test_comparable_periods_tmpv_excludes_pre_demerger_years():
    periods = [
        {"fiscal_year": "FY23", "period_end": "2023-03-31"},
        {"fiscal_year": "FY24", "period_end": "2024-03-31"},
        {"fiscal_year": "FY25", "period_end": "2025-03-31"},
        {"fiscal_year": "FY26", "period_end": "2026-03-31"},
    ]
    kept, note = comparable_periods("TMPV", periods)
    assert [p["fiscal_year"] for p in kept] == ["FY26"]
    assert note is not None
    assert "FY23" in note and "FY24" in note and "FY25" in note


def test_comparable_periods_jiofin_excludes_shell_year():
    periods = [
        {"fiscal_year": "FY23", "period_end": "2023-03-31"},
        {"fiscal_year": "FY24", "period_end": "2024-03-31"},
    ]
    kept, note = comparable_periods("JIOFIN", periods)
    assert [p["fiscal_year"] for p in kept] == ["FY24"]
    assert note is not None


def test_comparable_periods_no_action_returns_all_unfiltered():
    periods = [{"fiscal_year": "FY24", "period_end": "2024-03-31"}]
    kept, note = comparable_periods("TCS", periods)
    assert kept == periods
    assert note is None


def test_comparable_periods_eternal_null_cutoff_never_excludes():
    """ETERNAL's action has cutoff_period_end=null (informational-only) --
    comparable_periods must not exclude anything for it."""
    periods = [
        {"fiscal_year": "FY22", "period_end": "2022-03-31"},
        {"fiscal_year": "FY23", "period_end": "2023-03-31"},
    ]
    kept, note = comparable_periods("ETERNAL", periods)
    assert kept == periods
    assert note is None

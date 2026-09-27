import pytest

from app.metrics.dcf import dcf_intrinsic_value, dcf_sensitivity_table, reverse_dcf_implied_growth


def test_dcf_intrinsic_value_basic():
    result = dcf_intrinsic_value(
        base_fcff=1000,
        growth_rate_pct=10,
        wacc_pct=12,
        terminal_growth_pct=4,
        net_debt=500,
        shares_outstanding=100,
        forecast_years=5,
    )
    assert result["enterprise_value"] is not None
    assert result["enterprise_value"] > 0
    assert result["equity_value"] == pytest.approx(result["enterprise_value"] - 500)
    assert result["intrinsic_value_per_share"] == pytest.approx(result["equity_value"] / 100)


def test_dcf_higher_growth_gives_higher_value():
    low_growth = dcf_intrinsic_value(1000, 5, 12, 4, 500, 100)
    high_growth = dcf_intrinsic_value(1000, 15, 12, 4, 500, 100)
    assert high_growth["enterprise_value"] > low_growth["enterprise_value"]


def test_dcf_wacc_must_exceed_terminal_growth():
    result = dcf_intrinsic_value(1000, 10, 4, 4, 500, 100)
    assert result["enterprise_value"] is None
    result2 = dcf_intrinsic_value(1000, 10, 3, 4, 500, 100)
    assert result2["enterprise_value"] is None


def test_dcf_missing_input_returns_all_none():
    result = dcf_intrinsic_value(None, 10, 12, 4, 500, 100)
    assert result == {
        "enterprise_value": None,
        "equity_value": None,
        "intrinsic_value_per_share": None,
    }


def test_dcf_zero_shares_outstanding_leaves_per_share_none_but_ev_set():
    result = dcf_intrinsic_value(1000, 10, 12, 4, 500, 0)
    assert result["enterprise_value"] is not None
    assert result["intrinsic_value_per_share"] is None


def test_dcf_no_net_debt_defaults_to_zero():
    result = dcf_intrinsic_value(1000, 10, 12, 4, None, 100)
    assert result["equity_value"] == pytest.approx(result["enterprise_value"])


def test_reverse_dcf_recovers_the_forward_growth_rate():
    forward = dcf_intrinsic_value(
        base_fcff=1000,
        growth_rate_pct=8,
        wacc_pct=12,
        terminal_growth_pct=4,
        net_debt=500,
        shares_outstanding=100,
    )
    price = forward["intrinsic_value_per_share"]

    implied_growth = reverse_dcf_implied_growth(
        base_fcff=1000,
        current_price=price,
        wacc_pct=12,
        terminal_growth_pct=4,
        net_debt=500,
        shares_outstanding=100,
    )
    assert implied_growth == pytest.approx(8.0, abs=0.05)


def test_reverse_dcf_invalid_wacc_terminal_relationship_is_none():
    assert (
        reverse_dcf_implied_growth(1000, 50, 4, 4, 500, 100) is None
    )


def test_reverse_dcf_missing_inputs_is_none():
    assert reverse_dcf_implied_growth(None, 50, 12, 4, 500, 100) is None
    assert reverse_dcf_implied_growth(1000, 50, 12, 4, 500, None) is None
    assert reverse_dcf_implied_growth(1000, 50, 12, 4, 500, 0) is None


def test_sensitivity_table_is_monotonic_in_wacc_and_terminal_growth():
    table = dcf_sensitivity_table(
        base_fcff=1000,
        growth_rate_pct=10,
        wacc_values_pct=[10, 12, 14],
        terminal_growth_values_pct=[2, 4, 6],
        net_debt=500,
        shares_outstanding=100,
    )
    values = table["values"]
    # Fixed terminal growth (each column): value strictly falls as WACC rises.
    for col in range(3):
        column = [values[row][col] for row in range(3)]
        assert column == sorted(column, reverse=True)
    # Fixed WACC (each row): value strictly rises as terminal growth rises.
    for row in range(3):
        assert values[row] == sorted(values[row])


def test_reverse_dcf_inverts_forward_dcf_within_0_1_percent():
    forward = dcf_intrinsic_value(1000, 8, 12, 4, 500, 100)
    price = forward["intrinsic_value_per_share"]
    implied_growth = reverse_dcf_implied_growth(1000, price, 12, 4, 500, 100)
    assert abs(implied_growth - 8.0) / 8.0 < 0.001


def test_sensitivity_table_invalid_wacc_terminal_pair_is_none_not_crash():
    table = dcf_sensitivity_table(1000, 10, [4], [4, 6], 500, 100)
    assert table["values"] == [[None, None]]

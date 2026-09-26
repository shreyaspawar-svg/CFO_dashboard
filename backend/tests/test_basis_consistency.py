from app.metrics.basis_consistency import equity_basis_oscillation_detected


def test_hdfcbank_like_oscillation_is_detected():
    # Dec-24 -> Mar-25 -> Jun-25 -> Sep-25 -> Mar-26, from docs/data-notes.md
    equity = [502_000.0, 768_000.0, 543_000.0, 790_000.0, 817_000.0]
    assert equity_basis_oscillation_detected(equity) is True


def test_organic_growth_is_not_flagged():
    equity = [100_000.0, 106_000.0, 111_000.0, 118_000.0, 124_000.0]
    assert equity_basis_oscillation_detected(equity) is False


def test_a_single_large_one_off_jump_is_not_flagged():
    # A real capital raise (e.g. ADANIENT's +60.8%) is one-directional, not
    # a swing that reverses -- shouldn't be confused with a basis switch.
    equity = [100_000.0, 160_800.0, 168_000.0, 175_000.0]
    assert equity_basis_oscillation_detected(equity) is False


def test_small_noise_around_threshold_is_not_flagged():
    equity = [100_000.0, 111_000.0, 100_000.0, 111_000.0]  # +/-11%, under threshold
    assert equity_basis_oscillation_detected(equity) is False


def test_fewer_than_three_quarters_cannot_be_evaluated():
    assert equity_basis_oscillation_detected([100_000.0, 150_000.0]) is False
    assert equity_basis_oscillation_detected([100_000.0]) is False
    assert equity_basis_oscillation_detected([]) is False


def test_none_values_are_skipped_not_treated_as_zero():
    equity = [502_000.0, None, 768_000.0, 543_000.0, 790_000.0]
    assert equity_basis_oscillation_detected(equity) is True

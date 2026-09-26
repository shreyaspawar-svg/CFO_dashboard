from app.metrics.units import Crore, Shares, crore_to_rupees, per_share_value, rupees_to_crore


def test_crore_to_rupees():
    assert crore_to_rupees(Crore(1.0)) == 10_000_000


def test_rupees_to_crore_round_trips():
    assert rupees_to_crore(crore_to_rupees(Crore(107240.0))) == 107240.0


def test_per_share_value_matches_the_phase_2_1_regression_case():
    # HDFCBANK FY26: 816,739.56 Cr equity, ~15.39B shares -> ~530/share,
    # not the ~5.3e-5 the original crore-vs-raw-count bug produced.
    value = per_share_value(Crore(816739.56), Shares(15_393_260_762.0))
    assert value is not None
    assert 500 < value < 600


def test_per_share_value_zero_shares_is_none_not_a_crash():
    assert per_share_value(Crore(1000.0), Shares(0.0)) is None

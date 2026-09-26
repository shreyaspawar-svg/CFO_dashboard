from app.metrics.signals import strengths_and_watchouts


def _hist(*values: float | None) -> list[dict]:
    years = ["FY23", "FY24", "FY25", "FY26"]
    return [{"fiscal_year": y, "value": v} for y, v in zip(years, values)]


# --------------------------------------------------------------------------
# General template
# --------------------------------------------------------------------------


def test_roce_top_quartile_is_a_strength():
    metrics = {"roce": 56.5}
    peer_values = {"roce": [10, 20, 28, 30, 56.5]}
    signals = strengths_and_watchouts(metrics, {}, peer_values, "general")
    hit = next(s for s in signals if s["rule"] == "roce_top_quartile")
    assert hit["type"] == "strength"
    assert "56.5%" in hit["message"]


def test_tcs_shaped_de_rise_is_not_flagged_below_materiality_floor():
    # Real TCS history: 0.085x -> 0.089x -> 0.099x -> 0.105x -- strictly
    # rising but both the level and the total move are immaterial.
    history = {"debt_to_equity": _hist(0.085, 0.089, 0.099, 0.105)}
    signals = strengths_and_watchouts({}, history, {}, "general")
    assert not any(s["rule"] == "debt_to_equity_rising" for s in signals)


def test_debt_to_equity_rising_above_level_floor_is_a_watch():
    history = {"debt_to_equity": _hist(0.6, 0.65, 0.7, 0.75)}
    signals = strengths_and_watchouts({}, history, {}, "general")
    hit = next(s for s in signals if s["rule"] == "debt_to_equity_rising")
    assert hit["type"] == "watch"
    assert "0.60x" in hit["message"] and "0.75x" in hit["message"]


def test_debt_to_equity_rising_above_change_floor_is_a_watch_even_at_low_level():
    history = {"debt_to_equity": _hist(0.1, 0.15, 0.25, 0.4)}  # +0.3, level still < 0.5
    signals = strengths_and_watchouts({}, history, {}, "general")
    assert any(s["rule"] == "debt_to_equity_rising" for s in signals)


def test_margin_expanding_needs_at_least_2pp():
    history = {"ebitda_margin": _hist(20.0, 20.5, 20.9, 21.5)}  # +1.5pp total
    signals = strengths_and_watchouts({}, history, {}, "general")
    assert not any(s["rule"] == "margin_expanding" for s in signals)


def test_margin_expanding_at_2pp_or_more_is_a_strength():
    history = {"ebitda_margin": _hist(20.0, 21.0, 22.0, 23.0)}
    signals = strengths_and_watchouts({}, history, {}, "general")
    hit = next(s for s in signals if s["rule"] == "margin_expanding")
    assert hit["type"] == "strength"


def test_cfo_to_pat_weak_only_when_pat_is_positive():
    history = {
        "cfo_to_pat": _hist(1.1, 1.0, 0.6, 0.5),
        "net_income": _hist(100, 100, -50, 100),  # a loss in the first flagged year
    }
    signals = strengths_and_watchouts({}, history, {}, "general")
    assert not any(s["rule"] == "cfo_to_pat_weak" for s in signals)


def test_cfo_to_pat_weak_with_positive_pat_is_a_watch():
    history = {
        "cfo_to_pat": _hist(1.1, 1.0, 0.6, 0.5),
        "net_income": _hist(100, 100, 80, 90),
    }
    signals = strengths_and_watchouts({}, history, {}, "general")
    assert any(s["rule"] == "cfo_to_pat_weak" for s in signals)


def test_interest_coverage_thin_only_when_debt_is_material():
    metrics = {"interest_coverage": 1.5, "debt_to_assets": 0.02}  # 2% of assets
    signals = strengths_and_watchouts(metrics, {}, {}, "general")
    assert not any(s["rule"] == "interest_coverage_thin" for s in signals)


def test_interest_coverage_thin_with_material_debt_is_a_watch():
    metrics = {"interest_coverage": 1.5, "debt_to_assets": 0.3}
    signals = strengths_and_watchouts(metrics, {}, {}, "general")
    hit = next(s for s in signals if s["rule"] == "interest_coverage_thin")
    assert hit["type"] == "watch"


def test_capped_at_four_per_type():
    metrics = {"roce": 90.0, "interest_coverage": 0.5, "debt_to_assets": 0.5}
    history = {
        "debt_to_equity": _hist(0.6, 0.7, 0.8, 0.9),
        "cfo_to_pat": _hist(0.1, 0.1, 0.1, 0.1),
        "net_income": _hist(10, 10, 10, 10),
        "ebitda_margin": _hist(10.0, 15.0, 20.0, 25.0),
    }
    peer_values = {"roce": [10, 20, 90.0]}
    signals = strengths_and_watchouts(metrics, history, peer_values, "general")
    assert len([s for s in signals if s["type"] == "strength"]) <= 4
    assert len([s for s in signals if s["type"] == "watch"]) <= 4


def test_no_data_produces_no_signals():
    assert strengths_and_watchouts({}, {}, {}, "general") == []


# --------------------------------------------------------------------------
# Bank / NBFC template
# --------------------------------------------------------------------------


def test_general_rules_do_not_fire_for_bank_template():
    metrics = {"roce": 90.0, "interest_coverage": 0.1, "debt_to_assets": 0.9}
    history = {"debt_to_equity": _hist(0.6, 0.7, 0.8, 0.9), "ebitda_margin": _hist(10.0, 15.0, 20.0, 25.0)}
    signals = strengths_and_watchouts(metrics, history, {}, "bank")
    assert signals == []


def test_nim_improvement_above_floor_is_a_strength():
    history = {"nim": _hist(None, None, 2.7, 3.0)}
    signals = strengths_and_watchouts({}, history, {}, "bank")
    hit = next(s for s in signals if s["rule"] == "nim_change")
    assert hit["type"] == "strength"


def test_nim_change_below_floor_is_not_flagged():
    history = {"nim": _hist(None, None, 2.9, 3.0)}
    signals = strengths_and_watchouts({}, history, {}, "bank")
    assert not any(s["rule"] == "nim_change" for s in signals)


def test_cost_to_income_rise_above_floor_is_a_watch():
    history = {"cost_to_income": _hist(None, None, 40.0, 45.0)}
    signals = strengths_and_watchouts({}, history, {}, "nbfc")
    hit = next(s for s in signals if s["rule"] == "cost_to_income_change")
    assert hit["type"] == "watch"


def test_roa_top_quartile_is_a_strength():
    metrics = {"roa": 2.5}
    peer_values = {"roa": [1.0, 1.2, 1.5, 2.5]}
    signals = strengths_and_watchouts(metrics, {}, peer_values, "bank")
    hit = next(s for s in signals if s["rule"] == "roa_top_quartile")
    assert hit["type"] == "strength"


def test_roa_below_1pct_is_a_watch():
    metrics = {"roa": 0.5}
    signals = strengths_and_watchouts(metrics, {}, {}, "bank")
    hit = next(s for s in signals if s["rule"] == "roa_weak")
    assert hit["type"] == "watch"


def test_pat_lags_nii_for_two_years_is_a_watch():
    history = {
        "nii_growth": _hist(None, None, 10.0, 12.0),
        "pat_growth": _hist(None, None, -5.0, -2.0),
    }
    signals = strengths_and_watchouts({}, history, {}, "bank")
    hit = next(s for s in signals if s["rule"] == "pat_lags_nii")
    assert hit["type"] == "watch"


def test_pat_lags_nii_only_one_year_is_not_flagged():
    history = {
        "nii_growth": _hist(None, None, 10.0, 12.0),
        "pat_growth": _hist(None, None, 5.0, -2.0),  # gap only 14pp in year 2, not year 1
    }
    signals = strengths_and_watchouts({}, history, {}, "bank")
    assert not any(s["rule"] == "pat_lags_nii" for s in signals)


# --------------------------------------------------------------------------
# Insurance template
# --------------------------------------------------------------------------


def test_general_rules_do_not_fire_for_insurance_template():
    metrics = {"roce": 90.0, "interest_coverage": 0.1, "debt_to_assets": 0.9}
    signals = strengths_and_watchouts(metrics, {}, {}, "insurance")
    assert not any(s["rule"] in ("roce_top_quartile", "interest_coverage_thin") for s in signals)


def test_premium_growth_above_median_is_a_strength():
    metrics = {"premium_growth": 20.0}
    peer_values = {"premium_growth": [10.0, 12.0, 13.0]}
    signals = strengths_and_watchouts(metrics, {}, peer_values, "insurance")
    hit = next(s for s in signals if s["rule"] == "premium_growth_vs_median")
    assert hit["type"] == "strength"


def test_premium_growth_within_5pp_of_median_is_not_flagged():
    metrics = {"premium_growth": 14.0}
    peer_values = {"premium_growth": [10.0, 12.0, 13.0]}  # median 12, gap = 2pp
    signals = strengths_and_watchouts(metrics, {}, peer_values, "insurance")
    assert not any(s["rule"] == "premium_growth_vs_median" for s in signals)


def test_insurance_roe_bottom_quartile_is_a_watch():
    metrics = {"roe": 5.0}
    peer_values = {"roe": [5.0, 10.0, 15.0, 20.0]}
    signals = strengths_and_watchouts(metrics, {}, peer_values, "insurance")
    hit = next(s for s in signals if s["rule"] == "roe_bottom_quartile")
    assert hit["type"] == "watch"

from app.metrics.scoring import axis_score, health_radar, percentile_rank


def test_percentile_rank_best_of_peers_is_100():
    assert percentile_rank(10.0, [10.0, 8.0, 5.0, 2.0]) == 100.0


def test_percentile_rank_worst_of_peers_is_lowest():
    # value beats only itself among 4 peers -> 1/4 = 25%
    assert percentile_rank(2.0, [10.0, 8.0, 5.0, 2.0]) == 25.0


def test_percentile_rank_lower_is_better_flips_ranking():
    # For a "lower is better" metric (e.g. D/E), the smallest value wins.
    assert percentile_rank(2.0, [10.0, 8.0, 5.0, 2.0], higher_is_better=False) == 100.0


def test_percentile_rank_none_value_is_none():
    assert percentile_rank(None, [1.0, 2.0]) is None


def test_percentile_rank_all_none_peers_is_none():
    assert percentile_rank(5.0, [None, None]) is None


def test_percentile_rank_ignores_none_peers():
    # 5.0 beats 2.0 but not 10.0, out of 2 valid (non-None) peers = 50%.
    assert percentile_rank(5.0, [10.0, None, 2.0]) == 50.0


def test_axis_score_weighted_average():
    metric_values = {"a": 10.0, "b": 5.0}
    peer_values = {"a": [10.0, 5.0, 0.0], "b": [5.0, 3.0, 1.0]}
    specs = [
        {"key": "a", "weight": 0.5, "higher_is_better": True},
        {"key": "b", "weight": 0.5, "higher_is_better": True},
    ]
    result = axis_score(metric_values, peer_values, specs)
    # a: 10 beats all 3 -> 100th percentile. b: 5 beats all 3 -> 100th percentile.
    assert result["score"] == 100.0
    assert len(result["components"]) == 2


def test_axis_score_missing_metric_excluded_from_weight_total():
    metric_values = {"a": 10.0}  # "b" missing entirely
    peer_values = {"a": [10.0, 5.0], "b": [5.0, 3.0]}
    specs = [
        {"key": "a", "weight": 0.5, "higher_is_better": True},
        {"key": "b", "weight": 0.5, "higher_is_better": True},
    ]
    result = axis_score(metric_values, peer_values, specs)
    # Only "a" contributes; its 100th percentile should be the whole score,
    # not halved by "b"'s absent weight.
    assert result["score"] == 100.0
    assert result["components"][1]["percentile"] is None


def test_axis_score_empty_specs_is_none_not_zero():
    result = axis_score({}, {}, [])
    assert result["score"] is None
    assert result["components"] == []


def test_health_radar_bank_liquidity_axis_is_not_applicable():
    radar = health_radar("bank", {}, {})
    assert radar["liquidity"]["score"] is None
    assert radar["liquidity"]["components"] == []


def test_health_radar_general_has_all_six_axes():
    radar = health_radar("general", {}, {})
    assert set(radar.keys()) == {
        "growth",
        "profitability",
        "leverage",
        "liquidity",
        "efficiency",
        "valuation",
    }


def test_health_radar_unknown_template_falls_back_to_general():
    radar = health_radar("nonexistent", {}, {})  # type: ignore[arg-type]
    assert set(radar.keys()) == {
        "growth",
        "profitability",
        "leverage",
        "liquidity",
        "efficiency",
        "valuation",
    }

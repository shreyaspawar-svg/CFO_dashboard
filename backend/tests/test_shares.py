from app.metrics.shares import adjust_shares_for_splits


def test_no_splits_returns_shares_unchanged():
    assert adjust_shares_for_splits(100, "2024-03-31", [], "2026-09-26") == 100


def test_single_2_for_1_split_after_as_of_doubles_shares():
    splits = [{"date": "2025-01-15", "numerator": 2.0, "denominator": 1.0}]
    assert adjust_shares_for_splits(100, "2024-03-31", splits, "2026-09-26") == 200


def test_split_before_as_of_date_is_not_applied():
    splits = [{"date": "2023-01-15", "numerator": 2.0, "denominator": 1.0}]
    assert adjust_shares_for_splits(100, "2024-03-31", splits, "2026-09-26") == 100


def test_split_after_target_date_is_not_applied():
    splits = [{"date": "2027-01-15", "numerator": 2.0, "denominator": 1.0}]
    assert adjust_shares_for_splits(100, "2024-03-31", splits, "2026-09-26") == 100


def test_bonus_issue_3_for_2_multiplies_by_one_point_five():
    # A "1:2" bonus (1 new share for every 2 held) leaves 3 shares for every
    # 2 previously held -- Yahoo reports this the same way as a stock split,
    # numerator=3, denominator=2.
    splits = [{"date": "2025-06-01", "numerator": 3.0, "denominator": 2.0}]
    assert adjust_shares_for_splits(100, "2024-03-31", splits, "2026-09-26") == 150


def test_multiple_splits_compound():
    splits = [
        {"date": "2024-06-01", "numerator": 2.0, "denominator": 1.0},
        {"date": "2025-06-01", "numerator": 3.0, "denominator": 1.0},
    ]
    # 100 -> 200 (2:1) -> 600 (3:1)
    assert adjust_shares_for_splits(100, "2024-03-31", splits, "2026-09-26") == 600


def test_reverse_split_halves_shares():
    splits = [{"date": "2025-01-15", "numerator": 1.0, "denominator": 2.0}]
    assert adjust_shares_for_splits(200, "2024-03-31", splits, "2026-09-26") == 100


def test_same_date_is_a_no_op():
    splits = [{"date": "2025-01-15", "numerator": 2.0, "denominator": 1.0}]
    assert adjust_shares_for_splits(100, "2024-03-31", splits, "2024-03-31") == 100


def test_target_before_as_of_walks_backwards():
    splits = [{"date": "2024-06-01", "numerator": 2.0, "denominator": 1.0}]
    # Shares reported post-split (as_of later); asked for the pre-split
    # equivalent count as of an earlier target date.
    assert adjust_shares_for_splits(200, "2024-09-30", splits, "2024-01-01") == 100

from app.services.balance_sheet import compute_balance_sheet_period


def test_general_template_balance_check_passes_when_assets_equal_liab_plus_equity():
    li = {
        "total_assets": 1000,
        "total_liabilities": 580,  # + total_equity + minority_interest = 1000
        "total_equity": 400,
        "net_ppe": 300,
        "inventory": 100,
        "receivables": 150,
        "cash_and_equivalents": 200,
        "minority_interest": 20,
        "total_debt": 250,
        "payables": 100,
        "shares_outstanding": 40,
    }
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["balance_check_pct"] == pytest_approx(0.0)
    assert result["assets"]["Other"] == pytest_approx(1000 - (300 + 100 + 150 + 200))
    assert result["liabilities_equity"]["Other"] == pytest_approx(1000 - (400 + 20 + 250 + 100))
    assert result["net_debt"] == pytest_approx(250 - 200)
    # BVPS: equity 400 (Cr) / 40 (raw shares) -> converted via per_share_value
    assert result["bvps"] is not None and result["bvps"] > 0


def test_bank_template_uses_simplified_buckets_and_no_net_debt():
    li = {
        "total_assets": 5000,
        "total_liabilities": 4500,
        "total_equity": 500,
        "net_ppe": 100,
        "cash_and_equivalents": 400,
        "total_debt": 4000,
        "shares_outstanding": 100,
    }
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "bank")
    assert set(result["assets"].keys()) == {"Cash & equivalents", "Investments", "Loans", "Fixed assets", "Other"}
    assert set(result["liabilities_equity"].keys()) == {
        "Equity",
        "Minority interest",
        "Deposits",
        "Borrowings",
        "Other",
    }
    assert result["net_debt"] is None  # not meaningful for a bank


def test_missing_total_assets_leaves_other_and_balance_check_none():
    li = {"net_ppe": 100}
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["assets"]["Other"] is None
    assert result["balance_check_pct"] is None


def test_bvps_none_when_shares_missing():
    li = {"total_equity": 400, "shares_outstanding": None}
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["bvps"] is None


def test_balance_check_includes_minority_interest_in_right_hand_side():
    # total_liabilities + total_equity alone (580+400=980) would wrongly
    # show a 2% gap against total_assets=1000; minority interest (20) must
    # be added to close it, since TotalLiabilitiesNetMinorityInterest and
    # StockholdersEquity both exclude it.
    li = {"total_assets": 1000, "total_liabilities": 580, "total_equity": 400, "minority_interest": 20}
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["balance_check_pct"] == pytest_approx(0.0)


def test_other_current_and_non_current_split_out_when_reported():
    li = {
        "total_assets": 1000,
        "net_ppe": 300,
        "cash_and_equivalents": 200,
        "other_current_assets": 50,
        "other_non_current_assets": 30,
    }
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["assets"]["Other current"] == 50
    assert result["assets"]["Other non-current"] == 30
    # The true residual "Other" shrinks by exactly the amount now attributed
    # to the two split-out buckets, not double-counted.
    assert result["assets"]["Other"] == pytest_approx(1000 - (300 + 200 + 50 + 30))


def test_investments_uses_parent_only_when_subs_exceed_it():
    # RELIANCE-shaped regression: sub-keys (AFS/short-term/long-term-equity)
    # sum to ~3x the InvestmentinFinancialAssets rollup for the same period
    # -- they overlap the parent rather than sitting alongside it, so
    # summing everything double-counts and can even push "Other" negative.
    li = {
        "total_assets": 5000,
        "investments_parent": 1391,
        "investments_subs_sum": 2738,  # 1177 + 1399 + 162, all real RELIANCE FY26 values
        "net_ppe": 2000,
        "cash_and_equivalents": 500,
    }
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["assets"]["Investments"] == 1391
    assert result["assets"]["Other"] >= 0


def test_investments_uses_subs_sum_when_it_does_not_exceed_parent():
    li = {"investments_parent": 1000, "investments_subs_sum": 400}
    result = compute_balance_sheet_period("FY26", "2026-03-31", li, "general")
    assert result["assets"]["Investments"] == 400


def test_investments_falls_back_to_whichever_side_is_present():
    assert compute_balance_sheet_period("FY26", "2026-03-31", {"investments_parent": 500}, "general")["assets"][
        "Investments"
    ] == 500
    assert compute_balance_sheet_period("FY26", "2026-03-31", {"investments_subs_sum": 300}, "general")["assets"][
        "Investments"
    ] == 300


def pytest_approx(x):
    import pytest

    return pytest.approx(x, abs=1e-6)

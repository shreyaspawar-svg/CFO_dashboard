import pytest

from app.services.cash_flow_detail import compute_cash_flow_ratios, compute_cash_flow_sankey


def _net_flow(sankey: dict, node: str) -> float:
    inflow = sum(link["value"] for link in sankey["links"] if link["target"] == node)
    outflow = sum(link["value"] for link in sankey["links"] if link["source"] == node)
    return inflow - outflow


def test_sankey_reconciles_exactly_to_reported_change_in_cash_via_other_link():
    sankey = compute_cash_flow_sankey(cfo=500, cfi=-300, cff=-150, actual_change_in_cash=60)
    # computed = 500 - 300 - 150 = 50; reported = 60 -> gap = 10, must show as "Other"
    assert sankey["gap"] == pytest.approx(10)
    assert any(l["source"] == "Other (FX/rounding)" for l in sankey["links"])
    # The Cash pool's net inflow must equal the ACTUAL reported change --
    # the whole point of the reconciliation link.
    assert _net_flow(sankey, "Cash pool") == pytest.approx(60)


def test_sankey_with_no_gap_omits_the_other_link():
    sankey = compute_cash_flow_sankey(cfo=500, cfi=-300, cff=-150, actual_change_in_cash=50)
    assert sankey["gap"] == pytest.approx(0)
    assert not any(l["source"] == "Other (FX/rounding)" or l["target"] == "Other (FX/rounding)" for l in sankey["links"])


def test_sankey_negative_gap_flows_out_to_other():
    sankey = compute_cash_flow_sankey(cfo=500, cfi=-300, cff=-150, actual_change_in_cash=30)
    # computed = 50, reported = 30 -> gap = -20, flows OUT of the cash pool
    assert sankey["gap"] == pytest.approx(-20)
    assert any(l["target"] == "Other (FX/rounding)" for l in sankey["links"])
    assert _net_flow(sankey, "Cash pool") == pytest.approx(30)


def test_sankey_missing_actual_change_skips_gap_but_still_computes():
    sankey = compute_cash_flow_sankey(cfo=500, cfi=-300, cff=-150, actual_change_in_cash=None)
    assert sankey["computed_change_in_cash"] == pytest.approx(50)
    assert sankey["gap"] is None
    assert not any("Other" in (l["source"], l["target"]) for l in sankey["links"])


def test_sankey_shows_fx_effect_as_its_own_labelled_flow_and_still_reconciles():
    sankey = compute_cash_flow_sankey(cfo=500, cfi=-300, cff=-150, actual_change_in_cash=55, fx_effect=5)
    # computed = 500 - 300 - 150 + 5 = 55 -> matches reported exactly, no gap link
    assert sankey["gap"] == pytest.approx(0)
    assert any(l["source"] == "FX translation effect" for l in sankey["links"])
    assert not any("Other" in (l["source"], l["target"]) for l in sankey["links"])
    assert _net_flow(sankey, "Cash pool") == pytest.approx(55)


def test_cash_flow_ratios_basic():
    result = compute_cash_flow_ratios(cfo=500, ebitda=1000, net_income=400, fcf=300, revenue=2000)
    assert result["cfo_to_ebitda"] == pytest.approx(0.5)
    assert result["cfo_to_pat"] == pytest.approx(1.25)
    assert result["fcf_margin_pct"] == pytest.approx(15.0)


def test_cash_flow_ratios_none_safe():
    result = compute_cash_flow_ratios(None, None, None, None, None)
    assert result == {"cfo_to_ebitda": None, "cfo_to_pat": None, "fcf_margin_pct": None}

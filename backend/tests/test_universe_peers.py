from app.services.universe import peer_group_for_symbol


def test_small_sector_falls_back_to_template():
    # Telecom has exactly 1 company (BHARTIARTL) -- must fall back to the
    # "general" template group, which spans dozens of companies.
    peers, basis = peer_group_for_symbol("BHARTIARTL")
    assert basis == "template"
    assert len(peers) > 10
    assert all(c.template == "general" for c in peers)


def test_capital_goods_defence_single_company_falls_back():
    peers, basis = peer_group_for_symbol("BEL")
    assert basis == "template"


def test_large_sector_uses_sector_peers():
    # Banks & Financial Services has 12 companies -- no fallback needed.
    peers, basis = peer_group_for_symbol("HDFCBANK")
    assert basis == "sector"
    assert len(peers) == 12


def test_construction_and_materials_exactly_at_threshold_uses_sector():
    # Exactly 3 companies -- the plan's threshold keeps this as "sector",
    # matching its own list of which sectors fall back and which don't.
    peers, basis = peer_group_for_symbol("LT")
    assert basis == "sector"
    assert len(peers) == 3


def test_unknown_symbol_returns_empty():
    peers, basis = peer_group_for_symbol("NOTREAL")
    assert peers == []
    assert basis == "none"

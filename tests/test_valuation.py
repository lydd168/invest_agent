"""Valuation helper tests."""

from __future__ import annotations

from valuation import dcf, multiples


def test_discounted_cash_flow_handles_negative_inputs():
    result = dcf.discounted_cash_flow(
        free_cash_flows=[-100, 50, 60, 70],
        discount_rate=0.1,
        growth_rate=0.05,
        terminal_growth=0.02,
        shares_outstanding=1_000_000,
    )
    assert result["intrinsic_value_per_share"] is not None
    assert result["enterprise_value"] > 0


def test_multiples_intrinsic_value_from_eps():
    result = multiples.valuation_from_multiples(
        price=150,
        eps=5,
        revenue=None,
        ebit=None,
        shares_outstanding=1_000_000,
        terminal_multiple=15,
    )
    assert result["intrinsic_value_per_share"] == 75


def test_multiples_handles_missing_data():
    result = multiples.valuation_from_multiples(
        price=None,
        eps=None,
        revenue=None,
        ebit=None,
        shares_outstanding=0,
        terminal_multiple=15,
    )
    assert result["intrinsic_value_per_share"] is None
    assert result["pe"] is None

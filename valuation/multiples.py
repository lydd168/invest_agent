"""Simple multiples-based valuation helpers."""

from __future__ import annotations

from typing import Optional


def _safe_float(value: Optional[float]) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def valuation_from_multiples(
    price: Optional[float],
    eps: Optional[float],
    revenue: Optional[float],
    ebit: Optional[float],
    shares_outstanding: float,
    terminal_multiple: float,
) -> dict:
    price = _safe_float(price)
    eps = _safe_float(eps)
    revenue = _safe_float(revenue)
    ebit = _safe_float(ebit)
    shares = shares_outstanding if shares_outstanding > 0 else 1.0

    pe = (price / eps) if price and eps and eps != 0 else None
    ps = (price / (revenue / shares)) if price and revenue else None
    ev_ebit = None
    intrinsic_value = None

    if ebit and ebit > 0 and shares > 0:
        enterprise_value = ebit * terminal_multiple
        intrinsic_value = enterprise_value / shares
        ev_ebit = enterprise_value / ebit
    elif eps and eps > 0:
        intrinsic_value = eps * terminal_multiple

    return {
        "pe": pe,
        "ps": ps,
        "ev_ebit": ev_ebit,
        "intrinsic_value_per_share": intrinsic_value,
    }

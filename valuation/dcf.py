"""Deterministic discounted cash flow helper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass
class DCFResult:
    projected_fcf: List[float]
    discount_rate: float
    terminal_growth: float
    present_value: float
    terminal_value: float
    enterprise_value: float
    intrinsic_value_per_share: Optional[float]


def _initial_fcf(series: Iterable[float]) -> Optional[float]:
    values = [float(value) for value in series if value is not None]
    if not values:
        return None
    return values[-1]


def _project_cash_flows(latest_fcf: float, growth_rate: float, years: int = 5) -> List[float]:
    flows = []
    current = latest_fcf
    for _ in range(years):
        current *= 1 + growth_rate
        flows.append(current)
    return flows


def discounted_cash_flow(
    free_cash_flows: Iterable[float],
    discount_rate: float,
    growth_rate: float,
    terminal_growth: float,
    shares_outstanding: float,
    horizon_years: int = 5,
) -> dict:
    latest_fcf = _initial_fcf(free_cash_flows)
    if latest_fcf is None or shares_outstanding <= 0:
        return {
            "projected_fcf": [],
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "present_value": 0.0,
            "terminal_value": 0.0,
            "enterprise_value": 0.0,
            "intrinsic_value_per_share": None,
        }

    projected = _project_cash_flows(latest_fcf, growth_rate, horizon_years)

    present_value = 0.0
    for year, flow in enumerate(projected, start=1):
        present_value += flow / ((1 + discount_rate) ** year)

    terminal_value = projected[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth) if discount_rate > terminal_growth else 0.0
    terminal_present_value = terminal_value / ((1 + discount_rate) ** horizon_years)

    enterprise_value = present_value + terminal_present_value
    intrinsic_value_per_share = enterprise_value / shares_outstanding if enterprise_value > 0 else None

    result = DCFResult(
        projected_fcf=projected,
        discount_rate=discount_rate,
        terminal_growth=terminal_growth,
        present_value=present_value,
        terminal_value=terminal_value,
        enterprise_value=enterprise_value,
        intrinsic_value_per_share=intrinsic_value_per_share,
    )
    return result.__dict__

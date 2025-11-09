"""Valuation Model: 綜合 DCF 與倍數，輸出內在價值區間與安全邊際。"""

from __future__ import annotations

from statistics import mean
from typing import Dict, List, Optional

from valuation import dcf as dcf_module
from valuation import multiples as multiples_module


def _latest_close(price_history: List[Dict]) -> Optional[float]:
    for row in reversed(price_history):
        close = row.get("close")
        if close is None:
            continue
        try:
            return float(close)
        except (TypeError, ValueError):
            continue
    return None


def _latest_fcf(info: Dict) -> Optional[float]:
    cashflow = info.get("cashflow", {}) if isinstance(info, dict) else {}
    series = cashflow.get("freeCashFlows") if isinstance(cashflow, dict) else None
    if isinstance(series, list) and series:
        try:
            return float(series[-1])
        except (TypeError, ValueError):
            return None
    value = cashflow.get("freeCashflow") if isinstance(cashflow, dict) else None
    if value is None:
        value = info.get("metrics", {}).get("freeCashflow") if isinstance(info, dict) else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _shares_outstanding(info: Dict) -> Optional[float]:
    count = info.get("metrics", {}).get("sharesOutstanding") if isinstance(info, dict) else None
    if count is None and isinstance(info, dict):
        count = info.get("shareCount") or info.get("shares")
    try:
        return float(count) if count is not None else None
    except (TypeError, ValueError):
        return None


class ValuationModelAgent:
    """量化估值模組整合，計算內在價值區間與 MOS。"""

    def __init__(self, discount_rate: float = 0.1, terminal_growth: float = 0.02, terminal_multiple: float = 15.0) -> None:
        self.discount_rate = discount_rate
        self.terminal_growth = terminal_growth
        self.terminal_multiple = terminal_multiple

    def _dcf(self, info: Dict, metrics: Dict, price_history: List[Dict]) -> Dict:
        fcf_series = info.get("cashflow", {}).get("freeCashFlows", []) if isinstance(info, dict) else []
        shares = _shares_outstanding(info) or 1.0
        growth = metrics.get("fcf_cagr") if metrics else None
        growth_rate = growth if growth is not None else 0.05
        return dcf_module.discounted_cash_flow(
            free_cash_flows=fcf_series,
            discount_rate=self.discount_rate,
            growth_rate=growth_rate,
            terminal_growth=self.terminal_growth,
            shares_outstanding=shares,
        )

    def _multiples(self, info: Dict, metrics: Dict, price_history: List[Dict]) -> Dict:
        price = _latest_close(price_history) or 0.0
        eps = info.get("metrics", {}).get("eps") if isinstance(info, dict) else None
        revenue = info.get("financials", {}).get("totalRevenue") if isinstance(info, dict) else None
        ebit = info.get("financials", {}).get("ebit") if isinstance(info, dict) else None
        shares = _shares_outstanding(info) or 1.0
        return multiples_module.valuation_from_multiples(
            price=price,
            eps=eps,
            revenue=revenue,
            ebit=ebit,
            shares_outstanding=shares,
            terminal_multiple=self.terminal_multiple,
        )

    def evaluate(self, fundamentals: List[Dict]) -> List[Dict]:
        output: List[Dict] = []
        for item in fundamentals:
            ticker = item.get("ticker")
            info = item.get("info", {})
            metrics = item.get("metrics", {})
            price_history = item.get("price_history", [])
            price = _latest_close(price_history)

            dcf_result = self._dcf(info, metrics, price_history)
            multiples_result = self._multiples(info, metrics, price_history)

            intrinsic_candidates = [
                dcf_result.get("intrinsic_value_per_share"),
                multiples_result.get("intrinsic_value_per_share"),
            ]
            intrinsic_values = [value for value in intrinsic_candidates if isinstance(value, (int, float))]
            if intrinsic_values:
                midpoint = mean(intrinsic_values)
                low = min(intrinsic_values)
                high = max(intrinsic_values)
            else:
                midpoint = low = high = None

            margin_of_safety = None
            if midpoint and price:
                margin_of_safety = (midpoint - price) / midpoint

            output.append(
                {
                    "ticker": ticker,
                    "price": price,
                    "dcf": dcf_result,
                    "multiples": multiples_result,
                    "intrinsic_value_range": {
                        "low": low,
                        "mid": midpoint,
                        "high": high,
                    },
                    "margin_of_safety": margin_of_safety,
                }
            )
        return output

    def run(self, state: Dict) -> Dict:
        fundamentals = state.get("fundamentals", [])
        valuations = self.evaluate(fundamentals)
        state["valuation"] = valuations
        return state

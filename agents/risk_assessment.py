"""Risk Assessment: 嚴謹的保守過濾與倉位限制規則。"""

from __future__ import annotations

from typing import Dict, List


class RiskAssessmentAgent:
    """以保守原則過濾脆弱資產負債表並約束倉位。"""

    def __init__(self, max_weight: float = 0.10, leverage_threshold: float = 3.0) -> None:
        self.max_weight = max_weight
        self.leverage_threshold = leverage_threshold

    def assess(self, fundamentals: List[Dict], valuations: List[Dict]) -> List[Dict]:
        summary: List[Dict] = []
        valuation_map = {item.get("ticker"): item for item in valuations}
        for item in fundamentals:
            ticker = item.get("ticker")
            metrics = item.get("metrics", {})
            valuation = valuation_map.get(ticker, {})
            flags = []

            debt_to_fcf = metrics.get("debt_to_fcf")
            if debt_to_fcf is not None and debt_to_fcf > self.leverage_threshold:
                flags.append("High leverage vs FCF")

            fcf_cagr = metrics.get("fcf_cagr")
            if fcf_cagr is not None and fcf_cagr < 0:
                flags.append("Negative FCF growth")

            mos = valuation.get("margin_of_safety")
            allowed = mos is not None and mos > 0 and "High leverage vs FCF" not in flags
            weight = self.max_weight if allowed else 0.0

            summary.append(
                {
                    "ticker": ticker,
                    "flags": flags,
                    "margin_of_safety": mos,
                    "position_weight": weight,
                    "allowed": allowed,
                }
            )
        return summary

    def run(self, state: Dict) -> Dict:
        fundamentals = state.get("fundamentals", [])
        valuations = state.get("valuation", [])
        state["risk"] = self.assess(fundamentals, valuations)
        return state

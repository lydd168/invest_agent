"""Strategy Synthesis: LLM 產生倉位與決策理由（可降級為無 LLM）。"""

from __future__ import annotations

import os
from typing import Dict, Any, List

try:
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    ChatOpenAI = None  # type: ignore
    HumanMessage = None  # type: ignore
    SystemMessage = None  # type: ignore
    LLM_AVAILABLE = False


SYSTEM_PROMPT = (
    "你是嚴謹的價值投資分析師。請以巴菲特風格，基於提供的數據（估值、風險、新聞)"
    "給出簡潔、可執行的倉位建議與理由。必要時指出關鍵風險與需要跟進的指標。"
)


class StrategySynthesisAgent:
    def __init__(self, model: str | None = None, temperature: float = 0.1) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature

    def _fallback(self, ticker: str, valuation: Dict, risk: Dict) -> Dict[str, Any]:
        mos = valuation.get("margin_of_safety")
        allowed = risk.get("allowed")
        weight = risk.get("position_weight") or 0
        lines: List[str] = []
        if allowed and (mos or 0) > 0:
            lines.append("建議小幅建倉，持續觀察自由現金流與利潤率走勢。")
        elif allowed:
            lines.append("條件尚可，但缺乏安全邊際，建議觀望或極小倉位。")
        else:
            lines.append("風險訊號偏弱，建議暫不建倉。")
        return {
            "ticker": ticker,
            "strategy_comment": "\n".join(lines),
        }

    def run(self, state: Dict) -> Dict:
        fundamentals = state.get("fundamentals", [])
        valuations = {v.get("ticker"): v for v in state.get("valuation", [])}
        risks = {r.get("ticker"): r for r in state.get("risk", [])}

        outputs: List[Dict[str, Any]] = []
        if not LLM_AVAILABLE or not os.getenv("OPENAI_API_KEY"):
            for f in fundamentals:
                t = f.get("ticker")
                outputs.append(self._fallback(t, valuations.get(t, {}), risks.get(t, {})))
            state["llm_strategy"] = outputs
            return state

        llm = ChatOpenAI(model=self.model, temperature=self.temperature)

        for f in fundamentals:
            t = f.get("ticker")
            payload = {
                "ticker": t,
                "valuation": valuations.get(t, {}),
                "risk": risks.get(t, {}),
            }
            msg = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"請評估 {t} 的倉位與決策建議，資料：{payload}"),
            ]
            try:
                resp = llm.invoke(msg)
                comment = getattr(resp, "content", None) or "(no content)"
            except Exception:
                comment = self._fallback(t, payload["valuation"], payload["risk"]) [
                    "strategy_comment"
                ]
            outputs.append({"ticker": t, "strategy_comment": comment})

        state["llm_strategy"] = outputs
        return state

"""Narrative Writer: LLM/啟發式整合敘事（護城河、估值、新聞、風險）。"""

from __future__ import annotations

import os
from typing import Dict, Any, List

try:
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    HumanMessage = None  # type: ignore
    SystemMessage = None  # type: ignore
    LLM_AVAILABLE = False


SYSTEM_PROMPT = (
    "你是資深價值投資顧問，將提供公司近期投資敘事：競爭優勢、財務趨勢、新聞脈絡、關鍵風險與觀察指標。"
    "語氣務實、避免浮誇；可列出 2-4 個後續追蹤重點。"
)


class NarrativeWriterAgent:
    def __init__(self, model: str | None = None, temperature: float = 0.3) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature

    def _heuristic(self, ticker: str, fundamentals: Dict, valuation: Dict, news: Dict, risk: Dict) -> Dict[str, Any]:
        moat = fundamentals.get("metrics", {})
        mos = valuation.get("margin_of_safety")
        sentiment = news.get("sentiment")
        risk_flags = risk.get("flags", [])
        bullets: List[str] = []
        if moat.get("roic"):
            bullets.append("ROIC 指標顯示資本效率穩定。")
        if mos is not None and mos > 0:
            bullets.append("估值顯示存在安全邊際。")
        elif mos is not None:
            bullets.append("目前價格高於估算內在價值，缺乏安全邊際。")
        if sentiment is not None:
            bullets.append(f"近期新聞情緒分數為 {sentiment:.2f}。")
        if risk_flags:
            bullets.append("風險關鍵: " + ", ".join(risk_flags))
        if not bullets:
            bullets.append("尚缺乏可用敘事要素。")
        return {"ticker": ticker, "narrative": "\n".join(bullets)}

    def run(self, state: Dict) -> Dict:
        fundamentals_list = state.get("fundamentals", [])
        valuations = {v.get("ticker"): v for v in state.get("valuation", [])}
        risks = {r.get("ticker"): r for r in state.get("risk", [])}
        news_bundle = {n.get("ticker"): n for n in state.get("news_bundle", [])}

        outputs: List[Dict[str, Any]] = []
        if not LLM_AVAILABLE or not os.getenv("OPENAI_API_KEY"):
            for f in fundamentals_list:
                t = f.get("ticker")
                outputs.append(self._heuristic(t, f, valuations.get(t, {}), news_bundle.get(t, {}), risks.get(t, {})))
            state["llm_narrative"] = outputs
            return state

        llm = ChatOpenAI(model=self.model, temperature=self.temperature)
        for f in fundamentals_list:
            t = f.get("ticker")
            payload = {
                "fundamentals": f,
                "valuation": valuations.get(t, {}),
                "risk": risks.get(t, {}),
                "news": news_bundle.get(t, {}),
            }
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"整合敘述 {t}：{payload}"),
            ]
            try:
                resp = llm.invoke(messages)
                narrative = getattr(resp, "content", None) or "(no content)"
            except Exception:  # pragma: no cover
                narrative = self._heuristic(t, f, payload["valuation"], payload["news"], payload["risk"]) ["narrative"]
            outputs.append({"ticker": t, "narrative": narrative})

        state["llm_narrative"] = outputs
        return state

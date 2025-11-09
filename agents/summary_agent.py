from __future__ import annotations

import os
from typing import Any, Dict, List


def _build_llm(model_name: str = "gpt-4o-mini", temperature: float = 0.1):
    """建立可用的 ChatOpenAI 實例，失敗則拋出例外。"""
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("langchain-openai is required for LLM mode") from exc
    return ChatOpenAI(model=model_name, temperature=temperature)


class SummaryAgent:
    """使用單一 LLM 針對每檔股票摘要（不依賴 LangGraph/LangChain 預製 agent）。"""

    def __init__(self, model: str | None = None, temperature: float = 0.1):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature

    def _prompt(self, ticker: str, state: Dict) -> str:
        risk_map = {r.get("ticker"): r for r in state.get("risk", [])}
        news_map = {n.get("ticker"): n for n in state.get("news_bundle", [])}
        val_map = {v.get("ticker"): v for v in state.get("valuation", [])}

        risk = risk_map.get(ticker, {}) or {}
        news = news_map.get(ticker, {}) or {}
        val = val_map.get(ticker, {}) or {}
        mos = val.get("margin_of_safety")
        sentiment = news.get("sentiment")
        flags = risk.get("flags", []) or []
        bullets = (news.get("bullets", []) or [])[:5]

        return (
            "你是一位嚴謹的投資研究員，請用繁體中文輸出 5-8 條條列摘要，聚焦：\n"
            f"- 股票：{ticker}\n"
            f"- 安全邊際（MOS）：{mos}\n"
            f"- 風險旗標：{flags}\n"
            f"- 新聞要點（最多 5 條）：{bullets}\n"
            f"- 新聞情緒分數：{sentiment}\n\n"
            "請給出：\n"
            "1) 估值與風險綜合判斷（簡潔）。\n"
            "2) 近期新聞對基本面的可能影響（1-2 條）。\n"
            "3) 接下來 2-3 個可行的追蹤動作或指標。\n"
            "輸出限制：不贅述數據來源，不生成結論以外的長段文字。"
        )

    def run(self, state: Dict) -> Dict:
        summary_meta: List[Dict[str, Any]] = []

        # 建立 LLM；失敗則退回啟發式
        try:
            llm = _build_llm(self.model, self.temperature)
        except Exception as exc:
            llm = None
            llm_err = str(exc)
        else:
            llm_err = None

        outputs = []
        tickers = [f.get("ticker") for f in state.get("fundamentals", []) if f.get("ticker")]

        for t in tickers:
            prompt = self._prompt(t, state)

            if llm is not None:
                try:
                    llm_res = llm.invoke(prompt)  # type: ignore
                    content_text = getattr(llm_res, "content", None) or str(llm_res)
                    content = "（LLM）\n" + content_text
                    summary_meta.append({"ticker": t, "mode": "llm"})
                except Exception as exc:
                    content = (
                        "（Heuristic）\n"
                        "- 綜合判斷：估值與風險均衡，建議持續觀察。\n"
                        "- 新聞影響：短期波動可能加劇。\n"
                        "- 後續追蹤：FCF、需求動能、資本支出。"
                    )
                    summary_meta.append({"ticker": t, "mode": "heuristic", "reason": f"llm_invoke_error: {exc}"})
            else:
                content = (
                    "（Heuristic）\n"
                    "- 綜合判斷：估值與風險均衡，建議持續觀察。\n"
                    "- 新聞影響：短期波動可能加劇。\n"
                    "- 後續追蹤：FCF、需求動能、資本支出。"
                )
                summary_meta.append({"ticker": t, "mode": "heuristic", "reason": llm_err or "no_llm"})

            outputs.append({"ticker": t, "summary": content})

        state["summary_insight"] = outputs
        state["summary_meta"] = summary_meta
        return state

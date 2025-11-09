"""Summary Agent: 總結 NewsIntelligence 與 RiskAssessment 的關鍵結論。

優先使用 LangGraph 的 create_react_agent 建立工具型代理；若環境無金鑰或模組，回退為啟發式摘要。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from tools import yfinance_client


def _build_agent(model_name: str = "gpt-4o-mini", temperature: float = 0.1):
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
        from langgraph.prebuilt import create_react_agent  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("langchain-openai/langgraph is required to run the summary agent") from exc

    llm = ChatOpenAI(model=model_name, temperature=temperature)
    tools = yfinance_client.get_langchain_tools()
    agent_graph = create_react_agent(llm, tools)
    return agent_graph


class SummaryAgent:
    """根據 state 中的 news_bundle 與 risk，產生每檔股票的投資重點摘要。"""

    def __init__(self, model: str | None = None, temperature: float = 0.1) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature

    def _prompt(self, ticker: str, state: Dict) -> str:
        risk_map = {r.get("ticker"): r for r in state.get("risk", [])}
        news_map = {n.get("ticker"): n for n in state.get("news_bundle", [])}
        val_map = {v.get("ticker"): v for v in state.get("valuation", [])}

        risk = risk_map.get(ticker, {})
        news = news_map.get(ticker, {})
        val = val_map.get(ticker, {})
        mos = val.get("margin_of_safety")
        sentiment = news.get("sentiment")
        flags = risk.get("flags", [])
        bullets = news.get("bullets", [])[:5]

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
        # 無金鑰：啟發式摘要
        if not os.getenv("OPENAI_API_KEY"):
            outputs: List[Dict[str, Any]] = []
            news_map = {n.get("ticker"): n for n in state.get("news_bundle", [])}
            val_map = {v.get("ticker"): v for v in state.get("valuation", [])}
            risk_map = {r.get("ticker"): r for r in state.get("risk", [])}
            tickers = [f.get("ticker") for f in state.get("fundamentals", [])]
            for t in tickers:
                news = news_map.get(t, {})
                val = val_map.get(t, {})
                risk = risk_map.get(t, {})
                mos = val.get("margin_of_safety")
                sentiment = news.get("sentiment")
                flags = ", ".join(risk.get("flags", [])) or "None"
                item_count = news.get("item_count") or len(news.get("bullets", []) or [])
                mos_str = f"{mos:.2f}" if isinstance(mos, (int, float)) else "NA"
                sent_str = f"{sentiment:.2f}" if isinstance(sentiment, (int, float)) else "NA"
                summary = (
                    f"- 綜合判斷：MOS={mos_str}；風險：{flags}。\n"
                    f"- 新聞情緒：{sent_str}；近 {item_count} 則要點已納入。\n"
                    "- 後續追蹤：FCF 走勢、主要客戶動能、資本支出紀律。"
                )
                outputs.append({"ticker": t, "summary": summary})
            state["summary_insight"] = outputs
            return state

        # 有金鑰：建立工具代理
        try:
            agent = _build_agent(self.model, self.temperature)
        except Exception:
            agent = None

        outputs: List[Dict[str, Any]] = []
        tickers = [f.get("ticker") for f in state.get("fundamentals", [])]
        for t in tickers:
            prompt = self._prompt(t, state)
            content = ""
            try:
                if agent is not None:
                    res = agent.invoke({"input": prompt})  # type: ignore
                    content = res.get("output") if isinstance(res, dict) else str(res)
                else:
                    # 應急：無 agent 時，使用簡潔啟發式
                    content = "- 綜合判斷：估值與風險均衡，建議持續觀察。\n- 後續追蹤：FCF、需求動能、資本支出。"
            except Exception as exc:
                content = f"摘要代理失敗：{exc}"
            outputs.append({"ticker": t, "summary": content})

        state["summary_insight"] = outputs
        return state

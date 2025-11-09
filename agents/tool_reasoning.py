"""Tool Reasoning: LLM 工具輔助核對/補充，支援回退的簡易執行。"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from tools import yfinance_client


def _build_agent_and_executor(model_name: str = "gpt-4o-mini", temperature: float = 0.1):
    """回傳 (agent, executor_like) 支援 .invoke/.run

    先試 create_react_agent，不行則回退簡易工具執行。
    """
    # Model
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("langchain-openai is required to run the tool agent") from exc

    llm = ChatOpenAI(model=model_name, temperature=temperature)
    tools = yfinance_client.get_langchain_tools()

    try:
        from langgraph.prebuilt import create_react_agent  # type: ignore
        agent_graph = create_react_agent(llm, tools)
        return agent_graph, agent_graph
    except Exception:
        pass

    class _PseudoExecutor:
        def __init__(self, llm, tools):
            self.llm = llm
            self.tools = {tool.name: tool for tool in tools}

        def invoke(self, inputs: Dict[str, Any]):  # mimic agent executor
            query = inputs.get("input", "")
            extra: List[str] = []
            if "price" in query.lower() and "get_price_history" in self.tools:
                ph = self.tools["get_price_history"].run({"symbol": "AAPL", "period": "1mo", "interval": "1d"})
                extra.append(f"[price_history:1mo_days={len(ph.get('data', [])) if isinstance(ph, dict) else 'NA'}]")
            prompt = query + ("\n" + " ".join(extra) if extra else "")
            resp = self.llm.invoke(prompt)  # type: ignore
            return {"output": getattr(resp, "content", str(resp))}

    return None, _PseudoExecutor(llm, tools)


class ToolReasoningAgent:
    """針對每檔股票進行工具輔助推理，產出簡明摘要。"""

    def __init__(self, model: str | None = None, temperature: float = 0.1) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature

    def _question(self, ticker: str, state: Dict) -> str:
        val = {v.get("ticker"): v for v in state.get("valuation", [])}.get(ticker, {})
        risk = {r.get("ticker"): r for r in state.get("risk", [])}.get(ticker, {})
        news = {n.get("ticker"): n for n in state.get("news_bundle", [])}.get(ticker, {})
        return (
            f"請針對 {ticker}：\n"
            "1) 使用必要工具快速核對：基本面/股價歷史/近期新聞（只取必要資料）。\n"
            f"2) 目前估值與安全邊際：{val.get('intrinsic_value_range')}，MOS={val.get('margin_of_safety')}。\n"
            f"3) 風險旗標：{risk.get('flags', [])}。\n"
            f"4) 近期新聞彙整筆數：{news.get('item_count', 0)}。\n"
            "輸出：3-6 個條列結論 + 2-3 個後續追蹤指標。若工具查無資料，請明確標註。"
        )

    def run(self, state: Dict) -> Dict:
        if not os.getenv("OPENAI_API_KEY"):
            outputs: List[Dict[str, Any]] = []
            for f in state.get("fundamentals", []):
                t = f.get("ticker")
                outputs.append({
                    "ticker": t,
                    "tool_summary": "(No API key) 工具代理未執行。"
                })
            state["llm_tool_agent"] = outputs
            return state

        _, executor = _build_agent_and_executor(self.model, self.temperature)

        outputs: List[Dict[str, Any]] = []
        for f in state.get("fundamentals", []):
            t = f.get("ticker")
            prompt = self._question(t, state)
            try:
                result = None
                try:
                    result = executor.invoke({"input": prompt})  # type: ignore
                    content = result.get("output") if isinstance(result, dict) else str(result)
                except Exception:
                    content = executor.run(prompt)  # type: ignore
            except Exception as exc:
                content = f"工具代理失敗：{exc}"
            outputs.append({"ticker": t, "tool_summary": content})

        state["llm_tool_agent"] = outputs
        return state

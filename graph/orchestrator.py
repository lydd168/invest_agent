"""LangGraph-based orchestrator for the Buffett research workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from typing import Annotated

from agents.candidate_screener import CandidateScreenerAgent
from agents.input_supervisor import InputSupervisorAgent
from agents.fundamentals_analyst import FundamentalsAnalystAgent
from agents.news_intelligence import NewsIntelligenceAgent
from agents.valuation_model import ValuationModelAgent
from agents.risk_assessment import RiskAssessmentAgent
from agents.markdown_reporter import MarkdownReporterAgent
from agents.strategy_synthesis import StrategySynthesisAgent
from agents.narrative_writer import NarrativeWriterAgent
from agents.tool_reasoning import ToolReasoningAgent


class PipelineState(TypedDict, total=False):
    params: Dict  # singleton semantics not supported; we'll avoid duplicate writes manually
    candidates: List[str]
    fundamentals: List[Dict]
    news_bundle: List[Dict]
    valuation: List[Dict]
    risk: List[Dict]
    llm_strategy: List[Dict]
    llm_narrative: List[Dict]
    llm_tool_agent: List[Dict]
    report_path: str


def _default_params(user_input: Dict) -> Dict:
    params = dict(user_input or {})
    params.setdefault("tickers", None)
    params.setdefault("sector", None)
    params.setdefault("query", None)
    params.setdefault("news_window_days", 14)
    params.setdefault("max_candidates", None)
    params.setdefault("max_news", 30)
    params.setdefault("reports_dir", None)
    return params


def run_pipeline(user_input: Dict) -> Path:
    params = _default_params(user_input)

    supervisor = InputSupervisorAgent()
    screener = CandidateScreenerAgent()
    analyst = FundamentalsAnalystAgent()
    news_agent = NewsIntelligenceAgent(window_days=params["news_window_days"], max_news=params["max_news"])
    valuation_agent = ValuationModelAgent()
    risk_agent = RiskAssessmentAgent()
    reporter = MarkdownReporterAgent(reports_dir=params.get("reports_dir"))
    llm_strategy_agent = StrategySynthesisAgent()
    llm_narrative_agent = NarrativeWriterAgent()
    llm_tool_agent = ToolReasoningAgent()

    graph: StateGraph[PipelineState] = StateGraph(PipelineState)

    def screener_node(state: PipelineState) -> PipelineState:
        screener.run(state)
        return {"candidates": state.get("candidates", [])}  # type: ignore[return-value]

    def analyst_node(state: PipelineState) -> PipelineState:
        analyst.run(state)
        return {"fundamentals": state.get("fundamentals", [])}  # type: ignore[return-value]

    def news_node(state: PipelineState) -> PipelineState:
        news_agent.run(state)
        return {"news_bundle": state.get("news_bundle", [])}  # type: ignore[return-value]

    def valuation_node(state: PipelineState) -> PipelineState:
        valuation_agent.run(state)
        return {"valuation": state.get("valuation", [])}  # type: ignore[return-value]

    def risk_node(state: PipelineState) -> PipelineState:
        risk_agent.run(state)
        return {"risk": state.get("risk", [])}  # type: ignore[return-value]

    # Join gate to ensure both news and risk are ready before advancing to LLMs
    def join_gate_node(state: PipelineState) -> PipelineState:
        # 不寫入任何鍵，避免並行寫入衝突
        return {}

    def _join_ready(state: PipelineState) -> str:
        candidates = state.get("candidates") or []
        news = state.get("news_bundle") or []
        has_news = isinstance(news, list) and (len(news) >= len(candidates))
        has_risk = bool(state.get("risk"))
        return "ready" if has_news and has_risk else "wait"

    def llm_strategy_node(state: PipelineState) -> PipelineState:
        # 策略生成不依賴敘事/工具，可並行
        llm_strategy_agent.run(state)
        return {"llm_strategy": state.get("llm_strategy", [])}  # type: ignore[return-value]

    def llm_narrative_node(state: PipelineState) -> PipelineState:
        # 敘事生成不依賴策略結果（只用 fundamentals/valuation/risk/news），可並行
        llm_narrative_agent.run(state)
        return {"llm_narrative": state.get("llm_narrative", [])}  # type: ignore[return-value]

    def llm_tool_node(state: PipelineState) -> PipelineState:
        # 工具驗證僅依賴 fundamentals/valuation/risk/news，可並行
        llm_tool_agent.run(state)
        return {"llm_tool_agent": state.get("llm_tool_agent", [])}  # type: ignore[return-value]

    # Gate to wait for all three LLM outputs before reporting
    def llm_join_node(state: PipelineState) -> PipelineState:
        # 不寫入任何鍵，避免並行寫入衝突
        return {}

    def _llm_ready(state: PipelineState) -> str:
        has_strategy = bool(state.get("llm_strategy"))
        has_narrative = bool(state.get("llm_narrative"))
        has_tool = bool(state.get("llm_tool_agent"))
        return "ready" if (has_strategy and has_narrative and has_tool) else "wait"

    def reporter_node(state: PipelineState) -> PipelineState:
        path = reporter.run(state)
        state["report_path"] = str(path)
        return {"report_path": str(path)}  # type: ignore[return-value]

    def supervisor_node(state: PipelineState) -> PipelineState:
        supervisor.run(state)
        # Only emit candidates if supervisor set them.
        return {"candidates": state.get("candidates", [])}

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("screener", screener_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("news", news_node)
    graph.add_node("valuation", valuation_node)
    graph.add_node("risk", risk_node)
    graph.add_node("join_gate", join_gate_node)
    def noop_node(state: PipelineState) -> PipelineState:
        return state

    graph.add_node("llm_strategy", llm_strategy_node)
    graph.add_node("llm_narrative", llm_narrative_node)
    graph.add_node("llm_tool_agent", llm_tool_node)
    graph.add_node("llm_join", llm_join_node)
    # fanout 觸發器，避免 join_gate 因多來源重複觸發三個 LLM 節點
    def llm_fanout_node(state: PipelineState) -> PipelineState:
        return {}
    graph.add_node("llm_fanout", llm_fanout_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("noop", noop_node)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "screener")
    # Fan-out after screener: run analyst and news in parallel
    graph.add_edge("screener", "analyst")
    graph.add_edge("screener", "news")
    # Fundamentals path
    graph.add_edge("analyst", "valuation")
    graph.add_edge("valuation", "risk")
    # Fan-in gate fed by risk and news
    graph.add_edge("risk", "join_gate")
    graph.add_edge("news", "join_gate")
    # 當 join ready 才觸發 fanout，一次性分派三個 LLM 節點
    try:
        graph.add_conditional_edges(
            "join_gate",
            _join_ready,
            {"ready": "llm_fanout", "wait": "noop"},
        )
    except Exception:
        graph.add_edge("join_gate", "llm_fanout")
    # 並行執行三個 LLM 節點（由 fanout 觸發，避免 join_gate 被多次書寫觸發）
    graph.add_edge("llm_fanout", "llm_strategy")
    graph.add_edge("llm_fanout", "llm_narrative")
    graph.add_edge("llm_fanout", "llm_tool_agent")
    # 匯流節點
    graph.add_edge("llm_strategy", "llm_join")
    graph.add_edge("llm_narrative", "llm_join")
    graph.add_edge("llm_tool_agent", "llm_join")
    try:
        graph.add_conditional_edges(
            "llm_join",
            _llm_ready,
            {"ready": "reporter", "wait": "noop"},
        )
    except Exception:
        # fallback: 直接連到 reporter（可能多次觸發）
        graph.add_edge("llm_join", "reporter")
    graph.add_edge("reporter", END)

    app = graph.compile()

    initial_state: PipelineState = {"params": params}
    final_state = app.invoke(initial_state)
    report_path = final_state.get("report_path")
    if not report_path:
        raise RuntimeError("Pipeline did not produce a report path")
    return Path(report_path)

"""Markdown Reporter: 將聚合輸出序列化為 Markdown 報告。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class MarkdownReporterAgent:
    """將多代理結果輸出為 Markdown 檔案。"""

    def __init__(self, reports_dir: Optional[str] = None) -> None:
        default_dir = reports_dir or Path.cwd() / "reports"
        self.reports_dir = Path(default_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _info_summary(info: Dict) -> str:
        profile = info.get("profile") if isinstance(info, dict) else None
        if isinstance(profile, dict):
            summary = profile.get("summary") or profile.get("longBusinessSummary")
            if summary:
                return summary
        return "Summary unavailable."

    @staticmethod
    def _economic_moat(metrics: Dict) -> str:
        moat_signals = []
        roic = metrics.get("roic") if metrics else None
        if roic is not None:
            moat_signals.append(f"ROIC: {roic:.1%}")
        gm = metrics.get("gross_margin") if metrics else None
        if gm is not None:
            moat_signals.append(f"Gross Margin: {gm:.1%}")
        om = metrics.get("operating_margin") if metrics else None
        if om is not None:
            moat_signals.append(f"Operating Margin: {om:.1%}")
        if not moat_signals:
            return "No moat indicators available."
        return " | ".join(moat_signals)

    @staticmethod
    def _financial_table(metrics: Dict) -> str:
        rows = [
            ("ROIC", metrics.get("roic")),
            ("Gross Margin", metrics.get("gross_margin")),
            ("Operating Margin", metrics.get("operating_margin")),
            ("FCF CAGR", metrics.get("fcf_cagr")),
            ("Debt/FCF", metrics.get("debt_to_fcf")),
        ]
        md = ["| Metric | Value |", "|:------|------:|"]
        for label, value in rows:
            if value is None:
                formatted = "NA"
            elif label == "Debt/FCF":
                formatted = f"{value:.2f}x"
            else:
                formatted = f"{value:.1%}"
            md.append(f"| {label} | {formatted} |")
        return "\n".join(md)

    @staticmethod
    def _valuation_section(valuation: Dict) -> str:
        mos = valuation.get("margin_of_safety")
        intrinsic = valuation.get("intrinsic_value_range", {})
        low = intrinsic.get("low")
        mid = intrinsic.get("mid")
        high = intrinsic.get("high")
        price = valuation.get("price")
        lines = ["- Current price: ${:.2f}".format(price) if price else "- Current price: NA"]
        if mid:
            lines.append("- Intrinsic value (midpoint): ${:.2f}".format(mid))
            lines.append("- Range: ${:.2f} – ${:.2f}".format(low or mid, high or mid))
        else:
            lines.append("- Intrinsic value unavailable")
        if mos is not None:
            lines.append("- Margin of safety: {:.1%}".format(mos))
        return "\n".join(lines)

    @staticmethod
    def _risk_section(risk_entry: Dict) -> str:
        flags = risk_entry.get("flags", [])
        lines = []
        if flags:
            lines.append("- Risk flags: " + ", ".join(flags))
        else:
            lines.append("- Risk flags: None identified")
        weight = risk_entry.get("position_weight")
        lines.append("- Suggested position weight: {:.0%}".format(weight) if weight else "- Suggested position weight: 0%")
        decision = "✅ Accumulate" if risk_entry.get("allowed") else "❌ Pass"
        lines.append(f"- Decision: {decision}")
        return "\n".join(lines)

    @staticmethod
    def _news_section(news_entry: Dict, window_days: int) -> str:
        bullets = news_entry.get("bullets") or ["No material items detected."]
        timeline = news_entry.get("timeline") or []
        sentiment = news_entry.get("sentiment")
        topics = news_entry.get("topics") or []
        sources = news_entry.get("sources") or []

        bullet_md = "\n".join(f"- {point}" for point in bullets)
        timeline_md = "\n".join(
            f"- {item['date']} — {item['summary']} ([source]({item['url']}))"
            for item in timeline if item.get("date") and item.get("summary") and item.get("url")
        ) or "- Timeline unavailable"
        sources_md = "\n".join(f"- [{src['source']}]({src['url']})" for src in sources if src.get("url")) or "- Sources unavailable"
        sentiment_line = f"Sentiment score: {sentiment:.2f}" if sentiment is not None else "Sentiment score: NA"
        topics_line = "Topics: " + ", ".join(topics) if topics else "Topics: NA"

        section = f"## News & Text Intelligence (last {window_days} days)\n{bullet_md}\n\n### Timeline\n{timeline_md}\n\n{sentiment_line}\n\n{topics_line}\n\n### Source List\n{sources_md}"
        return section

    def _compose(self, ticker: str, info: Dict, metrics: Dict, valuation: Dict, risk_entry: Dict, news_entry: Dict, window_days: int, llm_strategy: Dict | None = None, llm_narrative: Dict | None = None, llm_tool: Dict | None = None) -> str:
        content = [
            f"# {ticker} Research (Buffett Style)",
            "- Business summary & circle of competence",
            "- Economic moat evidence",
            "- Key financial table",
            "- Intrinsic valuation & margin of safety",
            "- Risk factors",
            "- ✅ Decision & sizing",
            "",
            "## Business Summary",
            self._info_summary(info),
            "",
            "## Economic Moat",
            self._economic_moat(metrics),
            "",
            "## Key Financials",
            self._financial_table(metrics or {}),
            "",
            "## Intrinsic Valuation",
            self._valuation_section(valuation or {}),
            "",
            "## Risk Factors",
            self._risk_section(risk_entry or {}),
            "",
            self._news_section(news_entry or {}, window_days),
        ]
        if llm_strategy and llm_strategy.get("strategy_comment"):
            content += [
                "",
                "## LLM Strategy",
                llm_strategy.get("strategy_comment", ""),
            ]
        if llm_narrative and llm_narrative.get("narrative"):
            content += [
                "",
                "## LLM Narrative",
                llm_narrative.get("narrative", ""),
            ]
        if llm_tool and llm_tool.get("tool_summary"):
            content += [
                "",
                "## LLM Tool Agent",
                llm_tool.get("tool_summary", ""),
            ]
        return "\n".join(content)

    def _write_report(self, ticker: str, content: str) -> Path:
        stamp = datetime.utcnow().strftime("%Y%m%d")
        path = self.reports_dir / f"{stamp}_{ticker.upper()}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def run(self, state: Dict) -> Path:
        fundamentals = state.get("fundamentals", [])
        valuations = {item.get("ticker"): item for item in state.get("valuation", [])}
        risks = {item.get("ticker"): item for item in state.get("risk", [])}
        news_bundle = {item.get("ticker"): item for item in state.get("news_bundle", [])}
        llm_strategy_map = {item.get("ticker"): item for item in state.get("llm_strategy", [])}
        llm_narrative_map = {item.get("ticker"): item for item in state.get("llm_narrative", [])}
        llm_tool_map = {item.get("ticker"): item for item in state.get("llm_tool_agent", [])}
        params = state.get("params", {})
        window_days = params.get("news_window_days", 14)

        if fundamentals:
            iterable = fundamentals
        else:
            fallback_candidates = state.get("candidates") or []
            iterable = [
                {"ticker": t, "info": {}, "metrics": {}} for t in fallback_candidates
            ]
        last_path: Optional[Path] = None
        for item in iterable:
            ticker = item.get("ticker")
            content = self._compose(
                ticker=ticker,
                info=item.get("info", {}),
                metrics=item.get("metrics", {}),
                valuation=valuations.get(ticker, {}),
                risk_entry=risks.get(ticker, {}),
                news_entry=news_bundle.get(ticker, {}),
                window_days=window_days,
                llm_strategy=llm_strategy_map.get(ticker),
                llm_narrative=llm_narrative_map.get(ticker),
                llm_tool=llm_tool_map.get(ticker),
            )
            last_path = self._write_report(ticker, content)
        if last_path is None:
            raise RuntimeError("Reporter produced no output (no candidates or fundamentals)")
        state["report_path"] = str(last_path)
        return last_path

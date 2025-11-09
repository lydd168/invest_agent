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
    def _trim_sentences(text: str, max_sentences: int = 2, max_chars: int = 600) -> str:
        if not text:
            return text
        seps = [". ", "。", "! ", "？", "? "]
        # naive sentence split
        parts = [text]
        for sep in seps:
            tmp = []
            for p in parts:
                tmp.extend(p.split(sep))
            parts = tmp
        parts = [p.strip() for p in parts if p.strip()]
        trimmed = ". ".join(parts[:max_sentences])
        if len(trimmed) > max_chars:
            trimmed = trimmed[: max_chars - 1] + "…"
        return trimmed

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
    def _snapshot_table(price: float | None, intrinsic_mid: float | None, mos: float | None, metrics: Dict, risk_flags: List[str], sentiment: float | None) -> str:
        def fmt_usd(v):
            return f"${v:,.2f}" if v is not None else "NA"
        def fmt_pct(v):
            return f"{v*100:.1f}%" if v is not None else "NA"
        rows = [
            ("Price", fmt_usd(price)),
            ("Intrinsic (mid)", fmt_usd(intrinsic_mid)),
            ("MOS", fmt_pct(mos)),
            ("ROIC", fmt_pct(metrics.get("roic"))),
            ("Gross Margin", fmt_pct(metrics.get("gross_margin"))),
            ("Operating Margin", fmt_pct(metrics.get("operating_margin"))),
            ("Risk Flags", ", ".join(risk_flags) if risk_flags else "None"),
            ("Sentiment", f"{sentiment:.2f}" if sentiment is not None else "NA"),
        ]
        md = ["| Item | Value |", "|:-----|------:|"]
        for k, v in rows:
            md.append(f"| {k} | {v} |")
        return "\n".join(md)

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
        max_bullets = 5
        shown = bullets[:max_bullets]
        timeline = news_entry.get("timeline") or []
        sentiment = news_entry.get("sentiment")
        topics = news_entry.get("topics") or []
        sources = news_entry.get("sources") or []
        total = news_entry.get("item_count") or len(bullets)

        bullet_md = "\n".join(f"- {point}" for point in shown)
        if total > len(shown):
            bullet_md += f"\n- … and {total - len(shown)} more"
        timeline_md = "\n".join(
            f"- {item['date']} — {item['summary']} ([source]({item['url']}))"
            for item in timeline if item.get("date") and item.get("summary") and item.get("url")
        ) or "- Timeline unavailable"
        sources_md = "\n".join(f"- [{src['source']}]({src['url']})" for src in sources if src.get("url")) or "- Sources unavailable"
        sentiment_line = f"Sentiment score: {sentiment:.2f}" if sentiment is not None else "Sentiment score: NA"
        topics_line = "Topics: " + ", ".join(topics) if topics else "Topics: NA"

        section = f"## News & Text Intelligence (last {window_days} days)\n{bullet_md}\n\n### Timeline\n{timeline_md}\n\n{sentiment_line}\n\n{topics_line}\n\n### Source List\n{sources_md}"
        return section

    def _compose(self, ticker: str, info: Dict, metrics: Dict, valuation: Dict, risk_entry: Dict, news_entry: Dict, window_days: int) -> str:
        # derive key numbers
        intrinsic = (valuation or {}).get("intrinsic_value_range", {})
        price = (valuation or {}).get("price")
        mid = intrinsic.get("mid")
        mos = (valuation or {}).get("margin_of_safety")
        flags = (risk_entry or {}).get("flags", [])
        allowed = bool((risk_entry or {}).get("allowed"))
        position_weight = (risk_entry or {}).get("position_weight") or 0.0
        verdict = "✅ Accumulate" if allowed and (mos or 0) > 0 else "❌ Pass"
        sentiment = (news_entry or {}).get("sentiment")

        # trimmed summary for readability
        raw_summary = self._info_summary(info)
        summary_text = self._trim_sentences(raw_summary, max_sentences=2, max_chars=600)

        price_str = f"{price:.2f}" if price is not None else "NA"
        mid_str = f"{mid:.2f}" if mid is not None else "NA"
        sent_str = f"{sentiment:.2f}" if sentiment is not None else "NA"

        content = [
            f"# {ticker} Research (Buffett Style)",
            "- Business summary & circle of competence",
            "- Economic moat evidence",
            "- Key financial table",
            "- Intrinsic valuation & margin of safety",
            "- Risk factors",
            "- ✅ Decision & sizing",
            "",
            "## Decision Box",
            (
                f"> Verdict: {verdict} | Position: {position_weight:.0%} | MOS: {mos*100:.1f}%"
                if mos is not None
                else f"> Verdict: {verdict} | Position: {position_weight:.0%}"
            ),
            f"> Rationale: price {price_str} vs intrinsic mid {mid_str}; risk flags: {', '.join(flags) if flags else 'None'}; sentiment: {sent_str}",
            "",
            "## Executive Summary",
            f"- Verdict: {verdict} | Position: {position_weight:.0%} | MOS: {mos*100:.1f}%" if mos is not None else f"- Verdict: {verdict} | Position: {position_weight:.0%}",
            f"- Rationale: price {price_str} vs intrinsic mid {mid_str}; risk flags: {', '.join(flags) if flags else 'None'}; sentiment: {sent_str}",
            "",
            "### Snapshot",
            self._snapshot_table(price, mid, mos, metrics or {}, flags, sentiment),
            "",
            "## Business Summary",
            summary_text,
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
    # SummaryAgent insight 於 run() 階段注入
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
        summary_map = {item.get("ticker"): item for item in state.get("summary_insight", [])}
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
            )
            # Inject Summary Insight block
            summary_entry = summary_map.get(ticker)
            if summary_entry and summary_entry.get("summary"):
                content += "\n\n## Summary Insight\n" + summary_entry.get("summary", "")
            last_path = self._write_report(ticker, content)
        if last_path is None:
            raise RuntimeError("Reporter produced no output (no candidates or fundamentals)")
        state["report_path"] = str(last_path)
        return last_path

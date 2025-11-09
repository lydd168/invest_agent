"""News Intelligence: 近訊彙整、情緒與主題標註、關鍵事件時間軸。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from tools import yfinance_client

from nlp import news_pipeline


class NewsIntelligenceAgent:
    """聚合並蒸餾新聞，輸出可執行洞見。"""

    def __init__(self, window_days: int = 14, max_news: int = 30) -> None:
        self.window_days = window_days
        self.max_news = max_news
        self.news_tool = yfinance_client.get_ticker_news
        self.search_tool = yfinance_client.search

    def _collect(self, ticker: str, query: Optional[str]) -> List[Dict]:
        stories: List[Dict] = []
        primary = self.news_tool(symbol=ticker, max_items=self.max_news)
        if primary.ok and isinstance(primary.data, list):
            stories.extend(primary.data)

        if query:
            secondary = self.search_tool(query=query, search_type="news", max_items=self.max_news)
            if secondary.ok and isinstance(secondary.data, list):
                stories.extend(secondary.data)

        return stories

    def analyse(self, ticker: str, query: Optional[str]) -> Dict:
        raw_items = self._collect(ticker, query)
        normalized = [news_pipeline.normalize_title(item) for item in raw_items]
        deduped = news_pipeline.dedup_news(normalized)
        filtered = news_pipeline.filter_by_window(deduped, self.window_days)
        top_items = filtered[: self.max_news]

        bullets = news_pipeline.summarize_items(top_items)
        sentiment = news_pipeline.sentiment(top_items)
        topics = news_pipeline.tag_topics(top_items)
        timeline = news_pipeline.build_timeline(top_items)
        sources = news_pipeline.build_sources_list(top_items)

        return {
            "ticker": ticker,
            "fetched_at": datetime.utcnow().isoformat(),
            "item_count": len(top_items),
            "bullets": bullets,
            "sentiment": sentiment,
            "topics": topics,
            "timeline": timeline,
            "sources": sources,
            "raw_items": top_items,
        }

    def run(self, state: Dict) -> Dict:
        params = state.get("params", {})
        query = params.get("query")
        ticker_data = []
        for ticker in state.get("candidates", []):
            ticker_data.append(self.analyse(ticker, query))
        state["news_bundle"] = ticker_data
        return state

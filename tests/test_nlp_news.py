"""Unit tests for news NLP utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from nlp import news_pipeline


def _make_item(title: str, content: str, days_ago: int = 1, source: str = "Source", url: str = "https://example.com") -> dict:
    published = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "title": title,
        "content": content,
        "source": source,
        "url": url,
        "published_at": published,
    }


def test_deduplication_removes_similar_titles():
    items = [
        _make_item("Apple beats estimates", "Great quarter"),
        _make_item("Apple beats estimates!", "Repeat"),
        _make_item("Microsoft guides higher", "Positive outlook", days_ago=2),
    ]
    deduped = news_pipeline.dedup_news(items)
    assert len(deduped) == 2


def test_summarize_items_guarantees_minimum_bullets():
    items = [_make_item("Headline", "Content sentence one. Second sentence."), _make_item("Another", "")]
    bullets = news_pipeline.summarize_items(items)
    assert len(bullets) >= 3


def test_sentiment_balances_positive_and_negative_terms():
    items = [
        _make_item("Company raises guidance", "Strong growth and raised outlook"),
        _make_item("Company faces lawsuit", "Weak demand and lawsuit filed"),
    ]
    sentiment = news_pipeline.sentiment(items)
    assert sentiment is not None
    assert -1.0 <= sentiment <= 1.0


def test_topic_tagging_identifies_keywords():
    items = [_make_item("Quarterly earnings released", "The company reported strong earnings guidance"), _make_item("Announces buyback", "Share repurchase program")] 
    tags = news_pipeline.tag_topics(items)
    assert "earnings" in tags
    assert "guidance" in tags or "buyback" in tags

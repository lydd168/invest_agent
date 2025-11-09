"""Tests for yfinance news tool wrappers."""

from __future__ import annotations

import pytest

yf = pytest.importorskip("yfinance")

from tools import yfinance_client


class _Ticker:
    def __init__(self, payload):
        self.news = payload


def test_get_ticker_news_success(monkeypatch):
    payload = [
        {
            "title": "Apple launches new product",
            "summary": "Highlights from launch",
            "publisher": "NewsWire",
            "url": "https://example.com/aapl",
            "datetime": "2025-11-01T12:00:00Z",
        }
    ]

    monkeypatch.setattr(yf, "Ticker", lambda symbol: _Ticker(payload))

    response = yfinance_client.get_ticker_news(symbol="AAPL", max_items=5)
    assert response.ok is True
    assert len(response.data) == 1
    news_item = response.data[0]
    assert news_item["title"] == "Apple launches new product"
    assert news_item["symbol"] == "AAPL"
    assert news_item["published_at"].startswith("2025-11-01")


def test_get_ticker_news_timeout(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(yf, "Ticker", _raise)

    response = yfinance_client.get_ticker_news(symbol="MSFT")
    assert response.ok is False
    assert response.error is not None
    assert response.error.type == "RuntimeError"

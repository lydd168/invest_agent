"""End-to-end pipeline smoke test with mocked tool responses."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from graph.orchestrator import run_pipeline
from tools.yfinance_client import ToolMeta, ToolResponse


@pytest.fixture(autouse=True)
def mock_tools(monkeypatch):
    timestamp = datetime.utcnow().isoformat()

    def _response(tool: str, data, symbol: str | None = None, ok: bool = True):
        return ToolResponse(ok=ok, data=data, meta=ToolMeta(tool=tool, symbol=symbol, fetched_at=timestamp), error=None)

    monkeypatch.setattr(
    "tools.yfinance_client.search",
        lambda **kwargs: _response("search", data=[{"symbol": "AAPL"}]),
    )

    monkeypatch.setattr(
    "tools.yfinance_client.get_top",
        lambda **kwargs: _response("get_top", data=[{"symbol": "AAPL"}]),
    )

    info_payload = {
        "profile": {"summary": "Designs consumer electronics."},
        "financials": {
            "grossMargins": 0.4,
            "operatingMargins": 0.25,
            "totalRevenue": 100000,
            "operatingIncome": 25000,
        },
        "cashflow": {"freeCashFlows": [60000, 65000, 70000]},
        "balance_sheet": {"totalDebt": 50000},
        "metrics": {
            "returnOnInvestedCapital": 0.18,
            "freeCashflow": 70000,
            "sharesOutstanding": 16000000000,
            "eps": 6.0,
        },
    }

    monkeypatch.setattr(
    "tools.yfinance_client.get_ticker_info",
        lambda **kwargs: _response("get_ticker_info", data=info_payload, symbol=kwargs.get("symbol")),
    )

    price_history = [
        {"date": "2025-10-01", "close": 170.0},
        {"date": "2025-10-08", "close": 172.0},
    ]

    monkeypatch.setattr(
    "tools.yfinance_client.get_price_history",
        lambda **kwargs: _response("get_price_history", data=price_history, symbol=kwargs.get("symbol")),
    )

    news_payload = [
        {
            "title": "Apple raises guidance",
            "content": "Company raised outlook on strong demand",
            "source": "Newswire",
            "url": "https://example.com/news",
            "published_at": datetime.utcnow().isoformat(),
        }
    ]

    monkeypatch.setattr(
    "tools.yfinance_client.get_ticker_news",
        lambda **kwargs: _response("get_ticker_news", data=news_payload, symbol=kwargs.get("symbol")),
    )

    yield


def test_pipeline_generates_report(tmp_path: Path):
    output = run_pipeline(
        {
            "tickers": ["AAPL"],
            "news_window_days": 7,
            "max_news": 5,
            "reports_dir": str(tmp_path),
        }
    )
    assert output.exists()
    content = output.read_text()
    assert "# AAPL Research" in content
    assert "Intrinsic value" in content
    assert "News & Text Intelligence" in content

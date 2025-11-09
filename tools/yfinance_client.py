"""Direct yfinance-powered tool wrappers replacing the MCP dependency."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple

import requests
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool, StructuredTool

try:  # LangGraph <= 0.0.66 style import
    from langgraph.prebuilt import ToolNode  # type: ignore
except ImportError:  # LangGraph >= 0.1.0 relocated ToolNode
    try:
        from langgraph.prebuilt.tool_node import ToolNode  # type: ignore
    except ImportError:  # pragma: no cover - environment specific
        ToolNode = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from langgraph.prebuilt import ToolNode as ToolNodeType  # type: ignore
else:  # pragma: no cover - runtime fallback
    ToolNodeType = Any

logger = logging.getLogger(__name__)

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
SCREENER_URL = "https://query2.finance.yahoo.com/ws/screeners/v1/finance/screener/predefined/saved"


def _load_yf():
    try:
        import yfinance as yf  # type: ignore

        return yf
    except ModuleNotFoundError as exc:  # pragma: no cover - configuration issue
        raise RuntimeError("yfinance package is required. Install it via 'pip install yfinance'.") from exc


class ToolError(BaseModel):
    type: str = Field(..., description="Categorised error type")
    message: str = Field(..., description="Human-readable explanation")


class ToolMeta(BaseModel):
    tool: str
    symbol: Optional[str] = None
    fetched_at: str


class ToolResponse(BaseModel):
    ok: bool
    data: Any
    meta: ToolMeta
    error: Optional[ToolError] = None


class SearchInput(BaseModel):
    query: str
    search_type: Literal["all", "quotes", "news"] = "all"
    max_items: int = Field(default=25, gt=0, le=100)


class GetTopInput(BaseModel):
    sector: Optional[str] = None
    top_type: Literal[
        "top_etfs",
        "top_mutual_funds",
        "top_companies",
        "top_growth_companies",
        "top_performing_companies",
    ] = "top_companies"
    top_n: int = Field(default=10, gt=0, le=50)


class TickerInfoInput(BaseModel):
    symbol: str


class PriceHistoryInput(BaseModel):
    symbol: str
    period: Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"] = "6mo"
    interval: Literal[
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    ] = "1d"


class NewsInput(BaseModel):
    symbol: Optional[str] = None
    query: Optional[str] = None
    max_items: int = Field(default=30, gt=0, le=100)


def _meta(tool: str, symbol: Optional[str] = None) -> ToolMeta:
    return ToolMeta(tool=tool, symbol=symbol, fetched_at=datetime.now(timezone.utc).isoformat())


def _ok(tool: str, data: Any, symbol: Optional[str] = None) -> ToolResponse:
    return ToolResponse(ok=True, data=data, meta=_meta(tool, symbol), error=None)


def _fail(tool: str, exc: Exception, symbol: Optional[str] = None) -> ToolResponse:
    logger.exception("yfinance tool %s failed", tool)
    return ToolResponse(
        ok=False,
        data=None,
        meta=_meta(tool, symbol),
        error=ToolError(type=exc.__class__.__name__, message=str(exc)),
    )


def _search_via_http(query: str, max_items: int) -> List[Dict[str, Any]]:
    params = {"q": query, "quotesCount": max_items, "newsCount": 0}
    response = requests.get(SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    quotes = payload.get("quotes", []) if isinstance(payload, dict) else []
    return quotes[:max_items]


def _run_yfinance_search(query: str, max_quotes: int, max_news: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    yf = _load_yf()
    search_cls = getattr(yf, "Search", None)
    if search_cls is None:
        raise AttributeError("yfinance.Search class is unavailable")

    search_instance = search_cls(
        query,
        max_results=max(max_quotes, 1),
        news_count=max_news,
        lists_count=0,
        include_cb=False,
        include_nav_links=False,
        include_research=False,
        include_cultural_assets=False,
        enable_fuzzy_query=True,
        recommended=max(max_quotes, max_news, 1),
        timeout=15,
        raise_errors=False,
    )
    try:
        search_instance.search()
    except Exception as exc:  # pragma: no cover - network edge cases
        logger.debug("yfinance Search.search raised %s", exc, exc_info=True)

    quotes = list(getattr(search_instance, "quotes", []) or [])
    news = list(getattr(search_instance, "news", []) or [])
    return quotes[:max_quotes] if max_quotes else [], news[:max_news] if max_news else []


def search(**kwargs: Any) -> ToolResponse:
    try:
        payload = SearchInput.model_validate(kwargs)
        quotes: List[Dict[str, Any]] = []
        news_items: List[Dict[str, Any]] = []

        try:
            quotes, news_items = _run_yfinance_search(
                payload.query,
                payload.max_items if payload.search_type in {"all", "quotes"} else 0,
                payload.max_items if payload.search_type in {"all", "news"} else 0,
            )
        except AttributeError:
            yf = _load_yf()
            legacy_search = getattr(yf, "search", None)
            if callable(legacy_search):
                result = legacy_search(payload.query)
                if isinstance(result, dict):
                    quotes = list(result.get("quotes", []) or [])
                    news_items = list(result.get("news", []) or [])
            if not quotes and payload.search_type in {"all", "quotes"}:
                quotes = _search_via_http(payload.query, payload.max_items)
        except Exception:  # pragma: no cover - network edge cases
            if payload.search_type in {"all", "quotes"}:
                quotes = _search_via_http(payload.query, payload.max_items)

        if payload.search_type == "news":
            data: List[Dict[str, Any]] = [
                _standardize_news_item(item, item.get("symbol"))
                for item in news_items[: payload.max_items]
                if isinstance(item, dict)
            ]
        else:
            data = []
            for quote in quotes[: payload.max_items]:
                if not isinstance(quote, dict):
                    continue
                data.append(
                    {
                        "symbol": quote.get("symbol"),
                        "shortName": quote.get("shortname") or quote.get("longname"),
                        "exchange": quote.get("exchange"),
                        "sector": quote.get("sector"),
                    }
                )
        return _ok("search", data)
    except Exception as exc:  # pragma: no cover - network edge cases
        return _fail("search", exc)


_SCREENER_MAP = {
    "top_companies": "most_actives",
    "top_growth_companies": "top_growth_stocks",
    "top_performing_companies": "day_gainers",
    "top_etfs": "etf_most_actives",
    "top_mutual_funds": "mutualfunds_most_actives",
}


def _fetch_screener(scr_id: str, count: int) -> List[Dict[str, Any]]:
    payload = {"scrIds": scr_id, "count": count}
    response = requests.post(SCREENER_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    finance = data.get("finance", {}) if isinstance(data, dict) else {}
    result = finance.get("result") or []
    if result and isinstance(result[0], dict):
        return result[0].get("quotes", []) or []
    return []


def get_top(**kwargs: Any) -> ToolResponse:
    try:
        payload = GetTopInput.model_validate(kwargs)
        scr_id = _SCREENER_MAP.get(payload.top_type)
        if not scr_id:
            raise ValueError(f"Unsupported top_type: {payload.top_type}")
        quotes = _fetch_screener(scr_id, payload.top_n)
        data: List[Dict[str, Any]] = []
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            if payload.sector and quote.get("sector") and quote.get("sector") != payload.sector:
                continue
            data.append(
                {
                    "symbol": quote.get("symbol"),
                    "shortName": quote.get("shortName"),
                    "sector": quote.get("sector"),
                    "industry": quote.get("industry"),
                }
            )
        return _ok("get_top", data)
    except Exception as exc:  # pragma: no cover - network edge cases
        return _fail("get_top", exc)


def _extract_row(df, candidates: List[str]) -> List[float]:
    if df is None or df.empty:
        return []
    for name in candidates:
        if name in df.index:
            series = df.loc[name]
            values = [float(value) for value in series.dropna().tolist()]
            return values
    return []


def get_ticker_info(**kwargs: Any) -> ToolResponse:
    try:
        payload = TickerInfoInput.model_validate(kwargs)
        yf = _load_yf()
        ticker = yf.Ticker(payload.symbol)
        info = ticker.info if isinstance(ticker.info, dict) else {}

        cashflow_series = _extract_row(
            ticker.cashflow,
            ["Free Cash Flow", "FreeCashFlow"],
        )
        balance_sheet = ticker.balance_sheet
        total_debt_series = _extract_row(balance_sheet, ["Total Debt", "TotalDebt"])
        total_debt = total_debt_series[-1] if total_debt_series else None

        data = {
            "profile": {
                "summary": info.get("longBusinessSummary"),
            },
            "financials": {
                "grossMargins": info.get("grossMargins"),
                "operatingMargins": info.get("operatingMargins"),
                "totalRevenue": info.get("totalRevenue"),
                "operatingIncome": info.get("operatingIncome"),
            },
            "cashflow": {
                "freeCashFlows": cashflow_series,
            },
            "balance_sheet": {
                "totalDebt": total_debt,
            },
            "metrics": {
                "returnOnInvestedCapital": info.get("returnOnAssets"),
                "returnOnCapitalEmployed": info.get("returnOnEquity"),
                "freeCashflow": cashflow_series[-1] if cashflow_series else None,
                "sharesOutstanding": info.get("sharesOutstanding"),
                "eps": info.get("trailingEps") or info.get("forwardEps"),
                "totalDebt": total_debt,
            },
        }
        return _ok("get_ticker_info", data, payload.symbol)
    except Exception as exc:
        return _fail("get_ticker_info", exc, kwargs.get("symbol"))


def get_price_history(**kwargs: Any) -> ToolResponse:
    try:
        payload = PriceHistoryInput.model_validate(kwargs)
        yf = _load_yf()
        ticker = yf.Ticker(payload.symbol)
        history = ticker.history(period=payload.period, interval=payload.interval)
        rows: List[Dict[str, Any]] = []
        if history is not None and not history.empty:
            history = history.reset_index()
            for _, row in history.iterrows():
                date_value = row.get("Date") or row.get("Datetime")
                rows.append(
                    {
                        "date": date_value.isoformat() if hasattr(date_value, "isoformat") else date_value,
                        "open": row.get("Open"),
                        "high": row.get("High"),
                        "low": row.get("Low"),
                        "close": row.get("Close"),
                        "volume": row.get("Volume"),
                    }
                )
        return _ok("get_price_history", rows, payload.symbol)
    except Exception as exc:
        return _fail("get_price_history", exc, kwargs.get("symbol"))


def _standardize_news_item(item: Dict[str, Any], symbol: Optional[str]) -> Dict[str, Any]:
    content = item
    if "content" in item and isinstance(item["content"], dict):
        content = item["content"]
        symbol = symbol or item.get("symbol")
        if not symbol:
            related = item.get("relatedTickers") or content.get("relatedTickers")
            if isinstance(related, list) and related:
                symbol = related[0]
    published = (
        content.get("providerPublishTime")
        or content.get("pubDate")
        or item.get("providerPublishTime")
        or item.get("pubDate")
        or item.get("published_at")
    )
    if isinstance(published, (int, float)):
        published_iso = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
    else:
        published_iso = published
    provider = content.get("publisher") or content.get("provider") or item.get("provider")
    if isinstance(provider, dict):
        provider = provider.get("displayName") or provider.get("name")
    title = content.get("title") or item.get("title")
    summary = (
        content.get("summary")
        or content.get("description")
        or item.get("summary")
        or item.get("description")
    )
    url = (
        content.get("canonicalUrl", {}).get("url")
        if isinstance(content.get("canonicalUrl"), dict)
        else None
    ) or (
        content.get("clickThroughUrl", {}).get("url")
        if isinstance(content.get("clickThroughUrl"), dict)
        else None
    )
    if not url:
        url = item.get("link") or content.get("link") or item.get("url") or content.get("url")
    return {
        "title": title,
        "content": summary or content.get("content"),
        "source": provider,
        "url": url,
        "symbol": symbol or content.get("symbol"),
        "published_at": published_iso,
    }


def get_ticker_news(**kwargs: Any) -> ToolResponse:
    try:
        payload = NewsInput.model_validate(kwargs)
        symbol = payload.symbol or payload.query
        yf = _load_yf()

        items: List[Dict[str, Any]] = []
        if payload.symbol:
            ticker = yf.Ticker(payload.symbol)
            ticker_news = ticker.news or []
            if isinstance(ticker_news, list):
                items.extend(ticker_news)
        if payload.query:
            try:
                _, search_news = _run_yfinance_search(payload.query, 0, payload.max_items)
            except AttributeError:
                search_news = []
                legacy_search = getattr(yf, "search", None)
                if callable(legacy_search):
                    try:
                        search_payload = legacy_search(payload.query)
                        if isinstance(search_payload, dict):
                            search_news = list(search_payload.get("news", []) or [])
                    except Exception:  # pragma: no cover - network edge cases
                        search_news = []
            except Exception:  # pragma: no cover - network edge cases
                search_news = []
            if isinstance(search_news, list):
                items.extend(search_news)

        normalized = [
            _standardize_news_item(item, payload.symbol)
            for item in items[: payload.max_items]
            if isinstance(item, dict)
        ]
        return _ok("get_ticker_news", normalized, symbol)
    except Exception as exc:
        return _fail("get_ticker_news", exc, kwargs.get("symbol"))


def get_langchain_tools() -> List[BaseTool]:
    return [
        StructuredTool.from_function(
            name="search",
            description="Yahoo Finance search",
            func=lambda **tool_kwargs: search(**tool_kwargs).model_dump(),
            args_schema=SearchInput,
        ),
        StructuredTool.from_function(
            name="get_top",
            description="Yahoo Finance screener",
            func=lambda **tool_kwargs: get_top(**tool_kwargs).model_dump(),
            args_schema=GetTopInput,
        ),
        StructuredTool.from_function(
            name="get_ticker_info",
            description="Fetch ticker fundamentals",
            func=lambda **tool_kwargs: get_ticker_info(**tool_kwargs).model_dump(),
            args_schema=TickerInfoInput,
        ),
        StructuredTool.from_function(
            name="get_price_history",
            description="Fetch price history",
            func=lambda **tool_kwargs: get_price_history(**tool_kwargs).model_dump(),
            args_schema=PriceHistoryInput,
        ),
        StructuredTool.from_function(
            name="get_ticker_news",
            description="Fetch ticker news",
            func=lambda **tool_kwargs: get_ticker_news(**tool_kwargs).model_dump(),
            args_schema=NewsInput,
        ),
    ]


def as_toolnode() -> ToolNodeType:
    if ToolNode is None:
        raise RuntimeError(
            "LangGraph ToolNode is unavailable. Install a compatible langgraph version (>=0.0.65) "
            "or adjust tooling integrations."
        )
    return ToolNode(get_langchain_tools())


# Backwards-compatible aliases for legacy imports.
MCPToolError = ToolError
MCPToolMeta = ToolMeta
MCPToolResponse = ToolResponse

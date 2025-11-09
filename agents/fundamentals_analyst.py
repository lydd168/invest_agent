"""Fundamentals Analyst: 計算 Buffett 風格品質指標 (ROIC/邊際/FCF 等)。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from tools import yfinance_client


@dataclass
class TickerMetrics:
    ticker: str
    roic: Optional[float]
    gross_margin: Optional[float]
    operating_margin: Optional[float]
    fcf_cagr: Optional[float]
    debt_to_fcf: Optional[float]


def _calc_margin(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ZeroDivisionError, ValueError):
        return None


def _calc_cagr(series: Iterable[float]) -> Optional[float]:
    values = [float(x) for x in series if x is not None]
    if len(values) < 2:
        return None
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        return None
    periods = len(values) - 1
    try:
        return (end / start) ** (1 / periods) - 1
    except (ZeroDivisionError, ValueError):
        return None


def _extract_nested(payload: Dict, *path: str) -> Optional[float]:
    cursor: Dict = payload
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
        if cursor is None:
            return None
    if isinstance(cursor, (int, float)):
        return float(cursor)
    return None


def _sanitize_price_history(raw: List[Dict]) -> List[Dict]:
    sanitized = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        sanitized.append({
            "date": row.get("Date") or row.get("date"),
            "open": row.get("Open") or row.get("open"),
            "high": row.get("High") or row.get("high"),
            "low": row.get("Low") or row.get("low"),
            "close": row.get("Close") or row.get("close"),
            "volume": row.get("Volume") or row.get("volume"),
        })
    return sanitized


def _compute_metrics(ticker: str, info_payload: Dict, price_payload: Dict) -> Dict:
    info_data = info_payload.get("data") if info_payload.get("ok") else {}
    price_data = price_payload.get("data") if price_payload.get("ok") else []

    gross_margin = _extract_nested(info_data, "financials", "grossMargins")
    if gross_margin is None:
        gross_margin = _calc_margin(
            _extract_nested(info_data, "financials", "grossProfit"),
            _extract_nested(info_data, "financials", "totalRevenue"),
        )

    operating_margin = _extract_nested(info_data, "financials", "operatingMargins")
    if operating_margin is None:
        operating_margin = _calc_margin(
            _extract_nested(info_data, "financials", "operatingIncome"),
            _extract_nested(info_data, "financials", "totalRevenue"),
        )

    roic = (
        _extract_nested(info_data, "ratios", "roic")
        or _extract_nested(info_data, "metrics", "returnOnInvestedCapital")
        or _extract_nested(info_data, "metrics", "returnOnCapitalEmployed")
    )

    fcf_history = info_data.get("cashflow", {}).get("freeCashFlows", []) if isinstance(info_data, dict) else []
    fcf_cagr = _calc_cagr(fcf_history)

    latest_fcf = float(fcf_history[-1]) if fcf_history else None
    total_debt = _extract_nested(info_data, "balance_sheet", "totalDebt") or _extract_nested(info_data, "metrics", "totalDebt")
    debt_to_fcf = None
    if latest_fcf and latest_fcf != 0 and total_debt is not None:
        debt_to_fcf = float(total_debt) / latest_fcf

    metrics = TickerMetrics(
        ticker=ticker,
        roic=roic,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        fcf_cagr=fcf_cagr,
        debt_to_fcf=debt_to_fcf,
    )

    return {
        "ticker": ticker,
        "info": info_data,
        "price_history": _sanitize_price_history(price_data if isinstance(price_data, list) else []),
        "metrics": metrics.__dict__,
    }


class FundamentalsAnalystAgent:
    """抓取基本面與價格，產出 Buffett 指標彙整。"""

    def __init__(self) -> None:
        self.info_tool = yfinance_client.get_ticker_info
        self.history_tool = yfinance_client.get_price_history

    def analyze(self, tickers: Iterable[str]) -> List[Dict]:
        results: List[Dict] = []
        for ticker in tickers:
            info_response = self.info_tool(symbol=ticker)
            price_response = self.history_tool(symbol=ticker, period="1y", interval="1wk")
            results.append(_compute_metrics(ticker, info_response.model_dump(), price_response.model_dump()))
        return results

    def run(self, state: Dict) -> Dict:
        tickers = state.get("candidates", [])
        fundamentals = self.analyze(tickers)
        state["fundamentals"] = fundamentals
        return state

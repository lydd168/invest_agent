"""Candidate Screener: 依 sector / query / 種子清單彙整候選股票。"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from tools import yfinance_client


def _extract_symbols(response_payload: Dict) -> List[str]:
	if not response_payload or not response_payload.get("ok"):
		return []
	data = response_payload.get("data") or []
	symbols: Set[str] = set()
	if isinstance(data, list):
		for item in data:
			if isinstance(item, dict):
				symbol = (item.get("symbol") or item.get("ticker") or item.get("shortName"))
				if symbol:
					symbols.add(symbol.upper())
	return list(symbols)


class CandidateScreenerAgent:
	"""整合 Yahoo Finance 搜尋/排行，產生確定性的候選名單。"""

	def __init__(self) -> None:
		self.search_tool = yfinance_client.search
		self.top_tool = yfinance_client.get_top

	def shortlist(
		self,
		sector: Optional[str],
		query: Optional[str],
		seed_tickers: Optional[Iterable[str]],
	) -> List[str]:
		tickers: Set[str] = set()
		if seed_tickers:
			tickers.update(symbol.strip().upper() for symbol in seed_tickers if symbol)

		if query:
			response = self.search_tool(query=query, search_type="quotes", max_items=20)
			tickers.update(_extract_symbols(response.model_dump()))

		if sector:
			response = self.top_tool(sector=sector, top_type="top_companies", top_n=10)
			tickers.update(_extract_symbols(response.model_dump()))

		return sorted(tickers)

	def run(self, state: Dict) -> Dict:
		sector = state.get("params", {}).get("sector")
		query = state.get("params", {}).get("query")
		seed = state.get("params", {}).get("tickers")
		candidates = self.shortlist(sector, query, seed)
		if not candidates and seed:
			candidates = sorted({symbol.upper() for symbol in seed})
		state["candidates"] = candidates
		return state

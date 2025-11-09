"""Input Supervisor: 正規化輸入 tickers 與候選限制，準備初始 Universe。"""

from __future__ import annotations

from typing import Dict, List, Optional


class InputSupervisorAgent:
    """預處理輸入與候選上限，為 Screener 準備初始狀態。"""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _normalize_tickers(raw: List[str]) -> List[str]:
        norm: List[str] = []
        seen = set()
        for t in raw:
            if not t:
                continue
            u = t.strip().upper()
            if u and u not in seen:
                seen.add(u)
                norm.append(u)
        return norm

    def run(self, state: Dict) -> None:
        params: Dict = state.get("params", {})
        explicit = params.get("tickers") or []
        if isinstance(explicit, str):  # allow comma-separated
            explicit = [p.strip() for p in explicit.split(",") if p.strip()]
        if explicit:
            normalized = self._normalize_tickers(explicit)
            max_candidates: Optional[int] = params.get("max_candidates")
            if isinstance(max_candidates, int) and max_candidates > 0:
                normalized = normalized[:max_candidates]
            state["candidates"] = normalized
        else:
            if "candidates" not in state:
                state["candidates"] = []

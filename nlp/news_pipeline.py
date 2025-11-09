"""Utility functions for normalising and analysing news items."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from dateutil import parser as date_parser
from difflib import SequenceMatcher


_POSITIVE_WORDS = {"beat", "raised", "growth", "strong", "outperform"}
_NEGATIVE_WORDS = {"miss", "cut", "down", "lawsuit", "probe", "decline", "weak"}
_TOPIC_KEYWORDS = {
    "earnings": {"earnings", "eps", "profit", "quarter"},
    "guidance": {"guidance", "outlook", "forecast"},
    "buyback": {"buyback", "repurchase"},
    "litigation": {"lawsuit", "litigation", "settlement", "court"},
    "macro": {"inflation", "rates", "fed", "economy"},
}


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_title(item: Dict) -> Dict:
    title = item.get("title") or item.get("headline") or "Untitled"
    normalized = {
        "title": str(title).strip(),
        "content": item.get("content") or item.get("summary"),
        "source": item.get("source") or item.get("publisher"),
        "url": item.get("url") or item.get("link"),
        "symbol": item.get("symbol"),
        "published_at": item.get("published_at") or item.get("datetime"),
    }
    parsed_date = _parse_date(normalized["published_at"])
    if parsed_date:
        normalized["published_at"] = parsed_date.isoformat()
    else:
        normalized["published_at"] = None
    return normalized


def dedup_news(items: Iterable[Dict], similarity_threshold: float = 0.9) -> List[Dict]:
    seen: List[Dict] = []
    for item in items:
        title = item.get("title") or ""
        if not title:
            seen.append(item)
            continue
        is_duplicate = False
        for existing in seen:
            ratio = SequenceMatcher(None, title.lower(), (existing.get("title") or "").lower()).ratio()
            if ratio >= similarity_threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            seen.append(item)
    return seen


def filter_by_window(items: Iterable[Dict], days: int) -> List[Dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered: List[Dict] = []
    for item in items:
        published = _parse_date(item.get("published_at"))
        if published and published >= cutoff:
            filtered.append({**item, "published_at": published.isoformat()})
    return sorted(filtered, key=lambda x: x.get("published_at") or "", reverse=True)


def summarize_items(items: Iterable[Dict], min_items: int = 3, max_items: int = 6) -> List[str]:
    bullets: List[str] = []
    for item in items:
        title = item.get("title") or "Item"
        content = item.get("content") or ""
        headline = title
        if content:
            sentences = re.split(r"(?<=[.!?]) +", content)
            if sentences:
                headline = f"{title}: {sentences[0][:160]}".strip()
        bullets.append(headline)
        if len(bullets) >= max_items:
            break
    if len(bullets) < min_items:
        bullets.extend(["No additional material." for _ in range(min_items - len(bullets))])
    return bullets


def build_timeline(items: Iterable[Dict], limit: int = 10) -> List[Dict]:
    timeline: List[Dict] = []
    for item in items:
        published = item.get("published_at")
        if not published:
            continue
        timeline.append(
            {
                "date": published.split("T")[0],
                "summary": item.get("title") or "Untitled",
                "url": item.get("url"),
            }
        )
        if len(timeline) >= limit:
            break
    return timeline


def sentiment(items: Iterable[Dict]) -> Optional[float]:
    score = 0
    total = 0
    for item in items:
        text = " ".join(filter(None, [item.get("title"), item.get("content")])).lower()
        if not text:
            continue
        total += 1
        positive_hits = sum(1 for word in _POSITIVE_WORDS if word in text)
        negative_hits = sum(1 for word in _NEGATIVE_WORDS if word in text)
        score += positive_hits - negative_hits
    if total == 0:
        return None
    return max(-1.0, min(1.0, score / max(total, 1)))


def tag_topics(items: Iterable[Dict]) -> List[str]:
    topics: List[str] = []
    fragments: List[str] = []
    for item in items:
        title = item.get("title") or ""
        content = item.get("content") or ""
        fragments.append(title)
        fragments.append(content)
    text_blob = " ".join(fragment for fragment in fragments if fragment).lower()
    for label, keywords in _TOPIC_KEYWORDS.items():
        if any(keyword in text_blob for keyword in keywords):
            topics.append(label)
    return topics


def build_sources_list(items: Iterable[Dict]) -> List[Dict]:
    sources = []
    for item in items:
        url = item.get("url")
        source = item.get("source") or "Unknown"
        if url:
            sources.append({"source": source, "url": url})
    return sources

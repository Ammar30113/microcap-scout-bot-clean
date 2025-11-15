from __future__ import annotations

from typing import Dict, Iterable

import requests

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_POSITIVE_WORDS = {"beat", "record", "growth", "bullish", "upgrade", "surge", "momentum", "profit"}
_NEGATIVE_WORDS = {"miss", "weak", "downgrade", "lawsuit", "decline", "bearish", "loss", "fraud"}


def fetch_sentiment(symbol: str, *, lookback_days: int = 3) -> float:
    """Approximate sentiment via keyword heuristics on NewsAPI headlines."""

    if not settings.newsapi_key:
        return 0.0

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": symbol.upper(),
        "language": "en",
        "pageSize": 25,
        "sortBy": "publishedAt",
        "from": None,
    }
    headers = {"Authorization": settings.newsapi_key}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - network guard
        logger.warning("NewsAPI request failed for %s: %s", symbol, exc)
        return 0.0

    articles = response.json().get("articles", [])
    if not articles:
        return 0.0

    score = 0.0
    for article in articles:
        text = " ".join(
            filter(None, [article.get("title"), article.get("description"), article.get("content")])
        ).lower()
        score += _score_text(text)

    normalized = max(min(score / len(articles), 1.0), -1.0)
    return (normalized + 1.0) / 2.0  # map to 0-1


def _score_text(text: str) -> float:
    positive_hits = sum(text.count(word) for word in _POSITIVE_WORDS)
    negative_hits = sum(text.count(word) for word in _NEGATIVE_WORDS)
    total = positive_hits + negative_hits
    if total == 0:
        return 0.0
    return (positive_hits - negative_hits) / total

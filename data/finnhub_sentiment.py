from __future__ import annotations

from typing import Dict

import requests

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def fetch_sentiment(symbol: str) -> float:
    """Return Finnhub sentiment score for ``symbol`` (0-1 range)."""

    if not settings.finnhub_api_key:
        return 0.0

    url = "https://finnhub.io/api/v1/news-sentiment"
    params = {"symbol": symbol.upper(), "token": settings.finnhub_api_key}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - network guard
        logger.warning("Finnhub sentiment request failed for %s: %s", symbol, exc)
        return 0.0

    payload: Dict[str, float] = response.json()
    score = payload.get("companyNewsScore")
    if score is None:
        sentiment_blob = payload.get("sentiment") or {}
        score = sentiment_blob.get("companyNewsScore") or sentiment_blob.get("bullishPercent")
    if score is None:
        return 0.0
    return max(0.0, min(1.0, float(score)))

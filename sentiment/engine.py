from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from core.config import get_settings
from sentiment.gpt_provider import GPTProvider

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalize(score: float) -> float:
    try:
        val = float(score)
    except (TypeError, ValueError):
        return 0.0
    return max(min(val, 1.0), -1.0)


class SentimentEngine:
    def __init__(self) -> None:
        self.enabled = settings.use_sentiment
        self.cache_ttl = settings.sentiment_cache_ttl
        self.provider = GPTProvider()
        self._cache: Dict[str, Dict] = {}

    def _from_cache(self, symbol: str) -> Optional[Dict]:
        entry = self._cache.get(symbol.upper())
        if not entry:
            return None
        if time.time() - entry.get("timestamp", 0) > self.cache_ttl:
            return None
        return entry

    def _set_cache(self, symbol: str, payload: Dict) -> None:
        payload["timestamp"] = time.time()
        self._cache[symbol.upper()] = payload

    def _fetch_symbol(self, symbol: str) -> Dict:
        symbol_u = symbol.upper()
        res = self.provider.fetch_sentiment(symbol_u)
        score = _normalize(res.get("sentiment_score", 0.0))
        payload = {
            "symbol": symbol_u,
            "sentiment_score": score,
            "headlines": res.get("headlines") or [],
            "source": res.get("source", "gpt"),
        }
        logger.info("GPT sentiment for %s = %.4f", symbol_u, score)
        self._set_cache(symbol_u, payload)
        return payload

    def get_sentiment(self, symbol: str) -> Dict:
        if not self.enabled:
            return {"symbol": symbol.upper(), "sentiment_score": 0.0, "headlines": [], "source": "disabled"}

        cached = self._from_cache(symbol)
        if cached:
            return cached
        return self._fetch_symbol(symbol)

    def get_news(self, symbol: str) -> Dict:
        return self.get_sentiment(symbol)


_engine = SentimentEngine()


def get_sentiment(symbol: str) -> Dict:
    return _engine.get_sentiment(symbol)

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import requests

from config import get_settings
from market_data import get_aggregates
from utils.logger import get_logger

logger = get_logger("Sentiment")
settings = get_settings()

NEWS_WEIGHT = 0.4
ALPHA_WEIGHT = 0.3
MOMENTUM_WEIGHT = 0.3
TWITTER_WEIGHT = 0.2


@dataclass
class SentimentScore:
    score: float
    source_breakdown: Dict[str, float]


def get_sentiment(symbol: str) -> SentimentScore:
    symbol = symbol.upper()
    breakdown: Dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0
    available_sources: List[str] = []
    missing_sources: List[str] = []

    for name, weight, fetcher in _sentiment_sources():
        score, available = fetcher(symbol)
        breakdown[name] = score
        if available and weight > 0:
            weighted_sum += score * weight
            total_weight += weight
            available_sources.append(name)
        else:
            missing_sources.append(name)

    final_score = round(weighted_sum / total_weight, 2) if total_weight > 0 else 50.0
    logger.info(
        "Sentiment sources for %s available=%s missing=%s",
        symbol,
        available_sources,
        missing_sources,
    )
    return SentimentScore(score=final_score, source_breakdown=breakdown)


def _sentiment_sources():
    sources = [
        ("newsapi", NEWS_WEIGHT, _fetch_newsapi_sentiment),
        ("alphavantage", ALPHA_WEIGHT, _fetch_alpha_sentiment),
        ("momentum", MOMENTUM_WEIGHT, _fetch_price_momentum),
    ]
    if settings.enable_twitter:
        sources.append(("twitter", TWITTER_WEIGHT, _fetch_twitter_placeholder))
    return sources


def _fetch_newsapi_sentiment(symbol: str) -> Tuple[float, bool]:
    key = settings.newsapi_key
    if not key:
        return 50.0, False
    params = {
        "q": symbol,
        "language": "en",
        "apiKey": key,
        "sortBy": "publishedAt",
        "pageSize": 20,
    }
    try:
        response = requests.get("https://newsapi.org/v2/everything", params=params, timeout=6)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        if not articles:
            return 50.0, False
        score = 0.0
        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            if any(token in text for token in ("beat", "surge", "strong", "gain")):
                score += 70
            elif any(token in text for token in ("miss", "drop", "weak", "loss")):
                score += 30
            else:
                score += 50
        return round(score / len(articles), 2), True
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("NewsAPI sentiment failed for %s: %s", symbol, exc)
        return 50.0, False


def _fetch_alpha_sentiment(symbol: str) -> Tuple[float, bool]:
    key = settings.alpha_vantage_key
    if not key:
        return 50.0, False
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "apikey": key,
    }
    try:
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=6)
        response.raise_for_status()
        feed = response.json().get("feed", [])
        if not feed:
            return 50.0, False
        score = 0.0
        count = 0
        for item in feed[:20]:
            raw_score = item.get("overall_sentiment_score")
            if raw_score is None:
                continue
            normalized = max(min((float(raw_score) + 1.0) / 2.0 * 100.0, 100.0), 0.0)
            score += normalized
            count += 1
        if count == 0:
            return 50.0, False
        return round(score / count, 2), True
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("AlphaVantage sentiment failed for %s: %s", symbol, exc)
        return 50.0, False


def _fetch_price_momentum(symbol: str) -> Tuple[float, bool]:
    try:
        bars = get_aggregates(symbol, timespan="1day", limit=3)
        if len(bars) < 2:
            return 50.0, False
        prev, last = bars[-2], bars[-1]
        if prev.close == 0:
            return 50.0, False
        pct_change = (last.close - prev.close) / prev.close
        score = max(min((pct_change * 100) + 50, 100), 0)
        return round(score, 2), True
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("Momentum sentiment unavailable for %s: %s", symbol, exc)
        return 50.0, False


def _fetch_twitter_placeholder(symbol: str) -> Tuple[float, bool]:
    # Placeholder until Twitter/X sentiment is wired in.
    return 50.0, True

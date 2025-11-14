from __future__ import annotations

from typing import List

import requests

from config import get_settings
from utils.logger import get_logger

logger = get_logger("Universe")
settings = get_settings()

PRICE_MAX = 5.0
VOLUME_MIN = 200_000
MARKET_CAP_MIN = 50_000_000
MARKET_CAP_MAX = 2_000_000_000


def _screen_with_twelvedata() -> List[str]:
    key = settings.twelvedata_api_key
    if not key:
        logger.warning("TwelveData key missing; skipping screener")
        return []

    params = {
        "outputsize": 50,
        "market_cap_min": MARKET_CAP_MIN,
        "market_cap_max": MARKET_CAP_MAX,
        "price_max": PRICE_MAX,
        "volume_min": VOLUME_MIN,
        "apikey": key,
    }
    try:
        response = requests.get("https://api.twelvedata.com/stock_screener", params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            logger.warning("TwelveData screener payload malformed")
            return []
        symbols: List[str] = []
        for entry in data:
            try:
                price = float(entry.get("price", 0))
                volume = float(entry.get("volume", 0))
                market_cap = float(entry.get("market_cap", 0))
            except (TypeError, ValueError):
                continue
            if price >= PRICE_MAX or volume < VOLUME_MIN:
                continue
            if not (MARKET_CAP_MIN <= market_cap <= MARKET_CAP_MAX):
                continue
            symbol = entry.get("symbol")
            if symbol:
                symbols.append(symbol.upper())
        return symbols
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("TwelveData screener failed: %s", exc)
        return []


def _alpha_global_quote(symbol: str, key: str) -> tuple[float, float]:
    params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": key}
    response = requests.get("https://www.alphavantage.co/query", params=params, timeout=8)
    response.raise_for_status()
    payload = response.json().get("Global Quote", {})
    price = float(payload.get("05. price", 0))
    volume = float(payload.get("06. volume", 0))
    return price, volume


def _alpha_overview(symbol: str, key: str) -> float:
    params = {"function": "OVERVIEW", "symbol": symbol, "apikey": key}
    response = requests.get("https://www.alphavantage.co/query", params=params, timeout=8)
    response.raise_for_status()
    market_cap = float(response.json().get("MarketCapitalization", 0))
    return market_cap


def _screen_with_alpha() -> List[str]:
    key = settings.alpha_vantage_key
    if not key:
        logger.warning("AlphaVantage key missing; skipping screener fallback")
        return []

    params = {"function": "SYMBOL_SEARCH", "keywords": "micro", "apikey": key}
    try:
        response = requests.get("https://www.alphavantage.co/query", params=params, timeout=8)
        response.raise_for_status()
        matches = response.json().get("bestMatches", [])
        symbols: List[str] = []
        for match in matches[:10]:
            symbol = match.get("1. symbol")
            if not symbol:
                continue
            try:
                price, volume = _alpha_global_quote(symbol, key)
                market_cap = _alpha_overview(symbol, key)
            except Exception as exc:  # pragma: no cover - network guard
                logger.warning("AlphaVantage detail lookup failed for %s: %s", symbol, exc)
                continue
            if price >= PRICE_MAX or volume < VOLUME_MIN:
                continue
            if not (MARKET_CAP_MIN <= market_cap <= MARKET_CAP_MAX):
                continue
            symbols.append(symbol.upper())
        return symbols
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("AlphaVantage screener failed: %s", exc)
        return []


def build_universe() -> List[str]:
    screen = _screen_with_twelvedata()
    if not screen:
        screen = _screen_with_alpha()

    logger.info("Universe candidates before merge: %s", len(screen))

    combined = list(dict.fromkeys(screen + settings.symbols()))
    logger.info("Final universe size: %s", len(combined))
    return combined

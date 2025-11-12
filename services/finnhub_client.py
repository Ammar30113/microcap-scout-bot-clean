"""Finnhub async client helpers."""

from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx

from utils.http_client import get_http_client
from utils.logger import get_logger
from utils.settings import get_settings

logger = get_logger(__name__)

BASE_URL = "https://finnhub.io/api/v1"
FINNHUB_BACKOFF_SECONDS = int(os.getenv("FINNHUB_BACKOFF_SECONDS", "60"))
RATE_LIMIT_STATUSES = {403, 429}
_BACKOFF_UNTIL: Dict[str, float] = {"quote": 0.0, "sentiment": 0.0, "news": 0.0}


def _require_api_key() -> str:
    api_key = get_settings().finnhub_api_key
    if not api_key:
        raise RuntimeError("FINNHUB_API_KEY not configured")
    return api_key


async def get_quote(symbol: str) -> Optional[float]:
    """Fetch the latest Finnhub quote."""

    if _should_backoff("quote"):
        logger.info(
            "Finnhub quote backoff active (%ss remaining), skipping %s",
            _backoff_remaining("quote"),
            symbol,
        )
        return None

    api_key = _require_api_key()
    url = f"{BASE_URL}/quote"
    params = {"symbol": symbol.upper()}
    headers = {"X-Finnhub-Token": api_key}

    async with get_http_client() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network guard
            status = exc.response.status_code if exc.response else None
            if status in RATE_LIMIT_STATUSES:
                _start_backoff("quote", status, symbol)
                return None
            logger.warning("Finnhub quote lookup failed for %s: %s", symbol, exc)
            raise
        except httpx.HTTPError as exc:  # pragma: no cover - network guard
            logger.warning("Finnhub quote lookup failed for %s: %s", symbol, exc)
            raise

    payload = response.json()
    return payload.get("c")


async def get_company_news(symbol: str, days_back: int = 3) -> List[Dict[str, Any]]:
    """Return the most recent company news items for ``symbol`` (max 5)."""

    if _should_backoff("news"):
        logger.info(
            "Finnhub news backoff active (%ss remaining), skipping %s",
            _backoff_remaining("news"),
            symbol,
        )
        return []

    api_key = _require_api_key()
    today = date.today()
    start = today - timedelta(days=days_back)
    params = {
        "symbol": symbol.upper(),
        "from": start.isoformat(),
        "to": today.isoformat(),
    }
    headers = {"X-Finnhub-Token": api_key}
    url = f"{BASE_URL}/company-news"

    async with get_http_client() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network guard
            status = exc.response.status_code if exc.response else None
            if status in RATE_LIMIT_STATUSES:
                _start_backoff("news", status, symbol)
                return []
            logger.warning("Finnhub news lookup failed for %s: %s", symbol, exc)
            raise
        except httpx.HTTPError as exc:  # pragma: no cover - network guard
            logger.warning("Finnhub news lookup failed for %s: %s", symbol, exc)
            raise

    payload = response.json()
    return list(payload[:5]) if isinstance(payload, list) else []


async def get_sentiment(symbol: str) -> Dict[str, Any]:
    """Return Finnhub's aggregated news sentiment payload."""

    if _should_backoff("sentiment"):
        logger.info(
            "Finnhub sentiment backoff active (%ss remaining), skipping %s",
            _backoff_remaining("sentiment"),
            symbol,
        )
        return {}

    api_key = _require_api_key()
    headers = {"X-Finnhub-Token": api_key}
    params = {"symbol": symbol.upper()}
    url = f"{BASE_URL}/news-sentiment"

    async with get_http_client() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network guard
            status = exc.response.status_code if exc.response else None
            if status in RATE_LIMIT_STATUSES:
                _start_backoff("sentiment", status, symbol)
                return {}
            logger.warning("Finnhub sentiment lookup failed for %s: %s", symbol, exc)
            raise
        except httpx.HTTPError as exc:  # pragma: no cover - network guard
            logger.warning("Finnhub sentiment lookup failed for %s: %s", symbol, exc)
            raise

    payload: Dict[str, Any] = response.json()
    return payload.get("sentiment", {}) or {}


def _should_backoff(kind: str) -> bool:
    if FINNHUB_BACKOFF_SECONDS <= 0:
        return False
    expires_at = _BACKOFF_UNTIL.get(kind, 0.0)
    return time.time() < expires_at


def _start_backoff(kind: str, status: Optional[int], symbol: Optional[str] = None) -> None:
    if FINNHUB_BACKOFF_SECONDS <= 0:
        return
    delay = FINNHUB_BACKOFF_SECONDS
    _BACKOFF_UNTIL[kind] = time.time() + delay
    logger.warning(
        "Finnhub %s entering backoff for %ss (HTTP %s%s)",
        kind,
        delay,
        status,
        f", symbol {symbol}" if symbol else "",
    )


def _backoff_remaining(kind: str) -> int:
    expires_at = _BACKOFF_UNTIL.get(kind, 0.0)
    return max(int(expires_at - time.time()), 0)

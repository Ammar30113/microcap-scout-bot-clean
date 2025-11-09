import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yfinance as yf

from utils.logger import get_logger
from utils.settings import get_settings

logger = get_logger(__name__)

CACHE_TTL = timedelta(minutes=5)
THROTTLE_WINDOW_SECONDS = 30
THROTTLE_LIMIT = 10
THROTTLE_SLEEP_SECONDS = 10
MAX_FAILURES = 3
RATE_LIMIT_BACKOFF = timedelta(seconds=90)
FALLBACK_HTTP_TIMEOUT = 6.0

STOCKDATA_BASE_URL = "https://api.stockdata.org/v1/data/quote"
ALPACA_TRADE_PATH = "/stocks/{symbol}/trades/latest"
ALPACA_QUOTE_PATH = "/stocks/{symbol}/quotes/latest"


CacheEntry = Tuple[datetime, Dict[str, Any]]

CACHE: Dict[str, CacheEntry] = {}
LAST_REQUESTS: List[datetime] = []
FAIL_COUNTS: Dict[str, int] = {}
STATE_LOCK = threading.Lock()
RATE_LIMIT_UNTIL: Optional[datetime] = None


async def fetch_yfinance_snapshot(symbol: str) -> Dict[str, Any]:
    """
    Fetch a lightweight snapshot using yfinance in a thread executor with
    caching, throttling, and retry tracking to minimize Yahoo rate limits.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch, symbol.upper())


def _sync_fetch(symbol: str) -> Dict[str, Any]:
    now = datetime.utcnow()
    payload: Dict[str, Any] = {"provider": "yfinance", "symbol": symbol}

    wait_seconds = _current_rate_limit_delay(now)
    if wait_seconds > 0:
        payload["warning"] = f"yfinance_backoff_{int(wait_seconds)}s"
        fallback_snapshot = _fallback_snapshot(symbol, now)
        if fallback_snapshot is not None:
            payload["data"] = fallback_snapshot
        return payload

    cached = _get_cached(symbol, now)
    if cached is not None:
        payload["data"] = cached
        return payload

    if _has_exceeded_failures(symbol):
        payload["warning"] = "Skipping yfinance lookup after repeated failures"
        return payload

    _apply_throttling(now)
    _register_request(now)

    try:
        ticker = yf.Ticker(symbol)
        fast_info = dict(ticker.fast_info or {})
        history_frame = ticker.history(period="1d")
        history_payload: Dict[str, Any] = {}
        if not history_frame.empty:
            latest_row = history_frame.tail(1).reset_index().to_dict("records")
            history_payload = latest_row[0] if latest_row else {}
            date_value = history_payload.get("Date")
            if hasattr(date_value, "isoformat"):
                history_payload["Date"] = date_value.isoformat()

        result_data = {"fast_info": fast_info, "history": history_payload}

        _cache_result(symbol, now, result_data)
        _reset_failures(symbol)
        payload["data"] = result_data
    except Exception as exc:  # pragma: no cover - defensive
        failure_count = _increment_failure(symbol)
        if _is_rate_limit_error(exc):
            _set_rate_limit(now)
        logger.warning(
            "yfinance fetch failed for %s (attempt %s/%s): %s",
            symbol,
            failure_count,
            MAX_FAILURES,
            exc,
        )
        payload["error"] = str(exc)
        if failure_count >= MAX_FAILURES:
            payload["warning"] = "Skipping yfinance lookup after repeated failures"
        fallback_snapshot = _fallback_snapshot(symbol, now)
        if fallback_snapshot is not None:
            payload["data"] = fallback_snapshot
            existing_warning = payload.get("warning")
            fallback_note = "Using fallback quote provider"
            payload["warning"] = f"{existing_warning}; {fallback_note}" if existing_warning else fallback_note

    return payload


def _get_cached(symbol: str, now: datetime) -> Dict[str, Any] | None:
    with STATE_LOCK:
        entry = CACHE.get(symbol)
        if not entry:
            return None
        cached_time, data = entry
        if now - cached_time < CACHE_TTL:
            cached_data = data
        else:
            CACHE.pop(symbol, None)
            cached_data = None

    if cached_data is not None:
        logger.info("Using cached yfinance data for %s", symbol)
    return cached_data


def _cache_result(symbol: str, now: datetime, data: Dict[str, Any]) -> None:
    with STATE_LOCK:
        CACHE[symbol] = (now, data)


def _apply_throttling(now: datetime) -> None:
    with STATE_LOCK:
        LAST_REQUESTS[:] = [t for t in LAST_REQUESTS if (now - t).total_seconds() < THROTTLE_WINDOW_SECONDS]
        request_count = len(LAST_REQUESTS)
    if request_count >= THROTTLE_LIMIT:
        logger.warning("yfinance rate limit approaching — sleeping %s seconds", THROTTLE_SLEEP_SECONDS)
        time.sleep(THROTTLE_SLEEP_SECONDS)
        with STATE_LOCK:
            LAST_REQUESTS.clear()


def _register_request(timestamp: datetime) -> None:
    with STATE_LOCK:
        LAST_REQUESTS.append(timestamp)


def _increment_failure(symbol: str) -> int:
    with STATE_LOCK:
        FAIL_COUNTS[symbol] = FAIL_COUNTS.get(symbol, 0) + 1
        return FAIL_COUNTS[symbol]


def _reset_failures(symbol: str) -> None:
    with STATE_LOCK:
        FAIL_COUNTS.pop(symbol, None)


def _has_exceeded_failures(symbol: str) -> bool:
    with STATE_LOCK:
        failures = FAIL_COUNTS.get(symbol, 0)
    if failures >= MAX_FAILURES:
        logger.warning("Skipping yfinance lookups for %s after %s failures", symbol, failures)
        return True
    return False


def _current_rate_limit_delay(now: datetime) -> float:
    global RATE_LIMIT_UNTIL
    with STATE_LOCK:
        if RATE_LIMIT_UNTIL is None:
            return 0.0
        if now >= RATE_LIMIT_UNTIL:
            RATE_LIMIT_UNTIL = None
            return 0.0
        return (RATE_LIMIT_UNTIL - now).total_seconds()


def _set_rate_limit(now: datetime) -> None:
    global RATE_LIMIT_UNTIL
    backoff_until = now + RATE_LIMIT_BACKOFF
    with STATE_LOCK:
        RATE_LIMIT_UNTIL = backoff_until
    logger.warning(
        "yfinance rate limit triggered, backing off until %s (%.0fs)",
        backoff_until.isoformat(),
        RATE_LIMIT_BACKOFF.total_seconds(),
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "too many requests" in message or "rate limit" in message


def get_latest_price(symbol: str) -> Optional[float]:
    """
    Lightweight helper for synchronous price lookups used by the trading engine.
    """
    normalized_symbol = symbol.upper()
    snapshot = _sync_fetch(normalized_symbol)
    data = snapshot.get("data") or {}
    if not data:
        fallback = _fallback_snapshot(normalized_symbol, datetime.utcnow())
        if fallback is not None:
            data = fallback
    fast_info = data.get("fast_info") or {}

    price_candidates = [
        fast_info.get("lastPrice"),
        fast_info.get("regularMarketPrice"),
        fast_info.get("previousClose"),
    ]
    for price in price_candidates:
        if price is not None:
            return float(price)

    history = data.get("history") or {}
    close_value = history.get("Close") or history.get("close")
    if close_value is not None:
        return float(close_value)
    return None


def _fallback_snapshot(symbol: str, now: datetime) -> Optional[Dict[str, Any]]:
    """
    Attempt to build a snapshot using configured data providers when yfinance is unavailable.
    """
    upper_symbol = symbol.upper()
    price = _fetch_stockdata_price(upper_symbol)
    source = "stockdata"
    if price is None:
        price = _fetch_alpaca_price(upper_symbol)
        source = "alpaca"
    if price is None:
        logger.debug("No fallback price providers produced data for %s", upper_symbol)
        return None

    snapshot = _build_price_snapshot(price, source)
    _cache_result(upper_symbol, now, snapshot)
    logger.info("Using %s fallback pricing for %s", source, upper_symbol)
    return snapshot


def _build_price_snapshot(price: float, source: str) -> Dict[str, Any]:
    return {
        "fast_info": {"lastPrice": price},
        "history": {"Close": price},
        "meta": {"price_source": source},
    }


def _fetch_stockdata_price(symbol: str) -> Optional[float]:
    settings = get_settings()
    api_key = settings.stockdata_api_key
    if not api_key:
        return None

    params = {"symbols": symbol, "api_token": api_key}
    try:
        response = httpx.get(
            STOCKDATA_BASE_URL,
            params=params,
            timeout=FALLBACK_HTTP_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("StockData fallback failed for %s: %s", symbol, exc)
        return None

    records = payload.get("data") or []
    if not records:
        return None

    record = records[0]
    for field_name in ("price", "last", "close", "previous_close_price", "prev_close"):
        value = _coerce_float(record.get(field_name))
        if value is not None:
            return value
    return None


def _fetch_alpaca_price(symbol: str) -> Optional[float]:
    settings = get_settings()
    api_key = settings.alpaca_api_key
    secret_key = settings.alpaca_secret_key
    if not api_key or not secret_key:
        return None

    base_url = str(settings.alpaca_base_url).rstrip("/")
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
        "Accept": "application/json",
    }

    trade_url = f"{base_url}{ALPACA_TRADE_PATH.format(symbol=symbol)}"
    try:
        response = httpx.get(trade_url, headers=headers, timeout=FALLBACK_HTTP_TIMEOUT)
        response.raise_for_status()
        trade_payload = response.json()
        trade = trade_payload.get("trade") or {}
        trade_price = _coerce_float(trade.get("p") or trade.get("price"))
        if trade_price is not None:
            return trade_price
    except httpx.HTTPError as exc:
        logger.debug("Alpaca trade fallback failed for %s: %s", symbol, exc)

    quote_url = f"{base_url}{ALPACA_QUOTE_PATH.format(symbol=symbol)}"
    try:
        response = httpx.get(quote_url, headers=headers, timeout=FALLBACK_HTTP_TIMEOUT)
        response.raise_for_status()
        quote_payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Alpaca quote fallback failed for %s: %s", symbol, exc)
        return None

    quote = quote_payload.get("quote") or {}
    ask = _coerce_float(quote.get("ap") or quote.get("ask_price"))
    bid = _coerce_float(quote.get("bp") or quote.get("bid_price"))
    if ask is not None and bid is not None:
        return (ask + bid) / 2.0
    return ask or bid


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

import asyncio
from typing import Any, Dict

import yfinance as yf

from utils.logger import get_logger

logger = get_logger(__name__)


async def fetch_yfinance_snapshot(symbol: str) -> Dict[str, Any]:
    """
    Fetch a lightweight snapshot using yfinance in a thread executor.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch, symbol.upper())


def _sync_fetch(symbol: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"provider": "yfinance", "symbol": symbol}
    try:
        ticker = yf.Ticker(symbol)
        fast_info = dict(ticker.fast_info) if ticker.fast_info else {}
        payload["data"] = {"fast_info": fast_info}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("yfinance fetch failed: %s", exc)
        payload["error"] = str(exc)
    return payload

from typing import Any, Dict

import httpx

from utils.http_client import get_http_client
from utils.logger import get_logger
from utils.settings import get_settings

STOCKDATA_BASE_URL = "https://api.stockdata.org/v1/data/quote"

logger = get_logger(__name__)


async def fetch_stockdata_quote(symbol: str) -> Dict[str, Any]:
    """
    Fetch quote data from StockData.org.
    """
    settings = get_settings()
    payload: Dict[str, Any] = {"provider": "stockdata", "symbol": symbol.upper()}

    if not settings.stockdata_api_key:
        payload["warning"] = "STOCKDATA_API_KEY not configured"
        return payload

    params = {"symbols": symbol.upper(), "api_token": settings.stockdata_api_key}

    async with get_http_client() as client:
        try:
            response = await client.get(STOCKDATA_BASE_URL, params=params)
            response.raise_for_status()
            payload["data"] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("StockData request failed: %s", exc)
            payload["error"] = str(exc)

    return payload

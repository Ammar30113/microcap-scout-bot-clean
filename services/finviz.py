from typing import Any, Dict

import httpx

from utils.http_client import get_http_client
from utils.logger import get_logger
from utils.settings import get_settings

FINVIZ_BASE_URL = "https://finviz.com/api/quote.ashx"

logger = get_logger(__name__)


async def fetch_finviz_snapshot(symbol: str) -> Dict[str, Any]:
    """
    Fetch quote/snapshot data from Finviz for a given symbol.
    """
    settings = get_settings()
    payload: Dict[str, Any] = {"provider": "finviz", "symbol": symbol.upper()}

    if not settings.finviz_api_key:
        payload["warning"] = "FINVIZ_API_KEY not configured"
        return payload

    params = {"ticker": symbol.upper(), "token": settings.finviz_api_key}
    headers = {"User-Agent": "microcap-scout-bot/0.1.0"}

    async with get_http_client() as client:
        try:
            response = await client.get(FINVIZ_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Finviz request failed: %s", exc)
            payload["error"] = str(exc)
            return payload

    try:
        payload["data"] = response.json()
    except ValueError:
        payload["data"] = {"raw": response.text}

    return payload

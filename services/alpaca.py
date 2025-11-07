from typing import Any, Dict

import httpx

from utils.http_client import get_http_client
from utils.logger import get_logger
from utils.settings import get_settings

logger = get_logger(__name__)


async def fetch_alpaca_latest_quote(symbol: str) -> Dict[str, Any]:
    """
    Fetch the latest quote data from Alpaca's market data API.
    """
    settings = get_settings()
    payload: Dict[str, Any] = {"provider": "alpaca", "symbol": symbol.upper()}

    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        payload["warning"] = "ALPACA_API_KEY and ALPACA_SECRET_KEY not fully configured"
        return payload

    url = f"{settings.alpaca_base_url}/stocks/{symbol.upper()}/quotes/latest"
    headers = {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        "Accept": "application/json",
    }

    async with get_http_client() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload["data"] = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Alpaca request failed: %s", exc)
            payload["error"] = str(exc)

    return payload

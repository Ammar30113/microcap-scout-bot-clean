from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from core.logger import get_logger

logger = get_logger(__name__)


class PolygonProvider:
    """Market data + reference helper built on Polygon.io APIs."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        if not api_key:
            logger.warning("PolygonProvider initialized without API key")

    def _request(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        params = params or {}
        params.setdefault("apiKey", self.api_key)
        url = f"{self.base_url}{path}"
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_price(self, symbol: str) -> float:
        payload = self._request(f"/v2/aggs/ticker/{symbol.upper()}/prev")
        results = payload.get("results", [])
        if not results:
            raise RuntimeError("Polygon returned no aggregate data")
        return float(results[0].get("c"))

    def get_aggregates(self, symbol: str, timespan: str = "1day", limit: int = 60) -> List[Dict[str, float]]:
        end = datetime.utcnow()
        start = end - timedelta(days=limit * 2)
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": limit,
        }
        path = f"/v2/aggs/ticker/{symbol.upper()}/range/1/{timespan}/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
        payload = self._request(path, params=params)
        bars = payload.get("results", [])
        normalized: List[Dict[str, float]] = []
        for bar in bars:
            normalized.append(
                {
                    "open": float(bar.get("o", 0.0)),
                    "high": float(bar.get("h", 0.0)),
                    "low": float(bar.get("l", 0.0)),
                    "close": float(bar.get("c", 0.0)),
                    "volume": float(bar.get("v", 0.0)),
                    "timestamp": float(bar.get("t", 0.0)) / 1000.0,
                }
            )
        return normalized

    def get_reference_data(self, symbol: str) -> Optional[Dict[str, float]]:
        try:
            payload = self._request(f"/v3/reference/tickers/{symbol.upper()}")
        except Exception as exc:
            logger.debug("Polygon reference lookup failed for %s: %s", symbol, exc)
            return None
        results = payload.get("results") or {}
        market_cap = results.get("market_cap")
        day = results.get("day") or {}
        price = day.get("close") or day.get("c") or results.get("close")
        avg_volume = results.get("avg30_volume") or results.get("prev_day", {}).get("v")
        if market_cap is None or price is None or avg_volume is None:
            return None
        return {
            "symbol": symbol.upper(),
            "market_cap": float(market_cap),
            "price": float(price),
            "avg_volume": float(avg_volume),
        }

    def fetch_etf_holdings(self, etf_symbol: str) -> List[str]:
        holdings: List[str] = []
        next_url: Optional[str] = None
        params: Dict[str, str] = {"apiKey": self.api_key, "limit": "1000"}
        url = f"{self.base_url}/v2/reference/etfs/{etf_symbol.upper()}/holdings"
        while True:
            response = requests.get(next_url or url, params=None if next_url else params, timeout=10)
            response.raise_for_status()
            data = response.json()
            for holding in data.get("holdings", []):
                ticker = holding.get("ticker")
                if ticker:
                    holdings.append(ticker.upper())
            next_url = data.get("next_url")
            if not next_url:
                break
        return holdings

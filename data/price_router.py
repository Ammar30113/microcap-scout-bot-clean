from __future__ import annotations

from typing import Dict, List, Sequence

import pandas as pd

from core.config import get_settings
from core.logger import get_logger
from data.alpaca_provider import AlpacaProvider
from data.alphavantage_provider import AlphaVantageProvider
from data.twelvedata_provider import TwelveDataProvider

logger = get_logger(__name__)
settings = get_settings()


class PriceRouter:
    """Funnel price + aggregate requests across multiple providers."""

    def __init__(self) -> None:
        self.providers: Sequence[object] = (
            AlpacaProvider(settings),
            TwelveDataProvider(settings.twelvedata_api_key),
            AlphaVantageProvider(settings.alphavantage_api_key),
        )

    def get_price(self, symbol: str) -> float:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return provider.get_price(symbol)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - network guard
                provider_name = provider.__class__.__name__
                logger.warning("%s price lookup failed for %s: %s", provider_name, symbol, exc)
                last_error = exc
        raise RuntimeError(f"All providers failed to return price for {symbol}") from last_error

    def get_aggregates(self, symbol: str, timespan: str = "1day", limit: int = 60) -> List[Dict[str, float]]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                bars = provider.get_aggregates(symbol, timespan, limit)  # type: ignore[attr-defined]
                if bars:
                    return bars
            except Exception as exc:  # pragma: no cover - network guard
                provider_name = provider.__class__.__name__
                logger.warning("%s aggregates failed for %s: %s", provider_name, symbol, exc)
                last_error = exc
        raise RuntimeError(f"All providers failed to return aggregates for {symbol}") from last_error

    @staticmethod
    def aggregates_to_dataframe(bars: List[Dict[str, float]]) -> pd.DataFrame:
        frame = pd.DataFrame(bars)
        if not frame.empty:
            frame = frame.sort_values("timestamp").reset_index(drop=True)
        return frame

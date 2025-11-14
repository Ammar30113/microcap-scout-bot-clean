from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable, List, Optional, Sequence, TypeVar

import requests
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import TimeFrame, TimeFrameUnit

from config import get_settings
from utils.logger import get_logger

logger = get_logger("MarketData")
settings = get_settings()


class ProviderError(Exception):
    """Raised when a market data provider fails to return usable data."""


def _build_timeframe(timespan: str) -> TimeFrame:
    timespan = timespan.lower()
    if timespan == "1day":
        return TimeFrame.Day
    if timespan == "1hour":
        return TimeFrame(1, TimeFrameUnit.Hour)
    if timespan.endswith("min"):
        try:
            minutes = int(timespan.replace("min", ""))
        except ValueError as exc:
            raise ProviderError(f"Unsupported minute timeframe '{timespan}'") from exc
        return TimeFrame(minutes, TimeFrameUnit.Minute)
    if timespan == "1min":
        return TimeFrame.Minute
    if timespan == "5min":
        return TimeFrame(5, TimeFrameUnit.Minute)
    raise ProviderError(f"Unsupported timespan '{timespan}' for Alpaca")


@dataclass
class AggregateBar:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class AlpacaProvider:
    def __init__(self) -> None:
        if settings.alpaca_api_key and settings.alpaca_api_secret:
            self.client: Optional[tradeapi.REST] = tradeapi.REST(
                settings.alpaca_api_key,
                settings.alpaca_api_secret,
                base_url=str(settings.alpaca_trading_url),
            )
        else:
            self.client = None

    def get_price(self, symbol: str) -> float:
        if self.client is None:
            raise ProviderError("Alpaca credentials missing")
        try:
            trade = self.client.get_latest_trade(symbol.upper())
            price = getattr(trade, "price", None) or getattr(trade, "p", None)
            if price is None:
                raise ProviderError("Alpaca returned no price")
            return float(price)
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"Alpaca price lookup failed: {exc}") from exc

    def get_aggregates(self, symbol: str, timespan: str, limit: int) -> List[AggregateBar]:
        if self.client is None:
            raise ProviderError("Alpaca credentials missing")
        try:
            timeframe = _build_timeframe(timespan)
            bars = self.client.get_bars(symbol.upper(), timeframe, limit=limit)
            if not bars:
                raise ProviderError("Alpaca returned no aggregates")
            return [
                AggregateBar(
                    symbol=symbol.upper(),
                    timestamp=str(bar.t),
                    open=float(bar.o),
                    high=float(bar.h),
                    low=float(bar.l),
                    close=float(bar.c),
                    volume=float(bar.v),
                )
                for bar in bars
            ]
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"Alpaca aggregates lookup failed: {exc}") from exc


class TwelveDataProvider:
    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    def _require_key(self) -> str:
        if not self.api_key:
            raise ProviderError("TwelveData API key missing")
        return self.api_key

    def get_price(self, symbol: str) -> float:
        key = self._require_key()
        params = {"symbol": symbol.upper(), "apikey": key}
        try:
            response = requests.get(f"{self.BASE_URL}/price", params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
            price = payload.get("price")
            if price is None:
                raise ProviderError(f"TwelveData returned malformed payload: {payload}")
            return float(price)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"TwelveData price lookup failed: {exc}") from exc

    def get_aggregates(self, symbol: str, timespan: str, limit: int) -> List[AggregateBar]:
        key = self._require_key()
        params = {
            "symbol": symbol.upper(),
            "interval": timespan,
            "outputsize": limit,
            "apikey": key,
        }
        try:
            response = requests.get(f"{self.BASE_URL}/time_series", params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
            values = payload.get("values")
            if not isinstance(values, list):
                raise ProviderError(f"TwelveData returned malformed aggregates: {payload}")
            bars: List[AggregateBar] = []
            for item in values[:limit]:
                bars.append(
                    AggregateBar(
                        symbol=symbol.upper(),
                        timestamp=str(item.get("datetime")),
                        open=float(item.get("open")),
                        high=float(item.get("high")),
                        low=float(item.get("low")),
                        close=float(item.get("close")),
                        volume=float(item.get("volume") or 0),
                    )
                )
            return bars
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"TwelveData aggregates lookup failed: {exc}") from exc


class AlphaVantageProvider:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    def _require_key(self) -> str:
        if not self.api_key:
            raise ProviderError("AlphaVantage API key missing")
        return self.api_key

    def get_price(self, symbol: str) -> float:
        key = self._require_key()
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol.upper(),
            "apikey": key,
        }
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
            series = payload.get("Time Series (Daily)")
            if not isinstance(series, dict):
                raise ProviderError("AlphaVantage returned no daily data")
            latest_key = sorted(series.keys())[-1]
            latest = series[latest_key]
            return float(latest.get("4. close"))
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"AlphaVantage price lookup failed: {exc}") from exc

    def get_aggregates(self, symbol: str, timespan: str, limit: int) -> List[AggregateBar]:
        if timespan != "1day":
            raise ProviderError("AlphaVantage only supports 1day aggregates in this pipeline")
        key = self._require_key()
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol.upper(),
            "apikey": key,
        }
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
            series = payload.get("Time Series (Daily)")
            if not isinstance(series, dict):
                raise ProviderError("AlphaVantage returned no aggregates")
            bars: List[AggregateBar] = []
            for date_key in sorted(series.keys(), reverse=True)[:limit]:
                entry = series[date_key]
                bars.append(
                    AggregateBar(
                        symbol=symbol.upper(),
                        timestamp=date_key,
                        open=float(entry.get("1. open")),
                        high=float(entry.get("2. high")),
                        low=float(entry.get("3. low")),
                        close=float(entry.get("4. close")),
                        volume=float(entry.get("6. volume") or 0),
                    )
                )
            return list(reversed(bars))
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"AlphaVantage aggregates lookup failed: {exc}") from exc


class MassiveProvider:
    BASE_URL = "https://api.massive.com/v1"

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    def get_reference_price(self, symbol: str) -> float:
        if not self.api_key:
            raise ProviderError("Massive API key missing")
        url = f"{self.BASE_URL}/reference/tickers/{symbol}/aggregates"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"timespan": "minute", "limit": 1}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results")
            if not results:
                raise ProviderError("Massive returned no aggregates")
            latest = results[-1]
            price = latest.get("close") or latest.get("price") or latest.get("c")
            if price is None:
                raise ProviderError("Massive payload missing price")
            return float(price)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - network guard
            raise ProviderError(f"Massive reference lookup failed: {exc}") from exc


_ALPACA_PROVIDER = AlpacaProvider()
_TWELVEDATA_PROVIDER = TwelveDataProvider(settings.twelvedata_api_key)
_ALPHA_PROVIDER = AlphaVantageProvider(settings.alpha_vantage_key)
_MASSIVE_PROVIDER = MassiveProvider(settings.massive_api_key)

T = TypeVar("T")


def _run_fallback(symbol: str, providers: Sequence[tuple[str, Callable[[], T]]]) -> T:
    last_error: Optional[Exception] = None
    for idx, (name, fetcher) in enumerate(providers):
        try:
            return fetcher()
        except ProviderError as exc:
            last_error = exc
            logger.warning("Provider %s failed for %s: %s", name, symbol.upper(), exc)
            if idx < len(providers) - 1:
                next_name = providers[idx + 1][0]
                logger.warning("Falling back to %s for %s", next_name, symbol.upper())
    raise RuntimeError(f"All providers failed for {symbol.upper()}") from last_error


def get_price(symbol: str) -> float:
    symbol = symbol.upper()
    providers: Sequence[tuple[str, Callable[[], float]]] = (
        ("Alpaca", partial(_ALPACA_PROVIDER.get_price, symbol)),
        ("TwelveData", partial(_TWELVEDATA_PROVIDER.get_price, symbol)),
        ("AlphaVantage", partial(_ALPHA_PROVIDER.get_price, symbol)),
    )
    price = _run_fallback(symbol, providers)

    try:
        ref_price = _MASSIVE_PROVIDER.get_reference_price(symbol)
    except ProviderError as exc:
        logger.info("Massive skipped for %s: %s", symbol, exc)
        return price

    blended = round((price + ref_price) / 2, 4)
    logger.info("Massive enrichment applied for %s", symbol)
    return blended


def get_aggregates(symbol: str, timespan: str = "1day", limit: int = 1) -> List[AggregateBar]:
    symbol = symbol.upper()
    providers: Sequence[tuple[str, Callable[[], List[AggregateBar]]]] = (
        ("Alpaca", partial(_ALPACA_PROVIDER.get_aggregates, symbol, timespan, limit)),
        ("TwelveData", partial(_TWELVEDATA_PROVIDER.get_aggregates, symbol, timespan, limit)),
        ("AlphaVantage", partial(_ALPHA_PROVIDER.get_aggregates, symbol, timespan, limit)),
    )
    return _run_fallback(symbol, providers)

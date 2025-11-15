from __future__ import annotations

from typing import Sequence, Set

import requests

from core.config import get_settings
from core.logger import get_logger
from universe import csv_loader

logger = get_logger(__name__)
settings = get_settings()


def expand_etf_constituents(etfs: Sequence[str]) -> Set[str]:
    """Fetch ETF constituents using Alpaca's reference endpoints with CSV fallback."""

    tickers: Set[str] = set()
    for etf in etfs:
        holdings = _fetch_alpaca_holdings(etf)
        if holdings:
            tickers.update(holdings)

    if not tickers:
        logger.warning("Alpaca ETF holdings unavailable; falling back to CSV universe")
        fallback = csv_loader.load_universe_from_csv(settings.universe_fallback_csv)
        if not fallback.empty and "symbol" in fallback.columns:
            tickers.update(fallback["symbol"].dropna().astype(str).str.upper().tolist())
    return tickers


def _fetch_alpaca_holdings(etf_symbol: str) -> Set[str]:
    if not settings.alpaca_api_key or not settings.alpaca_api_secret:
        logger.warning("Alpaca credentials missing; cannot fetch holdings for %s", etf_symbol)
        return set()

    url = f"{settings.alpaca_data_url.rstrip('/')}/reference/etfs/{etf_symbol.upper()}/holdings"
    headers = {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network guard
        logger.warning("Alpaca ETF holdings request failed for %s: %s", etf_symbol, exc)
        return set()

    data = response.json()
    holdings = data.get("holdings") or data.get("results") or []
    symbols: Set[str] = set()
    for item in holdings:
        symbol = item.get("symbol") or item.get("ticker") or item.get("asset_id")
        if symbol:
            symbols.add(str(symbol).upper())
    if not symbols:
        logger.info("No holdings returned for %s", etf_symbol)
    return symbols

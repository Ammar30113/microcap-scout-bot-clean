from __future__ import annotations

from typing import List, Sequence, Set

from data.polygon_provider import PolygonProvider
from core.logger import get_logger

logger = get_logger(__name__)


def expand_etf_constituents(provider: PolygonProvider, etfs: Sequence[str]) -> Set[str]:
    """Fetch all constituents for the provided ETF list."""

    tickers: Set[str] = set()
    for etf in etfs:
        try:
            holdings = provider.fetch_etf_holdings(etf)
        except Exception as exc:
            logger.warning("Failed to load holdings for %s: %s", etf, exc)
            continue
        tickers.update(holdings)
    return tickers

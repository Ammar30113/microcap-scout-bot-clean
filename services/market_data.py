import asyncio
from typing import Any, Dict

from utils.logger import get_logger
from utils.settings import get_settings

from .alpaca import fetch_alpaca_latest_quote
from .finviz import fetch_finviz_snapshot
from .stockdata import fetch_stockdata_quote
from .yfinance_client import fetch_yfinance_snapshot

logger = get_logger(__name__)


async def gather_symbol_insights(symbol: str | None = None) -> Dict[str, Any]:
    """
    Fetch a blended market snapshot from Finviz, StockData, and Alpaca.
    """
    settings = get_settings()
    target_symbol = (symbol or settings.default_symbol).upper()
    logger.info("Gathering insights for %s", target_symbol)

    finviz_task = fetch_finviz_snapshot(target_symbol)
    stockdata_task = fetch_stockdata_quote(target_symbol)
    alpaca_task = fetch_alpaca_latest_quote(target_symbol)
    yfinance_task = fetch_yfinance_snapshot(target_symbol)

    finviz, stockdata, alpaca, yfinance_data = await asyncio.gather(
        finviz_task,
        stockdata_task,
        alpaca_task,
        yfinance_task,
    )

    return {
        "symbol": target_symbol,
        "sources": [finviz, stockdata, alpaca, yfinance_data],
    }

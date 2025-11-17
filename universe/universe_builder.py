from __future__ import annotations

from pathlib import Path
import pandas as pd

from core.config import get_settings
from core.logger import get_logger
from universe.csv_loader import load_universe_from_csv
from universe.etf_expander import fetch_etf_holdings

logger = get_logger(__name__)
settings = get_settings()

DEFAULT_ETFS = ["SPY", "QQQ", "IWM"]
UNIVERSE_CSV = Path("universe/fallback_universe.csv")


def _filter_symbols(symbols: list[str]) -> list[str]:
    return [sym for sym in symbols if sym.isalnum()]


def get_universe() -> list[str]:
    """Return a broad liquid universe from ETF constituents or CSV fallback."""

    holdings = fetch_etf_holdings(DEFAULT_ETFS)
    symbols: list[str] = []
    if holdings:
        symbols = _filter_symbols(sorted(set(holdings)))
        logger.info("Loaded %s symbols via ETF holdings", len(symbols))
    else:
        df = load_universe_from_csv(UNIVERSE_CSV)
        symbols = _filter_symbols(df["symbol"].dropna().astype(str).str.upper().tolist())
        logger.info("Loaded %s symbols from liquid_universe.csv", len(symbols))

    logger.info("Universe size after filtering: %s", len(symbols))
    return symbols

from __future__ import annotations

import pandas as pd

from core.config import get_settings
from core.logger import get_logger
from universe import csv_loader, microcap_filter
from universe.etf_expander import expand_etf_constituents

logger = get_logger(__name__)
settings = get_settings()


def build_universe() -> pd.DataFrame:
    """Construct the working symbol universe from ETF constituents and filters."""

    tickers = expand_etf_constituents(settings.microcap_etfs)
    fallback = csv_loader.load_universe_from_csv(settings.universe_fallback_csv)
    if fallback.empty:
        logger.warning("Fallback universe CSV empty; returning empty frame")
        return fallback

    if tickers:
        fallback["symbol"] = fallback["symbol"].astype(str).str.upper()
        subset = fallback[fallback["symbol"].isin({symbol.upper() for symbol in tickers})]
        if subset.empty:
            logger.warning("No overlap between ETF holdings and fallback CSV; using raw fallback data")
        else:
            fallback = subset
    else:
        logger.warning("ETF expansion yielded no tickers; using full fallback dataset")

    filtered = microcap_filter.apply_filters(fallback)
    if filtered.empty:
        logger.warning("Filtered universe empty; returning fallback data without filters")
        return fallback
    return filtered

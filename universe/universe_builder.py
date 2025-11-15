from __future__ import annotations

from typing import List

import pandas as pd

from core.config import get_settings
from core.logger import get_logger
from data.polygon_provider import PolygonProvider
from universe import csv_loader, microcap_filter
from universe.etf_expander import expand_etf_constituents

logger = get_logger(__name__)
settings = get_settings()


def build_universe() -> pd.DataFrame:
    """Construct the working symbol universe from ETF constituents and filters."""

    polygon = PolygonProvider(settings.polygon_api_key)
    tickers = expand_etf_constituents(polygon, settings.microcap_etfs)
    if not tickers:
        logger.warning("ETF expansion yielded no tickers; using CSV fallback")
        return microcap_filter.apply_filters(csv_loader.load_universe_from_csv(settings.universe_fallback_csv))

    fundamentals: List[dict] = []
    for symbol in sorted(tickers):
        reference = polygon.get_reference_data(symbol)
        if reference:
            fundamentals.append(reference)
    if not fundamentals:
        logger.warning("Polygon fundamentals unavailable; using CSV fallback")
        return microcap_filter.apply_filters(csv_loader.load_universe_from_csv(settings.universe_fallback_csv))

    df = pd.DataFrame(fundamentals)
    filtered = microcap_filter.apply_filters(df)
    if filtered.empty:
        logger.warning("Filtered universe empty; falling back to CSV data")
        fallback = csv_loader.load_universe_from_csv(settings.universe_fallback_csv)
        return microcap_filter.apply_filters(fallback)
    return filtered

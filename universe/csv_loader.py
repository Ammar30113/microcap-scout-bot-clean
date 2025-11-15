from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)


DEFAULT_COLUMNS = ["symbol", "market_cap", "price", "avg_volume"]


def load_universe_from_csv(path: Path) -> pd.DataFrame:
    """Load fallback universe data from CSV."""

    if not path.exists():
        logger.warning("Fallback universe CSV %s does not exist", path)
        return pd.DataFrame(columns=DEFAULT_COLUMNS)
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        logger.warning("Unable to read fallback CSV %s: %s", path, exc)
        return pd.DataFrame(columns=DEFAULT_COLUMNS)
    missing = [col for col in DEFAULT_COLUMNS if col not in df.columns]
    for column in missing:
        df[column] = 0
    return df[DEFAULT_COLUMNS]

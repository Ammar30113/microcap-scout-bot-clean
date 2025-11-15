from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import pandas as pd

from core.logger import get_logger

dtype_agg = List[Dict[str, float]]
logger = get_logger(__name__)

PAIRS: Tuple[Tuple[str, str], ...] = (
    ("IWM", "URTY"),
    ("AMD", "SMH"),
    ("NVDA", "SOXX"),
)


def generate_signals(get_aggregates: Callable[[str, str, int], dtype_agg], *, limit: int = 60) -> Dict[str, Dict[str, float | str]]:
    """Return arbitrage instructions keyed by symbol."""

    signals: Dict[str, Dict[str, float | str]] = {}
    for long_symbol, short_symbol in PAIRS:
        try:
            long_df = _to_frame(get_aggregates(long_symbol, "1day", limit))
            short_df = _to_frame(get_aggregates(short_symbol, "1day", limit))
        except Exception as exc:  # pragma: no cover - network guard
            logger.warning("Pair data unavailable for %s/%s: %s", long_symbol, short_symbol, exc)
            continue
        if long_df.empty or short_df.empty:
            continue
        spread = long_df["close"].tail(limit).reset_index(drop=True) - short_df["close"].tail(limit).reset_index(drop=True)
        if spread.std() == 0 or len(spread) < 20:
            continue
        z_score = (spread.iloc[-1] - spread.mean()) / spread.std()
        confidence = min(0.9, abs(float(z_score)) / 3)
        if z_score > 2:
            signals[long_symbol] = {"action": "SELL", "confidence": confidence, "label": "etf_arbitrage"}
            signals[short_symbol] = {"action": "BUY", "confidence": confidence, "label": "etf_arbitrage"}
        elif z_score < -2:
            signals[long_symbol] = {"action": "BUY", "confidence": confidence, "label": "etf_arbitrage"}
            signals[short_symbol] = {"action": "SELL", "confidence": confidence, "label": "etf_arbitrage"}
    return signals


def _to_frame(bars: dtype_agg) -> pd.DataFrame:
    frame = pd.DataFrame(bars)
    if not frame.empty:
        frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame

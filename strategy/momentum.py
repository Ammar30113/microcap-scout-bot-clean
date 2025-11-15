from __future__ import annotations

from typing import Dict

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, SMAIndicator


def generate_signal(symbol: str, price_frame: pd.DataFrame, ml_score: float) -> Dict[str, float | str]:
    if price_frame.empty or len(price_frame) < 30:
        return {"action": "HOLD", "confidence": 0.0, "label": "insufficient_data"}

    close = price_frame["close"].astype(float)
    price = close.iloc[-1]
    sma_20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    ema_fast = EMAIndicator(close, window=12).ema_indicator().iloc[-1]
    ema_slow = EMAIndicator(close, window=26).ema_indicator().iloc[-1]

    if price > sma_20 and rsi > 55 and ema_fast > ema_slow and ml_score >= 0.60:
        confidence = min(0.95, max(ml_score, 0.60))
        return {
            "action": "BUY",
            "confidence": confidence,
            "label": "momentum",
            "tp_mult": 3.0,
            "sl_mult": 1.5,
        }
    return {"action": "HOLD", "confidence": 0.0, "label": "momentum"}

from __future__ import annotations

from typing import Dict

import pandas as pd
from ta.momentum import RSIIndicator


def generate_signal(symbol: str, price_frame: pd.DataFrame, ml_score: float) -> Dict[str, float | str]:
    if price_frame.empty or len(price_frame) < 30:
        return {"action": "HOLD", "confidence": 0.0, "label": "mean_reversion"}

    close = price_frame["close"].astype(float)
    price = close.iloc[-1]
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    rolling_std = close.rolling(window=20).std().iloc[-1]
    vwap = _compute_vwap(price_frame)
    threshold = vwap - 2 * rolling_std

    if rsi < 32 and price < threshold and ml_score >= 0.50:
        confidence = min(0.85, 0.5 + (0.5 - rsi / 100))
        return {
            "action": "BUY",
            "confidence": confidence,
            "label": "mean_reversion",
            "tp_mult": 2.0,
            "sl_mult": 1.0,
        }
    return {"action": "HOLD", "confidence": 0.0, "label": "mean_reversion"}


def _compute_vwap(frame: pd.DataFrame) -> float:
    typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3
    volume = frame["volume"].replace(0, 1)
    cumulative = (typical_price * volume).cumsum() / volume.cumsum()
    return float(cumulative.iloc[-1])

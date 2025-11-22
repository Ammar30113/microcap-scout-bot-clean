from __future__ import annotations

import datetime as dt
import os
from typing import Optional

from strategy.technicals import passes_exit_filter
from data.price_router import PriceRouter

STOP_LOSS_PCT = 0.006
TAKE_PROFIT_PCT = 0.018
MAX_POSITIONS = 5
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET_USD", 10000))
MAX_POSITION_SIZE = DAILY_BUDGET / 3
price_router = PriceRouter()


def stop_loss_price(entry_price: float, crash_mode: bool = False) -> float:
    pct = 0.005 if crash_mode else STOP_LOSS_PCT
    return round(entry_price * (1 - pct), 2)


def take_profit_price(entry_price: float, crash_mode: bool = False) -> float:
    pct = 0.015 if crash_mode else TAKE_PROFIT_PCT
    return round(entry_price * (1 + pct), 2)


def can_open_position(current_positions: int, allocation_amount: float, crash_mode: bool = False) -> bool:
    max_positions = 3 if crash_mode else MAX_POSITIONS
    max_pos_size = (DAILY_BUDGET * 0.80 / max_positions) if crash_mode else MAX_POSITION_SIZE
    return current_positions < max_positions and allocation_amount <= max_pos_size


def should_exit(position: dict, crash_mode: bool = False) -> bool:
    """
    position: {"entry_price": float, "current_price": float, "open_date": iso str, "symbol": str}
    Intraday exit profile: TP +1.8%, SL -0.6%, hard time cap at 90 minutes.
    """
    price = float(position.get("current_price", 0.0))
    entry = float(position.get("entry_price", 0.0))
    open_date = position.get("open_date") or position.get("entered_at")
    symbol = position.get("symbol")

    if not price or not entry:
        return True

    tp_pct = 0.015 if crash_mode else TAKE_PROFIT_PCT
    sl_pct = 0.005 if crash_mode else STOP_LOSS_PCT
    time_cap_minutes = 60 if crash_mode else 90

    gain = (price / entry) - 1
    if gain >= tp_pct or gain <= -sl_pct:
        return True

    if open_date:
        try:
            cleaned_date = open_date.replace("Z", "+00:00") if isinstance(open_date, str) else open_date
            opened_at = dt.datetime.fromisoformat(cleaned_date)
            minutes_held = (dt.datetime.utcnow() - opened_at).total_seconds() / 60.0
            if minutes_held >= time_cap_minutes:
                return True
        except Exception:
            return True

    if symbol:
        try:
            bars = price_router.get_aggregates(symbol, window=120)
            df = PriceRouter.aggregates_to_dataframe(bars)
            if passes_exit_filter(df):
                return True
        except Exception:
            return False
    return False

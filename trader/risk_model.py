from __future__ import annotations

from datetime import date
from typing import Any, Dict

from core.config import Settings


def atr_targets(price: float, atr: float, action: str, *, tp_mult: float = 3.0, sl_mult: float = 1.5) -> tuple[float, float]:
    atr = atr or price * 0.02
    if action == "BUY":
        tp = price + atr * tp_mult
        sl = price - atr * sl_mult
    else:
        tp = price - atr * tp_mult
        sl = price + atr * sl_mult
    return round(tp, 2), round(sl, 2)


def can_enter_trade(state: Dict[str, Any], settings: Settings) -> bool:
    today = date.today().isoformat()
    if state.get("date") != today:
        state["date"] = today
        state["daily_pnl"] = 0.0
    max_loss = settings.max_daily_loss_pct * state.get("equity", settings.initial_equity)
    return abs(state.get("daily_pnl", 0.0)) < max_loss and len(state.get("positions", [])) < settings.max_positions


def update_daily_pnl(state: Dict[str, any], pnl: float) -> None:
    state.setdefault("daily_pnl", 0.0)
    state["daily_pnl"] = float(state["daily_pnl"]) + float(pnl)

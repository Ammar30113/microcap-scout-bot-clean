from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from config import get_settings
from market_data import get_aggregates, get_price
from utils.logger import get_logger

logger = get_logger("Macro")


@dataclass
class MacroState:
    size_factor: float
    min_factor: float
    reasons: List[str] = field(default_factory=list)

    @property
    def allow_trades(self) -> bool:
        return self.size_factor >= self.min_factor


def evaluate_macro_state() -> MacroState:
    settings = get_settings()
    size_factor = 1.0
    reasons: List[str] = []

    try:
        bars = get_aggregates(settings.macro_spy_symbol, timespan=f"{settings.macro_trend_minutes}min", limit=2)
        if len(bars) >= 2:
            trend = bars[-1].close - bars[-2].close
            if trend < 0:
                size_factor *= settings.macro_spy_reduce_factor
                reasons.append("spy_trend_negative")
                logger.warning("SPY trend negative; reducing size")
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("Unable to evaluate SPY macro trend: %s", exc)

    try:
        vix_price = get_price(settings.macro_vix_symbol)
        if vix_price > settings.macro_vix_threshold:
            size_factor *= settings.macro_vix_reduce_factor
            reasons.append("vix_elevated")
            logger.warning("VIX above threshold; reducing size")
    except Exception as exc:  # pragma: no cover - network guard
        logger.warning("Unable to evaluate VIX macro filter: %s", exc)

    state = MacroState(size_factor=size_factor, min_factor=settings.macro_min_size_factor, reasons=reasons)
    if not state.allow_trades:
        logger.warning("Macro filters blocking trades: %s", ",".join(reasons) or "none")
    return state

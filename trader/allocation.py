from __future__ import annotations

from core.config import Settings


def determine_position_size(
    equity: float,
    confidence: float,
    price: float,
    atr: float,
    settings: Settings,
) -> int:
    """Calculate dynamic position size bounded by risk constraints."""

    if equity <= 0 or price <= 0:
        return 0

    normalized_confidence = max(settings.min_confidence, min(confidence, 1.0))
    base_capital = equity * settings.max_position_pct
    allocation = base_capital * normalized_confidence

    atr = atr or price * 0.02
    stop_distance = max(atr * settings.atr_multiplier, price * 0.01)
    if stop_distance <= 0:
        return 0

    qty = int(allocation / stop_distance)
    return max(qty, 0)

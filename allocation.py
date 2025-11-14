from __future__ import annotations

import math
from typing import Optional

from config import get_settings

settings = get_settings()


def calculate_quantity(price: float, stop_loss: Optional[float] = None, use_risk_model: bool = True) -> int:
    if price <= 0:
        return 0

    max_position_size = settings.daily_budget / max(settings.max_positions, 1)
    base_qty = math.floor(max_position_size / price)
    qty = max(base_qty, 0)

    if use_risk_model and stop_loss is not None and stop_loss < price:
        risk_per_trade = settings.daily_budget * settings.risk_per_trade_pct
        risk_per_share = price - stop_loss
        if risk_per_share > 0:
            risk_qty = math.floor(risk_per_trade / risk_per_share)
            if risk_qty > 0:
                qty = min(qty, risk_qty) if qty > 0 else risk_qty

    return qty

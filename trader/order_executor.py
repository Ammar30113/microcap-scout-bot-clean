from __future__ import annotations

from typing import Dict

import alpaca_trade_api as tradeapi

from core.config import get_settings
from core.logger import get_logger
from trader import allocation, portfolio_state, risk_model

logger = get_logger(__name__)
settings = get_settings()


class OrderExecutor:
    def __init__(self) -> None:
        self.client = tradeapi.REST(settings.alpaca_api_key, settings.alpaca_api_secret, settings.alpaca_base_url)
        self.state = portfolio_state.load_state(settings.portfolio_state_path, settings)

    def refresh_state(self) -> None:
        self.state = portfolio_state.load_state(settings.portfolio_state_path, settings)

    def execute(self, decision: Dict[str, float | str]) -> None:
        if decision.get("action") in {"HOLD", None}:
            return
        if not risk_model.can_enter_trade(self.state, settings):
            logger.info("Risk guard blocked trade for %s", decision.get("symbol"))
            return

        symbol = str(decision["symbol"])
        action = str(decision["action"])
        price = float(decision.get("price") or decision.get("tp") or 0.0)
        atr = float(decision.get("atr", 0.0))
        qty = allocation.determine_position_size(self.state.get("equity", settings.initial_equity), decision.get("confidence", 0.0), price, atr, settings)
        if qty <= 0:
            logger.info("Qty zero for %s, skipping", symbol)
            return

        side = "buy" if action == "BUY" else "sell"
        take_profit = float(decision.get("tp", price))
        stop_loss = float(decision.get("sl", price))

        logger.info(
            "Submitting %s order: %s qty=%s tp=%s sl=%s", side, symbol, qty, take_profit, stop_loss
        )
        order = self.client.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type="market",
            time_in_force="day",
            order_class="bracket",
            take_profit={"limit_price": round(take_profit, 2)},
            stop_loss={"stop_price": round(stop_loss, 2)},
        )
        logger.info("Order accepted %s", order)
        portfolio_state.record_trade(self.state, symbol, action, qty, price, float(decision.get("confidence", 0.0)))
        portfolio_state.save_state(settings.portfolio_state_path, self.state)

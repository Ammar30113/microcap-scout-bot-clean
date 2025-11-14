from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import alpaca_trade_api as tradeapi

from allocation import calculate_quantity
from config import get_settings
from macro import evaluate_macro_state
from market_data import get_price
from sentiment import get_sentiment
from universe import build_universe
from utils.logger import get_logger

logger = get_logger("Trading")


def _build_alpaca_client(settings) -> tradeapi.REST:
    return tradeapi.REST(
        settings.alpaca_api_key,
        settings.alpaca_api_secret,
        base_url=str(settings.alpaca_trading_url),
    )


def _compute_levels(price: float, settings) -> Dict[str, float]:
    take_profit = round(price * (1 + settings.take_profit_pct), 2)
    stop_loss = round(price * (1 - settings.stop_loss_pct), 2)
    return {"entry": round(price, 2), "take_profit": take_profit, "stop_loss": stop_loss}


def execute_trades() -> Dict[str, Any]:
    settings = get_settings()
    client = _build_alpaca_client(settings)
    macro_state = evaluate_macro_state()

    universe = build_universe()
    logger.info("Processed universe size=%s", len(universe))

    executed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    if not macro_state.allow_trades:
        logger.warning("Macro filters prevented trading; skipping run")
        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "executed": executed,
            "skipped": skipped,
            "macro": {"size_factor": macro_state.size_factor, "reasons": macro_state.reasons},
        }
        logger.info("Summary: %s", json.dumps(summary))
        return summary

    for symbol in universe:
        try:
            price = get_price(symbol)
        except RuntimeError as exc:
            logger.warning("Price unavailable for %s: %s", symbol, exc)
            skipped.append({"symbol": symbol, "reason": "price_unavailable"})
            logger.info("Decision %s action=skip reason=price_unavailable", symbol)
            continue

        sentiment = get_sentiment(symbol)
        levels = _compute_levels(price, settings)
        base_qty = calculate_quantity(price, stop_loss=levels["stop_loss"], use_risk_model=True)
        adjusted_qty = int(base_qty * macro_state.size_factor)

        if adjusted_qty < 1:
            skipped.append({"symbol": symbol, "reason": "quantity_below_one"})
            logger.info("Decision %s action=skip reason=quantity_below_one", symbol)
            continue

        try:
            client.submit_order(
                symbol=symbol,
                qty=adjusted_qty,
                side="buy",
                type="market",
                time_in_force="gtc",
                order_class="bracket",
                take_profit={"limit_price": levels["take_profit"]},
                stop_loss={"stop_price": levels["stop_loss"]},
            )
            trade_record = {
                "symbol": symbol,
                "qty": adjusted_qty,
                "entry": levels["entry"],
                "take_profit": levels["take_profit"],
                "stop_loss": levels["stop_loss"],
                "sentiment": sentiment.score,
            }
            executed.append(trade_record)
            logger.info("Decision %s action=execute qty=%s sentiment=%.2f", symbol, adjusted_qty, sentiment.score)
        except Exception as exc:  # pragma: no cover - network guard
            logger.warning("Trade submission failed for %s: %s", symbol, exc)
            skipped.append({"symbol": symbol, "reason": "order_failed"})
            logger.info("Decision %s action=skip reason=order_failed", symbol)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "executed": executed,
        "skipped": skipped,
        "macro": {"size_factor": macro_state.size_factor, "reasons": macro_state.reasons},
    }
    logger.info("Summary: %s", json.dumps(summary))
    return summary


if __name__ == "__main__":
    execute_trades()

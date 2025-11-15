from __future__ import annotations

import asyncio
import math

import pandas as pd

from core.config import get_settings
from core.logger import get_logger
from core.scheduler import Scheduler
from data.finnhub_sentiment import fetch_sentiment as fetch_finnhub_sentiment
from data.newsapi_sentiment import fetch_sentiment as fetch_news_sentiment
from data.price_router import PriceRouter
from strategy.etf_arbitrage import generate_signals as generate_arbitrage_signals
from strategy.ml_classifier import MLClassifier
from strategy.signal_router import SignalRouter
from trader.order_executor import OrderExecutor
from universe.universe_builder import build_universe

logger = get_logger(__name__)
settings = get_settings()
price_router = PriceRouter()
ml_model = MLClassifier()
signal_router = SignalRouter(ml_model)
order_executor = OrderExecutor()


async def run_trading_cycle() -> None:
    logger.info("Building universe")
    universe_df = build_universe()
    if universe_df.empty:
        logger.warning("Universe is empty; skipping run")
        return

    try:
        etf_reference = PriceRouter.aggregates_to_dataframe(price_router.get_aggregates("IWM", settings.default_timespan, 120))
    except Exception as exc:
        logger.warning("Unable to fetch ETF reference data: %s", exc)
        etf_reference = pd.DataFrame()

    arbitrage_map = generate_arbitrage_signals(price_router.get_aggregates)

    executed = 0
    evaluated = 0
    for _, row in universe_df.iterrows():
        symbol = row["symbol"]
        evaluated += 1
        try:
            bars = price_router.get_aggregates(symbol, settings.default_timespan, 120)
        except Exception as exc:  # pragma: no cover - network guard
            logger.warning("Aggregates unavailable for %s: %s", symbol, exc)
            continue
        price_frame = PriceRouter.aggregates_to_dataframe(bars)
        if price_frame.empty:
            continue

        sentiments = {
            "finnhub": fetch_finnhub_sentiment(symbol),
            "newsapi": fetch_news_sentiment(symbol),
        }
        try:
            liquidity_hint = float(row.get("avg_volume", 0.0)) / 1_000_000.0
        except (TypeError, ValueError):
            liquidity_hint = 0.0
        if math.isnan(liquidity_hint):
            liquidity_hint = 0.0
        decision = signal_router.evaluate_symbol(
            symbol,
            price_frame,
            etf_reference,
            sentiments,
            arbitrage_map,
            liquidity_hint,
        )
        if decision["action"] == "HOLD":
            continue

        try:
            decision["price"] = price_router.get_price(symbol)
        except Exception:
            decision["price"] = float(price_frame["close"].iloc[-1])

        order_executor.execute(decision)
        executed += 1

    logger.info("Cycle complete — evaluated %s symbols, executed %s trades", evaluated, executed)


def main() -> None:
    scheduler = Scheduler()
    scheduler.register("microcap-cycle", run_trading_cycle, settings.scheduler_interval_seconds)
    asyncio.run(scheduler.start())


if __name__ == "__main__":
    main()

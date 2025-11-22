import logging
import time

from universe.universe_builder import get_universe
from strategy.signal_router import route_signals
from trader.allocation import allocate_positions
from trader.order_executor import execute_trades, close_position, list_positions
from trader import risk_model
from data.price_router import PriceRouter
from strategy.crash_detector import is_crash_mode

logging.basicConfig(level=logging.INFO, format="%Y-%m-%d %H:%M:%S | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)
price_router = PriceRouter()


def microcap_cycle():
    while True:
        start = time.time()
        try:
            crash, drop = is_crash_mode()
            logger.info("Crash mode = %s (SPY 5min drop = %.3f)", crash, drop)
            logger.info("=== Crash Mode %s ===", "ACTIVE" if crash else "OFF")

            universe = get_universe()
            if not universe:
                logger.info("Universe empty; skipping cycle")
                continue

            signals = route_signals(universe, crash_mode=crash)
            if not signals:
                logger.info("No signals generated; skipping allocations")
                continue
            allocations = allocate_positions(signals, crash_mode=crash)

            # Enforce max position caps before submitting
            filtered_allocations = {}
            open_positions = list_positions()
            open_count = len(open_positions)
            for symbol, shares in allocations.items():
                try:
                    price = price_router.get_price(symbol)
                except Exception as exc:  # pragma: no cover - network guard
                    logger.warning("Skipping %s for risk check; price unavailable: %s", symbol, exc)
                    continue
                notional = shares * price
                if risk_model.can_open_position(open_count + len(filtered_allocations), notional, crash_mode=crash):
                    filtered_allocations[symbol] = shares
                else:
                    logger.info("Risk cap blocked %s (notional %.2f)", symbol, notional)

            execute_trades(filtered_allocations, crash_mode=crash)

            # Exit checks for existing positions
            for pos in list_positions():
                try:
                    current_price = float(pos.current_price)
                    entry_price = float(pos.avg_entry_price)
                except Exception:
                    continue
                position_payload = {
                    "symbol": pos.symbol,
                    "current_price": current_price,
                    "entry_price": entry_price,
                    "open_date": getattr(pos, "current_price_timestamp", None) or None,
                }
                if risk_model.should_exit(position_payload, crash_mode=crash):
                    close_position(pos.symbol)

            logger.info("=== Cycle Complete ===")
        except Exception as exc:  # pragma: no cover - defensive loop
            logger.exception("Cycle failed: %s", exc)
        finally:
            elapsed = time.time() - start
            sleep_for = max(300 - elapsed, 0)
            time.sleep(sleep_for)


if __name__ == "__main__":
    microcap_cycle()

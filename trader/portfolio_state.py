from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict

from core.config import Settings
from core.logger import get_logger

logger = get_logger(__name__)


DEFAULT_STATE = {
    "date": date.today().isoformat(),
    "equity": 100000.0,
    "daily_pnl": 0.0,
    "positions": [],
}


def load_state(path: Path, settings: Settings) -> Dict[str, Any]:
    if not path.exists():
        return reset_state(path, settings, warn=True)
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Portfolio state unreadable — resetting.")
        state = reset_state(path, settings, warn=False)
        return state
    if not isinstance(state, dict) or not state:
        logger.warning("Portfolio state unreadable — resetting.")
        state = reset_state(path, settings, warn=False)
        return state
    ensure_today_state(state, settings)
    return state


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def ensure_today_state(state: Dict[str, Any], settings: Settings) -> None:
    today = date.today().isoformat()
    if state.get("date") != today:
        state["date"] = today
        state["daily_pnl"] = 0.0
        state.setdefault("equity", settings.initial_equity)
        state["positions"] = []


def reset_state(path: Path, settings: Settings, warn: bool = False) -> Dict[str, Any]:
    if warn:
        logger.warning("Portfolio state unreadable — resetting.")
    state = {"positions": {}, "last_updated": datetime.utcnow().isoformat()}
    save_state(path, state)
    return state


def record_trade(
    state: Dict[str, Any],
    symbol: str,
    action: str,
    qty: int,
    price: float,
    confidence: float,
) -> None:
    trade = {
        "symbol": symbol,
        "action": action,
        "qty": qty,
        "price": price,
        "confidence": confidence,
    }
    positions = state.setdefault("positions", [])
    if isinstance(positions, dict):
        positions = state["positions"] = []
    positions.append(trade)
    logger.info("Recorded trade %s", trade)

from __future__ import annotations

from typing import Dict

import pandas as pd

from strategy import mean_reversion, momentum
from strategy.ml_classifier import MLClassifier, build_features
from trader import risk_model


class SignalRouter:
    def __init__(self, ml_model: MLClassifier) -> None:
        self.ml_model = ml_model

    def evaluate_symbol(
        self,
        symbol: str,
        price_frame: pd.DataFrame,
        etf_frame: pd.DataFrame,
        sentiments: Dict[str, float],
        arbitrage_map: Dict[str, Dict[str, float | str]],
        liquidity_hint: float,
    ) -> Dict[str, float | str]:
        features = build_features(
            price_frame,
            etf_frame,
            finnhub_sentiment=sentiments.get("finnhub", 0.0),
            newsapi_sentiment=sentiments.get("newsapi", 0.0),
            liquidity_hint=liquidity_hint,
        )
        ml_score = self.ml_model.predict(features)
        signals = [
            momentum.generate_signal(symbol, price_frame, ml_score),
            mean_reversion.generate_signal(symbol, price_frame, ml_score),
            arbitrage_map.get(symbol, {"action": "HOLD", "confidence": 0.0, "label": "etf_arbitrage"}),
        ]
        decision = self._merge_signals(symbol, price_frame, features, signals)
        decision["ml_score"] = ml_score
        return decision

    def _merge_signals(
        self,
        symbol: str,
        price_frame: pd.DataFrame,
        features: Dict[str, float],
        signals: list[Dict[str, float | str]],
    ) -> Dict[str, float | str]:
        best = {"action": "HOLD", "confidence": 0.0, "label": "none"}
        for signal in signals:
            if signal.get("action") == "HOLD":
                continue
            if float(signal.get("confidence", 0.0)) > float(best.get("confidence", 0.0)):
                best = signal

        price = float(price_frame["close"].iloc[-1]) if not price_frame.empty else 0.0
        atr = float(features.get("atr", price * 0.02))
        if best["action"] == "HOLD" or price <= 0:
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": 0.0,
                "tp": price,
                "sl": price,
                "price": price,
                "atr": atr,
            }

        tp_mult = float(best.get("tp_mult", 3.0))
        sl_mult = float(best.get("sl_mult", 1.5))
        tp, sl = risk_model.atr_targets(price, atr, str(best.get("action")), tp_mult=tp_mult, sl_mult=sl_mult)
        return {
            "symbol": symbol,
            "action": best["action"],
            "confidence": float(best.get("confidence", 0.0)),
            "tp": tp,
            "sl": sl,
            "price": price,
            "atr": atr,
        }

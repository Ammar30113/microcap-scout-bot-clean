from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import AliasChoices, AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    alpaca_api_key: str = Field(default="", validation_alias=AliasChoices("ALPACA_API_KEY", "APCA_API_KEY_ID"))
    alpaca_api_secret: str = Field(default="", validation_alias=AliasChoices("ALPACA_API_SECRET", "APCA_API_SECRET_KEY"))
    alpaca_trading_url: AnyHttpUrl = Field(
        default="https://paper-api.alpaca.markets",
        validation_alias=AliasChoices("ALPACA_TRADING_BASE_URL", "APCA_API_BASE_URL"),
    )
    alpaca_data_url: AnyHttpUrl = Field(
        default="https://data.alpaca.markets",
        validation_alias=AliasChoices("ALPACA_DATA_BASE_URL", "APCA_API_DATA_URL"),
    )

    massive_api_key: Optional[str] = Field(default=None, validation_alias="MASSIVE_API_KEY")
    twelvedata_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("TWELVEDATA_API_KEY", "TWELVEDATA_KEY"))
    alpha_vantage_key: Optional[str] = Field(default=None, validation_alias="ALPHAVANTAGE_KEY")
    newsapi_key: Optional[str] = Field(default=None, validation_alias="NEWSAPI_KEY")
    enable_twitter: bool = Field(default=False, validation_alias="ENABLE_TWITTER")

    daily_budget: float = Field(default=10000.0, validation_alias="DAILY_BUDGET_USD")
    max_positions: int = Field(default=10, validation_alias="MAX_POSITIONS")
    risk_per_trade_pct: float = Field(default=0.02, validation_alias="RISK_PER_TRADE_PCT")
    take_profit_pct: float = Field(default=0.04, validation_alias="TAKE_PROFIT_PCT")
    stop_loss_pct: float = Field(default=0.02, validation_alias="STOP_LOSS_PCT")

    universe_symbols: List[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "TSLA"], validation_alias="UNIVERSE_SYMBOLS")

    macro_spy_symbol: str = Field(default="SPY", validation_alias="MACRO_SPY_SYMBOL")
    macro_vix_symbol: str = Field(default="VIX", validation_alias="MACRO_VIX_SYMBOL")
    macro_trend_minutes: int = Field(default=30, validation_alias="MACRO_TREND_MINUTES")
    macro_vix_threshold: float = Field(default=25.0, validation_alias="MACRO_VIX_THRESHOLD")
    macro_spy_reduce_factor: float = Field(default=0.5, validation_alias="MACRO_SPY_REDUCE_FACTOR")
    macro_vix_reduce_factor: float = Field(default=0.5, validation_alias="MACRO_VIX_REDUCE_FACTOR")
    macro_min_size_factor: float = Field(default=0.2, validation_alias="MACRO_MIN_SIZE_FACTOR")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def symbols(self) -> List[str]:
        if isinstance(self.universe_symbols, list):
            return [symbol.strip().upper() for symbol in self.universe_symbols if symbol]
        if isinstance(self.universe_symbols, str):
            return [token.strip().upper() for token in self.universe_symbols.split(",") if token.strip()]
        return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

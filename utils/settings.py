from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    finviz_api_key: Optional[str] = Field(default=None, validation_alias="FINVIZ_API_KEY")
    stockdata_api_key: Optional[str] = Field(default=None, validation_alias="STOCKDATA_API_KEY")
    alpaca_api_key: Optional[str] = Field(default=None, validation_alias="ALPACA_API_KEY")
    alpaca_secret_key: Optional[str] = Field(default=None, validation_alias="ALPACA_SECRET_KEY")
    alpaca_base_url: AnyHttpUrl = Field(
        default="https://data.alpaca.markets/v2",
        validation_alias="ALPACA_BASE_URL",
    )
    default_symbol: str = Field(default="SPY", validation_alias="DEFAULT_SYMBOL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

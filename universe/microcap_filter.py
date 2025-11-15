from __future__ import annotations

import pandas as pd

MICROCAP_CEILING = 2_000_000_000  # $2B
MIN_PRICE = 2.0
MIN_AVG_VOLUME = 100_000


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    numeric_df = df.copy()
    numeric_df["market_cap"] = pd.to_numeric(numeric_df["market_cap"], errors="coerce")
    numeric_df["price"] = pd.to_numeric(numeric_df["price"], errors="coerce")
    numeric_df["avg_volume"] = pd.to_numeric(numeric_df["avg_volume"], errors="coerce")
    filtered = numeric_df[
        (numeric_df["market_cap"] < MICROCAP_CEILING)
        & (numeric_df["price"] > MIN_PRICE)
        & (numeric_df["avg_volume"] > MIN_AVG_VOLUME)
    ]
    filtered = filtered.dropna(subset=["symbol"]).copy()
    filtered["symbol"] = filtered["symbol"].str.upper()
    return filtered.sort_values("market_cap")

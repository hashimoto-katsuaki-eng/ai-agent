from __future__ import annotations

from datetime import date

import pandas as pd


def make_trending_bars(
    trading_dates: list[date] | pd.DatetimeIndex,
    codes: tuple[str, ...] = ("1000",),
    breakout_index: int = 260,
) -> pd.DataFrame:
    rows = []
    for code_index, code in enumerate(codes):
        for index, trading_date in enumerate(trading_dates):
            close = 1000 + code_index * 50 + index * 0.3
            if index == breakout_index:
                close += 2
            high = close + 0.1
            low = close - 0.2
            volume = 100.0
            if index == breakout_index:
                volume = 500.0
            rows.append(
                {
                    "date": pd.Timestamp(trading_date),
                    "code": code,
                    "open": close - 0.1,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "turnover": 1_000_000_000.0,
                    "upper_limit": 0.0,
                }
            )
    return pd.DataFrame(rows)


def default_screening_config() -> dict[str, float | int]:
    return {
        "liquidity_window": 20,
        "min_average_turnover": 500_000_000,
        "volume_window": 20,
        "min_volume_ratio": 2.0,
        "breakout_window": 20,
        "ma_short_window": 25,
        "ma_long_window": 75,
        "max_ma_deviation": 0.25,
        "high_52w_window": 250,
        "high_52w_bonus": 0.1,
    }

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from fxbt.signals import compute_indicators, generate_signals


def signal_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0, 10.0],
            "high": [12.0, 10.0, 10.0, 10.0],
            "low": [9.8, 7.8, 9.5, 9.5],
            "close": [12.0, 8.0, 12.0, 8.0],
            "prior_high": [11.0, 10.0, 11.0, 10.0],
            "prior_low": [9.0, 9.0, 9.0, 9.0],
            "ma_short": [11.5, 8.5, 11.5, 8.5],
            "ma_long": [10.5, 9.5, 10.5, 9.5],
            "atr": [1.0, 1.0, 0.5, 1.0],
            "range": [0.2, 0.2, 2.0, 0.2],
            "ready": [True, True, True, True],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )


def test_prior_high_uses_only_previous_lookback_rows() -> None:
    daily = pd.DataFrame(
        {
            "open": np.arange(1.0, 26.0),
            "high": np.arange(2.0, 27.0),
            "low": np.arange(0.0, 25.0),
            "close": np.arange(1.0, 26.0),
        },
        index=pd.date_range("2024-01-01", periods=25, freq="D"),
    )

    indicators = compute_indicators(daily, {"breakout_lookback": 20, "ma_short": 2, "ma_long": 3, "atr_period": 2})

    assert np.isnan(indicators["prior_high"].iloc[19])
    assert indicators["prior_high"].iloc[20] == 21
    assert indicators["prior_high"].iloc[20] != daily["high"].iloc[20]


def test_generate_signals_applies_breakout_trend_overheat_and_direction_flags() -> None:
    ind = signal_frame()
    config = {"overheat_atr_mult": 3, "enable_long": True, "enable_short": True}

    signals = generate_signals(ind, config)

    assert signals.tolist() == [1, -1, 0, -1]
    assert generate_signals(ind, {**config, "enable_long": False}).tolist() == [0, -1, 0, -1]
    assert generate_signals(ind, {**config, "enable_short": False}).tolist() == [1, 0, 0, 0]


def test_future_changes_and_truncation_do_not_change_past_indicators_or_signals() -> None:
    rng = np.random.default_rng(239)
    dates = pd.bdate_range("2019-01-01", periods=260)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
    daily = pd.DataFrame(
        {
            "open": close * (1 + rng.normal(0, 0.002, len(dates))),
            "high": close * (1 + rng.uniform(0.002, 0.02, len(dates))),
            "low": close * (1 - rng.uniform(0.002, 0.02, len(dates))),
            "close": close,
        },
        index=dates,
    )
    config = {
        "breakout_lookback": 20,
        "ma_short": 25,
        "ma_long": 75,
        "atr_period": 14,
        "overheat_atr_mult": 3,
    }
    original_indicators = compute_indicators(daily, config)
    original_signals = generate_signals(original_indicators, config)

    for t in (90, 145, 220):
        cutoff = dates[t]
        changed = daily.copy()
        future = changed.index > cutoff
        changed.loc[future, ["open", "high", "low", "close"]] *= 10
        changed_indicators = compute_indicators(changed, config)
        changed_signals = generate_signals(changed_indicators, config)
        truncated_indicators = compute_indicators(daily.loc[:cutoff], config)
        truncated_signals = generate_signals(truncated_indicators, config)

        assert_frame_equal(original_indicators.loc[:cutoff], changed_indicators.loc[:cutoff])
        assert_series_equal(original_signals.loc[:cutoff], changed_signals.loc[:cutoff])
        assert_frame_equal(original_indicators.loc[:cutoff], truncated_indicators)
        assert_series_equal(original_signals.loc[:cutoff], truncated_signals)

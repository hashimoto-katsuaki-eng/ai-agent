"""先読みを避けたスクリーニング特徴量と日次ランキング。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from jpbt.jquants import normalize_daily_bars


def build_feature_panel(
    bars: pd.DataFrame,
    trading_dates: Sequence[pd.Timestamp | str],
    config: Mapping[str, float | int],
) -> pd.DataFrame:
    """営業日ごとに並べ、当日までの情報だけでスクリーニング特徴量を計算する。"""
    normalized = normalize_daily_bars(bars)
    if normalized.empty:
        return pd.DataFrame()

    calendar = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique()
    calendar = calendar.sort_values()
    rows: list[pd.DataFrame] = []
    for code, group in normalized.groupby("code", sort=False):
        group = group.drop_duplicates("date", keep="last").set_index("date")
        present_dates = group.index.intersection(calendar)
        if present_dates.empty:
            continue
        date_range = calendar[(calendar >= present_dates.min()) & (calendar <= present_dates.max())]
        data = group.reindex(date_range).copy()
        data["code"] = code
        close = data["close"]
        high = data["high"]
        volume = data["volume"]
        turnover = data["turnover"]
        data["average_turnover"] = turnover.rolling(
            int(config["liquidity_window"]), min_periods=int(config["liquidity_window"])
        ).mean()
        prior_volume_mean = volume.shift(1).rolling(
            int(config["volume_window"]), min_periods=int(config["volume_window"])
        ).mean()
        data["volume_ratio"] = volume.div(prior_volume_mean.where(prior_volume_mean > 0))
        data["prior_20d_high"] = high.shift(1).rolling(
            int(config["breakout_window"]),
            min_periods=int(config["breakout_window"]),
        ).max()
        data["breakout_margin"] = close.div(data["prior_20d_high"]).sub(1)
        data["ma_short"] = close.rolling(
            int(config["ma_short_window"]), min_periods=int(config["ma_short_window"])
        ).mean()
        data["ma_long"] = close.rolling(
            int(config["ma_long_window"]), min_periods=int(config["ma_long_window"])
        ).mean()
        data["ma_deviation"] = close.div(data["ma_short"]).sub(1)
        data["prior_52w_high"] = high.shift(1).rolling(
            int(config["high_52w_window"]),
            min_periods=int(config["high_52w_window"]),
        ).max()
        data["is_52w_high"] = close.gt(data["prior_52w_high"])
        data["date"] = data.index
        rows.append(data.reset_index(drop=True))

    if not rows:
        return pd.DataFrame()
    panel = pd.concat(rows, ignore_index=True)
    panel = apply_signal_conditions(panel, config)
    daily_ranks = panel.loc[panel["signal"]].groupby("date", sort=False)
    panel["volume_percentile"] = np.nan
    panel["breakout_percentile"] = np.nan
    panel.loc[panel["signal"], "volume_percentile"] = daily_ranks[
        "volume_ratio"
    ].rank(method="average", pct=True).to_numpy()
    panel.loc[panel["signal"], "breakout_percentile"] = daily_ranks[
        "breakout_margin"
    ].rank(method="average", pct=True).to_numpy()
    panel["score"] = np.nan
    passing = panel["signal"]
    panel.loc[passing, "score"] = (
        panel.loc[passing, ["volume_percentile", "breakout_percentile"]].mean(axis=1)
        + panel.loc[passing, "is_52w_high"].astype(float)
        * float(config["high_52w_bonus"])
    )
    panel["score_rank"] = np.nan
    panel.loc[passing, "score_rank"] = (
        panel.loc[passing]
        .groupby("date", sort=False)["score"]
        .rank(method="first", ascending=False)
    )
    return panel.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def apply_signal_conditions(
    features: pd.DataFrame, config: Mapping[str, float | int]
) -> pd.DataFrame:
    """各スクリーニング条件を境界値込みで判定する。"""
    result = features.copy()
    result["liquidity_pass"] = result["average_turnover"].ge(
        float(config["min_average_turnover"])
    )
    result["volume_surge_pass"] = result["volume_ratio"].ge(
        float(config["min_volume_ratio"])
    )
    result["breakout_pass"] = result["close"].gt(result["prior_20d_high"])
    result["trend_pass"] = result["close"].gt(result["ma_short"]) & result[
        "ma_short"
    ].gt(result["ma_long"])
    result["not_overheated_pass"] = result["ma_deviation"].le(
        float(config["max_ma_deviation"])
    )
    condition_columns = [
        "liquidity_pass",
        "volume_surge_pass",
        "breakout_pass",
        "trend_pass",
        "not_overheated_pass",
    ]
    result[condition_columns] = result[condition_columns].fillna(False).astype(bool)
    result["is_52w_high"] = result["is_52w_high"].fillna(False).astype(bool)
    result["signal"] = result[condition_columns].all(axis=1)
    return result


def select_top_n(signals: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """日ごとにスコア降順、銘柄コード昇順で上位N銘柄を返す。"""
    if signals.empty:
        return signals.copy()
    ordered = signals.sort_values(
        ["date", "score", "code"],
        ascending=[True, False, True],
        kind="stable",
    )
    return ordered.groupby("date", sort=False, group_keys=False).head(top_n).copy()

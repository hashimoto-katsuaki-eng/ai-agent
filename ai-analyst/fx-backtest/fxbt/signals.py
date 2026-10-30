"""指標とシグナル判定。すべて当日終値までのデータだけで計算する（先読みなし）。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int) -> pd.Series:
    """Wilder 方式の ATR。最初の n 本の TR 平均を初期値にし、以降は再帰平滑化。"""
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    tr = tr.to_numpy(dtype="float64")
    atr = np.full(len(tr), np.nan)
    if len(tr) >= n:
        atr[n - 1] = tr[:n].mean()
        for i in range(n, len(tr)):
            atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return pd.Series(atr, index=close.index)


def compute_indicators(daily: pd.DataFrame, sc: dict) -> pd.DataFrame:
    lb = int(sc.get("breakout_lookback", 20))
    df = daily[["open", "high", "low", "close"]].copy()
    # 前日までの lb 日高値/安値 = t-lb 〜 t-1（当日を含めない）
    df["prior_high"] = df["high"].shift(1).rolling(lb, min_periods=lb).max()
    df["prior_low"] = df["low"].shift(1).rolling(lb, min_periods=lb).min()
    # 移動平均は当日終値を含む
    df["ma_short"] = df["close"].rolling(int(sc.get("ma_short", 25))).mean()
    df["ma_long"] = df["close"].rolling(int(sc.get("ma_long", 75))).mean()
    df["atr"] = wilder_atr(df["high"], df["low"], df["close"], int(sc.get("atr_period", 14)))
    df["range"] = df["high"] - df["low"]
    df["ready"] = df[["prior_high", "prior_low", "ma_short", "ma_long", "atr"]].notna().all(axis=1)
    return df


def generate_signals(ind: pd.DataFrame, sc: dict) -> pd.Series:
    """+1=買い, -1=売り, 0=なし。シグナル日 t の終値時点で判定する。"""
    c = ind["close"]
    overheat = ind["range"] > float(sc.get("overheat_atr_mult", 3.0)) * ind["atr"]
    ok = ind["ready"] & ~overheat
    long = ok & (c > ind["prior_high"]) & (c > ind["ma_short"]) & (ind["ma_short"] > ind["ma_long"])
    short = ok & (c < ind["prior_low"]) & (c < ind["ma_short"]) & (ind["ma_short"] < ind["ma_long"])
    sig = pd.Series(0, index=ind.index, dtype="int64")
    if sc.get("enable_long", True):
        sig[long] = 1
    if sc.get("enable_short", True):
        sig[short] = -1
    return sig

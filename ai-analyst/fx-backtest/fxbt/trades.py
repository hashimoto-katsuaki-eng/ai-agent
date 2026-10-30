"""1 トレード単位の損益評価（資金管理なし、pips ベース）。

価格データは BID 足。買いは ASK（= BID + スプレッド）で入って BID で出る。
売りは BID で入って ASK で買い戻す。損切りはそれぞれ約定側の価格で判定する。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TradeParams:
    holding_days: int
    stop_atr_mult: float
    pip: float
    spread_pips: float = 0.0
    take_profit_atr_mult: float | None = None
    swap_long_pips: float = 0.0
    swap_short_pips: float = 0.0
    triple_swap_weekday: int = 2


def simulate_trade(
    o: np.ndarray,
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    weekdays: np.ndarray,
    t: int,
    direction: int,
    atr: float,
    p: TradeParams,
) -> dict | None:
    """シグナル日 t のトレードを評価する。t+N が存在しなければ None。

    エントリー: t+1 の始値。保有 1 日目 = t+1、N 日目 = t+N の終値でエグジット。
    損切り: 足の始値が損切り価格を越えていれば（窓開け）始値で約定、
    足の途中で届けば損切り価格で約定。利確（任意）と同じ足で両方届く場合は損切りを優先する。
    """
    n = p.holding_days
    e, last = t + 1, t + n
    if last >= len(o) or not np.isfinite(atr) or atr <= 0:
        return None
    spread = p.spread_pips * p.pip
    dist = p.stop_atr_mult * atr
    tp_dist = None if p.take_profit_atr_mult is None else p.take_profit_atr_mult * atr
    s = 1 if direction > 0 else -1
    # 約定側の価格（買い: BID で決済、売り: ASK で決済）
    adj = 0.0 if s > 0 else spread
    entry = o[e] + spread if s > 0 else o[e]
    stop = entry - s * dist
    tp = None if tp_dist is None else entry + s * tp_dist

    exit_idx, exit_price, reason = last, None, "time"
    worst = 0.0
    for d in range(e, last + 1):
        od, hd, ld, cd = o[d] + adj, h[d] + adj, l[d] + adj, c[d] + adj
        if d > e and s * (od - stop) <= 0:
            exit_idx, exit_price, reason = d, od, "stop_gap"
            worst = max(worst, s * (entry - od))
            break
        if d > e and tp is not None and s * (od - tp) >= 0:
            exit_idx, exit_price, reason = d, od, "take_profit_gap"
            worst = max(worst, s * (entry - od))
            break
        adverse = ld if s > 0 else hd
        favorable = hd if s > 0 else ld
        hit_stop = s * (adverse - stop) <= 0
        hit_tp = tp is not None and s * (favorable - tp) >= 0
        if hit_stop:
            exit_idx, exit_price, reason = d, stop, "stop"
            worst = max(worst, s * (entry - stop))
            break
        worst = max(worst, s * (entry - adverse))
        if hit_tp:
            exit_idx, exit_price, reason = d, tp, "take_profit"
            break
        if d == last:
            exit_idx, exit_price, reason = d, cd, "time"

    pnl = s * (exit_price - entry)
    swap_days = int(sum(3 if weekdays[d] == p.triple_swap_weekday else 1 for d in range(e, exit_idx)))
    swap_rate = p.swap_long_pips if s > 0 else p.swap_short_pips
    swap_pips = swap_days * swap_rate
    pnl_pips = pnl / p.pip
    return {
        "direction": "long" if s > 0 else "short",
        "entry_idx": e,
        "exit_idx": exit_idx,
        "entry_price": entry,
        "exit_price": exit_price,
        "stop_price": stop,
        "atr": atr,
        "pnl_pips": pnl_pips,
        "swap_days": swap_days,
        "swap_pips": swap_pips,
        "pnl_pips_swap": pnl_pips + swap_pips,
        "mae_pips": max(worst, 0.0) / p.pip,
        "exit_reason": reason,
        "bars_held": exit_idx - e + 1,
    }


def evaluate_all(ind: pd.DataFrame, p: TradeParams, directions: tuple[int, ...] = (1, -1)) -> pd.DataFrame:
    """指標が揃っている全日について、各方向にエントリーした場合の結果を計算する。

    ルールのトレードはこの表のうちシグナルが出た行、ランダムエントリーの母集団はこの表全体。
    """
    o, h, l, c = (ind[k].to_numpy(dtype="float64") for k in ("open", "high", "low", "close"))
    atr = ind["atr"].to_numpy(dtype="float64")
    ready = ind["ready"].to_numpy(dtype=bool)
    weekdays = ind.index.dayofweek.to_numpy()
    dates = ind.index
    rows = []
    for t in np.flatnonzero(ready):
        for direction in directions:
            r = simulate_trade(o, h, l, c, weekdays, int(t), direction, atr[t], p)
            if r is None:
                continue
            r["signal_idx"] = int(t)
            r["signal_date"] = dates[t]
            r["entry_date"] = dates[r["entry_idx"]]
            r["exit_date"] = dates[r["exit_idx"]]
            rows.append(r)
    cols = [
        "signal_date",
        "entry_date",
        "exit_date",
        "direction",
        "entry_price",
        "exit_price",
        "stop_price",
        "atr",
        "pnl_pips",
        "swap_days",
        "swap_pips",
        "pnl_pips_swap",
        "mae_pips",
        "exit_reason",
        "bars_held",
        "signal_idx",
        "entry_idx",
        "exit_idx",
    ]
    return pd.DataFrame(rows, columns=cols)

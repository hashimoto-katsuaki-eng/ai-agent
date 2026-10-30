"""ランダムエントリーとの比較（モンテカルロ）。"""

from __future__ import annotations

import numpy as np
import pandas as pd

VALUE_COLS = ("pnl_pips", "pnl_pips_swap")


def random_benchmark(
    rule: pd.DataFrame,
    pool: pd.DataFrame,
    n_runs: int,
    rng: np.random.Generator,
    alpha: float = 0.05,
) -> dict:
    """ルールと同じ (通貨ペア, 方向) ごとの件数だけ、同じ期間の候補日からランダムに選んでエントリーする。

    保有日数・損切り・スプレッド・スワップは同じ条件。1 回の試行 = ルールと同件数のトレード。
    p_value = ランダム試行の平均損益がルール以上になった割合（+1 補正）。
    """
    out: dict = {"n_trades": len(rule), "n_runs": int(n_runs)}
    if len(rule) == 0:
        return out
    total = len(rule)
    sums = {v: np.zeros(n_runs) for v in VALUE_COLS}
    wins = np.zeros(n_runs)
    for (pair, direction), grp in sorted(rule.groupby(["pair", "direction"]), key=lambda x: x[0]):
        cand = pool[(pool["pair"] == pair) & (pool["direction"] == direction)]
        if cand.empty:
            raise ValueError(f"ランダム母集団が空です: {pair} {direction}")
        idx = rng.integers(0, len(cand), size=(n_runs, len(grp)))
        for v in VALUE_COLS:
            arr = cand[v].to_numpy()[idx]
            sums[v] += arr.sum(axis=1)
            if v == "pnl_pips":
                wins += (arr > 0).sum(axis=1)
    for v in VALUE_COLS:
        means = sums[v] / total
        rule_mean = float(rule[v].mean())
        p_value = (int((means >= rule_mean).sum()) + 1) / (n_runs + 1)
        out[v] = {
            "rule_mean": rule_mean,
            "random_mean": float(means.mean()),
            "random_p05": float(np.percentile(means, 5)),
            "random_p50": float(np.percentile(means, 50)),
            "random_p95": float(np.percentile(means, 95)),
            "p_value": p_value,
            "beats_random": bool(p_value < alpha),
        }
    out["rule_win_rate"] = float((rule["pnl_pips"] > 0).mean())
    out["random_win_rate"] = float((wins / total).mean())
    return out

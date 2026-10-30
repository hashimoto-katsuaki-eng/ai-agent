"""集計と fx_summary.md の生成。"""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIOD_LABEL = {"first": "前半（条件調整用）", "second": "後半（検証用・主結果）"}


def trade_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"取引回数": 0}
    return {
        "取引回数": len(df),
        "勝率": float((df["pnl_pips"] > 0).mean()),
        "平均pips": float(df["pnl_pips"].mean()),
        "中央値pips": float(df["pnl_pips"].median()),
        "平均pips(スワップ込)": float(df["pnl_pips_swap"].mean()),
        "中央値pips(スワップ込)": float(df["pnl_pips_swap"].median()),
        "平均円/1万通貨": float(df["pnl_jpy_10k"].mean()),
        "中央値円/1万通貨": float(df["pnl_jpy_10k"].median()),
        "平均円/1万通貨(スワップ込)": float(df["pnl_jpy_10k_swap"].mean()),
        "平均最大逆行pips": float(df["mae_pips"].mean()),
        "最大逆行pips(最大)": float(df["mae_pips"].max()),
        "損切り率": float(df["exit_reason"].isin(["stop", "stop_gap"]).mean()),
    }


def group_stats(df: pd.DataFrame, key) -> pd.DataFrame:
    rows = []
    for k, g in df.groupby(key, sort=True):
        rows.append({"区分": k, **trade_stats(g)})
    return pd.DataFrame(rows)


def fmt(v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "はい" if v else "いいえ"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    if isinstance(v, (float, np.floating)):
        if not np.isfinite(v):
            return "-"
        return f"{v:,.2f}"
    if isinstance(v, pd.Period):
        return str(v)
    return str(v)


def pct(v: float) -> str:
    return "-" if v is None or not np.isfinite(v) else f"{v * 100:.1f}%"


def md_table(rows: list[dict] | pd.DataFrame, pct_cols: tuple[str, ...] = ()) -> str:
    if isinstance(rows, pd.DataFrame):
        rows = rows.to_dict("records")
    if not rows:
        return "（該当なし）\n"
    cols = list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(pct(r.get(c)) if c in pct_cols else fmt(r.get(c, "")) for c in cols) + " |")
    return "\n".join(out) + "\n"


PCT_COLS = ("勝率", "損切り率", "年率リターン", "最大DD%", "総リターン", "ランダム勝率")


def stats_rows(trades: pd.DataFrame, periods=("second", "first")) -> list[dict]:
    rows = []
    for period in periods:
        for n, g in trades[trades["period"] == period].groupby("holding_days"):
            rows.append({"期間": PERIOD_LABEL[period], "保有日数": int(n), **trade_stats(g)})
    return rows


def bench_rows(bench: dict, periods=("second", "first")) -> list[dict]:
    rows = []
    for (period, n), b in sorted(bench.items(), key=lambda x: (x[0][0] != "second", x[0][1])):
        if period not in periods or "pnl_pips" not in b:
            continue
        for v, label in (("pnl_pips", "スワップ除く"), ("pnl_pips_swap", "スワップ込")):
            r = b[v]
            rows.append(
                {
                    "期間": PERIOD_LABEL[period],
                    "保有日数": n,
                    "損益": label,
                    "取引回数": b["n_trades"],
                    "ルール平均pips": r["rule_mean"],
                    "ランダム平均pips": r["random_mean"],
                    "ランダム5%点": r["random_p05"],
                    "ランダム95%点": r["random_p95"],
                    "p値": r["p_value"],
                    "ランダムに勝った": r["beats_random"],
                    "ルール勝率": b["rule_win_rate"],
                    "ランダム勝率": b["random_win_rate"],
                }
            )
    return rows


def portfolio_row(label: dict, st: dict) -> dict:
    sk = st.get("skips", {})
    return {
        **label,
        "取引数": st.get("n_trades", 0),
        "最終資産": st.get("final_equity"),
        "総損益": st.get("total_pnl"),
        "年率リターン": st.get("annual_return", float("nan")),
        "最大DD円": st.get("max_dd_jpy", 0.0),
        "最大DD%": st.get("max_dd_pct", float("nan")),
        "最大実効レバ": st.get("max_leverage", 0.0),
        "1倍超の日数": st.get("days_over_leverage", 0),
        "税引後損益": st.get("after_tax_pnl"),
        "見送り(単位不足)": sk.get("unit_too_small", 0),
        "見送り(レバ上限)": sk.get("leverage_cap", 0),
        "見送り(同時保有上限)": sk.get("max_positions", 0),
        "見送り(同一ペア保有中)": sk.get("pair_held", 0),
        "見送り(通貨偏り)": sk.get("currency_limit", 0),
        "数量削減": st.get("reduced_entries", 0),
        "強制縮小": st.get("leverage_reductions", 0),
    }

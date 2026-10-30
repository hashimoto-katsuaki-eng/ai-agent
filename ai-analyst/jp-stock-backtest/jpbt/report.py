"""日本語Markdownレポートを生成する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from jpbt.evaluate import percent


def _yen(value: float) -> str:
    return f"¥{value:,.0f}" if np.isfinite(value) else "—"


def _number(value: float) -> str:
    return f"{value:,.0f}" if np.isfinite(value) else "—"


def _signal_table(metrics: pd.DataFrame) -> str:
    headers = [
        "Top N",
        "保有日数",
        "候補",
        "有効件数",
        "エントリー除外",
        "期間外",
        "決済価格なし",
        "勝率（コスト後）",
        "平均リターン（粗）",
        "平均リターン（コスト後）",
        "中央値（粗）",
        "平均MAE",
        "最悪MAE",
        "ベンチマーク平均",
        "超過リターン",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in metrics.itertuples(index=False):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.top_n),
                    f"{row.horizon}日",
                    str(row.candidate_count),
                    str(row.signal_count),
                    str(row.entry_excluded),
                    str(row.horizon_excluded),
                    str(row.exit_unavailable),
                    percent(row.win_rate_net),
                    percent(row.mean_return_gross),
                    percent(row.mean_return_net),
                    percent(row.median_return_gross),
                    percent(row.mean_mae),
                    percent(row.worst_mae),
                    percent(row.benchmark_mean_return),
                    percent(row.excess_net_return),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _monthly_signal_table(monthly: pd.DataFrame) -> str:
    headers = ["Top N", "保有日数", "決済月", "件数", "平均リターン（コスト後）", "ベンチマーク", "超過"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in monthly.sort_values(["top_n", "horizon", "month"]).itertuples(index=False):
        lines.append(
            f"| {row.top_n} | {row.horizon}日 | {row.month} | {row.count} | "
            f"{percent(row.mean_return_net)} | {percent(row.benchmark_mean_return)} | "
            f"{percent(row.excess_net_return)} |"
        )
    return "\n".join(lines) if len(lines) > 2 else "該当データなし"


def _portfolio_month_ends(
    horizon: int,
    results: Mapping[tuple[int, str], Mapping[str, Any]],
    benchmark: Mapping[str, Any],
) -> str:
    curves = {
        "A": results[(horizon, "A")]["equity"][["date", "equity"]].rename(
            columns={"equity": "A"}
        ),
        "B": results[(horizon, "B")]["equity"][["date", "equity"]].rename(
            columns={"equity": "B"}
        ),
        "ベンチマーク": benchmark["equity"][["date", "equity"]].rename(
            columns={"equity": "ベンチマーク"}
        ),
    }
    combined = curves["A"].merge(curves["B"], on="date", how="outer").merge(
        curves["ベンチマーク"], on="date", how="outer"
    )
    if combined.empty:
        return "該当データなし"
    combined = combined.sort_values("date")
    combined["month"] = combined["date"].dt.strftime("%Y-%m")
    month_end = combined.groupby("month", as_index=False).tail(1).sort_values("date")
    lines = ["| 月末 | A | B | ベンチマーク |", "|---|---:|---:|---:|"]
    for _, row in month_end.iterrows():
        lines.append(
            f"| {row['month']} | {_yen(row['A'])} | {_yen(row['B'])} | "
            f"{_yen(row['ベンチマーク'])} |"
        )
    return "\n".join(lines)


def _monthly_portfolio_table(
    horizon: int,
    results: Mapping[tuple[int, str], Mapping[str, Any]],
    benchmark: Mapping[str, Any],
) -> str:
    monthly_frames = {
        "A": results[(horizon, "A")]["monthly"].set_index("month")["pnl"],
        "B": results[(horizon, "B")]["monthly"].set_index("month")["pnl"],
        "ベンチマーク": benchmark["monthly"].set_index("month")["pnl"],
    }
    months = sorted(set().union(*(frame.index for frame in monthly_frames.values())))
    lines = ["| 月 | A損益 | B損益 | ベンチマーク損益 |", "|---|---:|---:|---:|"]
    for month in months:
        values = [monthly_frames[name].get(month, np.nan) for name in ("A", "B", "ベンチマーク")]
        lines.append(f"| {month} | {_yen(values[0])} | {_yen(values[1])} | {_yen(values[2])} |")
    return "\n".join(lines)


def render_summary(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    signal_start_date: pd.Timestamp,
    signal_metrics: pd.DataFrame,
    signal_monthly: pd.DataFrame,
    portfolio_results: Mapping[tuple[int, str], Mapping[str, Any]],
    benchmark_results: Mapping[int, Mapping[str, Any]],
    sensitivity: Sequence[Mapping[str, float | int]],
    config: Mapping[str, Any],
) -> str:
    """実行結果と仕様上の制約を summary.md にまとめる。"""
    lines = [
        "# 日本株スクリーニング・バックテスト",
        "",
        f"- データ取得期間: {start_date:%Y-%m-%d} 〜 {end_date:%Y-%m-%d}",
        f"- シグナル評価期間: {signal_start_date:%Y-%m-%d} 〜 {end_date:%Y-%m-%d}",
        f"- 初期資金: {_yen(float(config['portfolio']['initial_capital']))}",
        "- 価格: J-Quants V2の調整後OHLCV。シグナルは当日終値までの情報で計算。",
        "- エントリー: t+1始値。保有日数Nはエントリー日を1日目としてt+N終値で決済。",
        "",
        "## シグナル単位の評価",
        "",
        "勝率は往復コスト控除後リターンが正の割合です。超過リターンは、各シグナル日の流動性適格銘柄ベンチマーク平均に対するコスト後の差です。",
        "",
        _signal_table(signal_metrics),
        "",
        "### 月別シグナル成績（決済月）",
        "",
        _monthly_signal_table(signal_monthly),
        "",
        "## 資金10万円でのポートフォリオ比較",
        "",
        "ベンチマークは、前営業日終値時点で流動性条件を満たした全銘柄の翌日終値間リターンを均等加重し、複利運用します。",
        "",
    ]
    for horizon in config["screening"]["horizons"]:
        benchmark = benchmark_results[int(horizon)]
        lines.extend(
            [
                f"### {horizon}営業日保有",
                "",
                "| 方式 | 最終資産 | CAGR | 最大DD（円） | 最大DD（%） | 取引回数 | 年税引後損益 | Aの価格理由スキップ率 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for mode in ("A", "B"):
            metrics = portfolio_results[(int(horizon), mode)]["metrics"]
            skip_ratio = percent(metrics["price_skip_ratio"]) if mode == "A" else "—"
            lines.append(
                f"| {mode} | {_yen(metrics['final_equity'])} | {percent(metrics['cagr'])} | "
                f"{_yen(metrics['max_drawdown_yen'])} | {percent(metrics['max_drawdown_percent'])} | "
                f"{metrics['trade_count']} | {_yen(metrics['after_tax_pnl'])} | {skip_ratio} |"
            )
        metrics = benchmark["metrics"]
        lines.append(
            f"| ベンチマーク | {_yen(metrics['final_equity'])} | {percent(metrics['cagr'])} | "
            f"{_yen(metrics['max_drawdown_yen'])} | {percent(metrics['max_drawdown_percent'])} | — | — | — |"
        )
        lines.extend(
            [
                "",
                f"#### {horizon}日保有: 月末資産",
                "",
                _portfolio_month_ends(int(horizon), portfolio_results, benchmark),
                "",
                f"#### {horizon}日保有: 月別損益",
                "",
                _monthly_portfolio_table(int(horizon), portfolio_results, benchmark),
                "",
                f"#### {horizon}日保有: 年ごとの実現損益・税",
                "",
                "| 方式 | 年 | 実現損益 | 税額 |",
                "|---|---:|---:|---:|",
            ]
        )
        for mode in ("A", "B"):
            tax_metrics = portfolio_results[(int(horizon), mode)]["metrics"]
            years = sorted(
                set(tax_metrics["yearly_realized_pnl"])
                | set(tax_metrics["tax_by_year"])
            )
            for year in years:
                lines.append(
                    f"| {mode} | {year} | "
                    f"{_yen(tax_metrics['yearly_realized_pnl'].get(year, 0.0))} | "
                    f"{_yen(tax_metrics['tax_by_year'].get(year, 0.0))} |"
                )
        lines.append("")

    lines.extend(
        [
            "## コスト感度",
            "",
            "| 保有日数 | 往復コスト | A CAGR | B CAGR |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in sensitivity:
        lines.append(
            f"| {row['horizon']}日 | {percent(float(row['cost']))} | "
            f"{percent(float(row['cagr_a']))} | {percent(float(row['cagr_b']))} |"
        )
    lines.extend(
        [
            "",
            "## 制約事項",
            "",
            "- Freeプランは株価データが過去2年分・12週間遅延です。指定期間に含まれる範囲で日付指定の日足を取得します。上場廃止銘柄は上場期間中の日付を指定すれば取得できる場合がありますが、保存期間外や取得不能データは含まれません。J-Quantsの日足は東証上場銘柄が対象です。",
            "- 52週高値判定に必要な過去250営業日のウォームアップを除外するため、シグナル評価期間はデータ取得期間より短くなります。",
            "- J-Quants V2の調整後価格は株式分割等で過去分が遡及再計算されます。現時点で指定どおり調整後価格を使いますが、完全なポイントインタイム価格ではありません。現金配当調整は含みません。",
            "- Freeプランでは前場・後場別の四本値は提供されません。単元未満株の実際の証券会社別約定タイミングは再現せず、翌営業日始値で近似しています。",
            "- V2の上限到達フラグULは当日の高値が上限に達したかを示し、始値が上限だったかは特定できません。始値上限の保守的な代替として、翌日UL=1の銘柄を除外します。",
            "- 税額は決済年ごとの実現損益を通算し、黒字年にのみ20.315%を課す簡易計算です。年をまたぐ損失繰越・税控除は行いません。未決済建玉の含み益には課税しません。",
            "- 約定不能・価格欠損がある場合、エントリーできない候補は除外して件数を計上します。予定決済日の価格が欠ける場合は、価格が再び得られる日まで保有を継続します。",
            "",
        ]
    )
    return "\n".join(lines)

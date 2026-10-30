"""J-Quants取得から評価・資産推移レポートまでを実行するCLI。"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from jpbt.evaluate import evaluate_signals
from jpbt.jquants import (
    JQuantsClient,
    MasterParquetCache,
    ParquetCache,
    filter_common_stock_bars,
)
from jpbt.portfolio import simulate_equal_weight_benchmark, simulate_portfolio
from jpbt.report import render_summary
from jpbt.signals import build_feature_panel, screening_warmup_days


def _date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).resolve()
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    for key in ("cache_dir", "output_dir"):
        configured_path = Path(config[key])
        config[key] = (
            configured_path if configured_path.is_absolute() else path.parent / configured_path
        )
    return config


def determine_date_range(config: dict[str, Any], today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    end_date = _date_value(config.get("end_date"))
    if end_date is None:
        end_date = today - timedelta(days=int(config["free_delay_days"]))
    start_date = _date_value(config.get("start_date"))
    if start_date is None:
        start_date = _subtract_years(end_date, int(config["history_years"]))
    if start_date > end_date:
        raise ValueError("start_dateはend_date以前にしてください。")
    return start_date, end_date


def trading_days(calendar: pd.DataFrame) -> list[date]:
    if calendar.empty:
        return []
    data = calendar.rename(columns={"Date": "date", "HolDiv": "hol_div"}).copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    return (
        data.loc[data["hol_div"].astype(str).eq("1"), "date"]
        .dropna()
        .dt.date
        .drop_duplicates()
        .sort_values()
        .tolist()
    )


def first_trading_day_each_month(dates: list[date]) -> list[date]:
    first_by_month: dict[tuple[int, int], date] = {}
    for trading_date in sorted(dates):
        first_by_month.setdefault((trading_date.year, trading_date.month), trading_date)
    return list(first_by_month.values())


def _write_signal_csv(signals: pd.DataFrame, output_path: Path) -> None:
    columns = [
        "date",
        "code",
        "score",
        "score_rank",
        "average_turnover",
        "volume_ratio",
        "prior_20d_high",
        "breakout_margin",
        "ma_short",
        "ma_long",
        "ma_deviation",
        "prior_52w_high",
        "is_52w_high",
        "liquidity_pass",
        "volume_surge_pass",
        "breakout_pass",
        "trend_pass",
        "not_overheated_pass",
        "entry_date",
        "entry_status",
    ]
    for horizon in sorted(
        {int(column.split("_")[1][:-1]) for column in signals if column.startswith("return_")}
    ):
        columns.extend(
            [
                f"return_{horizon}d",
                f"net_return_{horizon}d",
                f"mae_{horizon}d",
                f"status_{horizon}d",
            ]
        )
    available = [column for column in columns if column in signals]
    export = signals[available].copy()
    if "date" in export:
        export["date"] = pd.to_datetime(export["date"]).dt.strftime("%Y-%m-%d")
    export.to_csv(output_path, index=False)


def run_backtest(config: dict[str, Any], client: Any) -> tuple[Path, Path]:
    start_date, end_date = determine_date_range(config)
    calendar = client.fetch_calendar(start_date, end_date)
    dates = trading_days(calendar)
    if not dates:
        raise RuntimeError("取得期間に東証営業日がありません。")
    cache = ParquetCache(config["cache_dir"], client)
    bars = cache.fetch_dates(dates)
    if bars.empty:
        raise RuntimeError("日次株価データがありません。")

    screening = config["screening"]
    portfolio_config = config["portfolio"]
    master_cache = MasterParquetCache(config["cache_dir"], client)
    master_snapshots = master_cache.fetch_dates(first_trading_day_each_month(dates))
    bars, missing_master_codes = filter_common_stock_bars(bars, master_snapshots)
    if bars.empty:
        raise RuntimeError("上場銘柄マスタの条件を満たす株価データがありません。")
    panel = build_feature_panel(bars, dates, screening)
    if panel.empty:
        raise RuntimeError("スクリーニング特徴量を計算できませんでした。")
    analysis_start_index = screening_warmup_days(screening)
    if len(dates) <= analysis_start_index:
        raise RuntimeError(
            "データ期間が不足しています。"
            f"スクリーニング条件の計算には最低{analysis_start_index + 1}営業日必要です。"
        )
    analysis_start_date = pd.Timestamp(dates[analysis_start_index])
    panel = panel.loc[panel["date"] >= analysis_start_date].reset_index(drop=True)
    signals, signal_metrics, signal_monthly, _ = evaluate_signals(
        panel,
        dates,
        screening["top_n"],
        screening["horizons"],
        float(screening["roundtrip_cost"]),
    )
    benchmark_results: dict[int, dict[str, Any]] = {}
    portfolio_results: dict[tuple[int, str], dict[str, Any]] = {}
    sensitivity: list[dict[str, float | int]] = []
    initial_capital = float(portfolio_config["initial_capital"])

    for horizon in screening["horizons"]:
        benchmark_results[int(horizon)] = simulate_equal_weight_benchmark(
            panel, dates, initial_capital, analysis_start_index
        )
        for mode, baseline_cost_key in (("A", "cost_a"), ("B", "cost_b")):
            portfolio_results[(int(horizon), mode)] = simulate_portfolio(
                panel,
                signals,
                dates,
                int(horizon),
                portfolio_config,
                mode,
                float(portfolio_config[baseline_cost_key]),
                analysis_start_index,
            )
        for cost in portfolio_config["sensitivity_costs"]:
            result_a = simulate_portfolio(
                panel,
                signals,
                dates,
                int(horizon),
                portfolio_config,
                "A",
                float(cost),
                analysis_start_index,
            )
            result_b = simulate_portfolio(
                panel,
                signals,
                dates,
                int(horizon),
                portfolio_config,
                "B",
                float(cost),
                analysis_start_index,
            )
            sensitivity.append(
                {
                    "horizon": int(horizon),
                    "cost": float(cost),
                    "cagr_a": float(result_a["metrics"]["cagr"]),
                    "cagr_b": float(result_b["metrics"]["cagr"]),
                }
            )

    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    signals_path = output_dir / "signals.csv"
    summary_path = output_dir / "summary.md"
    _write_signal_csv(signals, signals_path)
    summary_path.write_text(
        render_summary(
            pd.Timestamp(dates[0]),
            pd.Timestamp(dates[-1]),
            analysis_start_date,
            signal_metrics,
            signal_monthly,
            portfolio_results,
            benchmark_results,
            sensitivity,
            config,
            missing_master_codes,
        ),
        encoding="utf-8",
    )
    return signals_path, summary_path


def main(argv: list[str] | None = None, client: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description="J-Quants日本株スクリーニングのバックテスト")
    parser.add_argument("--config", default="config.yaml", help="設定YAMLファイル")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    active_client = client or JQuantsClient(
        rate_limit_sleep_seconds=float(config["rate_limit_sleep_seconds"]),
        max_retries=int(config["max_retries"]),
        retry_backoff_seconds=float(config["retry_backoff_seconds"]),
    )
    signals_path, summary_path = run_backtest(config, active_client)
    print(f"完了: {signals_path}")
    print(f"完了: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

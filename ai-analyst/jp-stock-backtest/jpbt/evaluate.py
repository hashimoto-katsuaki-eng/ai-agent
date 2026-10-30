"""シグナル単位の将来リターン、ベンチマーク、月別成績を計算する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from jpbt.signals import select_top_n


def _dates_after(
    values: pd.Series,
    date_index: dict[pd.Timestamp, int],
    dates: pd.DatetimeIndex,
    offset: int,
) -> pd.Series:
    indices = values.map(date_index)
    positions = indices + offset
    valid = positions.notna() & positions.lt(len(dates))
    result = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    result.loc[valid] = dates.take(positions.loc[valid].astype(int).to_numpy()).to_numpy()
    return result


def net_return(gross_return: pd.Series | float, roundtrip_cost: float) -> pd.Series | float:
    """建玉・決済の双方に同率コストをかけた1株リターンを返す。"""
    return gross_return - (roundtrip_cost / 2) * (2 + gross_return)


def add_forward_returns(
    panel: pd.DataFrame,
    trading_dates: Sequence[pd.Timestamp | str],
    horizons: Sequence[int],
    roundtrip_cost: float = 0.002,
) -> pd.DataFrame:
    """翌日始値からt+N終値までのリターンとMAEを付加する。"""
    result = panel.sort_values(["code", "date"], kind="stable").copy()
    dates = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique()
    dates = dates.sort_values()
    date_index = {trading_date: index for index, trading_date in enumerate(dates)}
    grouped = result.groupby("code", sort=False)
    result["entry_open"] = grouped["open"].shift(-1)
    result["entry_volume"] = grouped["volume"].shift(-1)
    result["entry_upper_limit"] = grouped["upper_limit"].shift(-1)
    result["entry_date"] = _dates_after(result["date"], date_index, dates, 1)

    status = pd.Series("valid", index=result.index, dtype="object")
    date_positions = result["date"].map(date_index)
    end_of_data = date_positions.add(1).ge(len(dates))
    status.loc[end_of_data] = "beyond_data_end"
    status.loc[~end_of_data & (result["entry_open"].isna() | result["entry_open"].le(0))] = (
        "missing_open"
    )
    status.loc[
        ~end_of_data
        & status.eq("valid")
        & (result["entry_volume"].isna() | result["entry_volume"].le(0))
    ] = "zero_volume"
    status.loc[
        ~end_of_data
        & status.eq("valid")
        & result["entry_upper_limit"].eq(1)
    ] = "upper_limit"
    result["entry_status"] = status

    for horizon in horizons:
        close_at_exit = grouped["close"].shift(-int(horizon))
        low_columns = [
            grouped["low"].shift(-step).rename(f"low_{step}")
            for step in range(1, int(horizon) + 1)
        ]
        holding_lows = pd.concat(low_columns, axis=1)
        mae_low = holding_lows.min(axis=1)
        result[f"exit_date_{horizon}d"] = _dates_after(
            result["date"], date_index, dates, int(horizon)
        )
        horizon_beyond = date_positions.add(int(horizon)).ge(len(dates))
        horizon_status = result["entry_status"].copy()
        horizon_status.loc[horizon_beyond] = "horizon_beyond_data"
        exit_missing = (
            ~horizon_beyond
            & horizon_status.eq("valid")
            & (close_at_exit.isna() | close_at_exit.le(0))
        )
        horizon_status.loc[exit_missing] = "exit_close_missing"
        result[f"status_{horizon}d"] = horizon_status
        valid = horizon_status.eq("valid")
        gross = close_at_exit.div(result["entry_open"]).sub(1)
        result[f"return_{horizon}d"] = gross.where(valid)
        result[f"net_return_{horizon}d"] = net_return(gross, roundtrip_cost).where(valid)
        result[f"mae_{horizon}d"] = (
            mae_low.div(result["entry_open"]).sub(1).where(valid)
        )
        result[f"exit_close_{horizon}d"] = close_at_exit
    return result.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def evaluate_signals(
    panel: pd.DataFrame,
    trading_dates: Sequence[pd.Timestamp | str],
    top_n_values: Sequence[int],
    horizons: Sequence[int],
    roundtrip_cost: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[int, pd.DataFrame]]:
    """Top N別・保有日数別の指標、月次内訳、流動性ベンチマークを返す。"""
    forward = add_forward_returns(panel, trading_dates, horizons, roundtrip_cost)
    signals = forward.loc[forward["signal"]].copy()
    signal_metrics: list[dict[str, float | int]] = []
    monthly_rows: list[dict[str, float | int | str]] = []
    benchmarks: dict[int, pd.DataFrame] = {}

    for horizon in horizons:
        return_column = f"return_{horizon}d"
        mae_column = f"mae_{horizon}d"
        status_column = f"status_{horizon}d"
        selected_universe = forward.loc[
            forward["liquidity_pass"] & forward[status_column].eq("valid")
        ].copy()
        benchmark_daily = (
            selected_universe.groupby("date", as_index=False)[return_column]
            .mean()
            .rename(columns={return_column: "benchmark_return"})
        )
        date_values = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique()
        date_values = date_values.sort_values()
        date_map = {value: index for index, value in enumerate(date_values)}
        benchmark_daily["exit_date"] = _dates_after(
            benchmark_daily["date"], date_map, date_values, int(horizon)
        )
        benchmark_daily["month"] = benchmark_daily["exit_date"].dt.strftime("%Y-%m")
        benchmarks[int(horizon)] = benchmark_daily

        for top_n in top_n_values:
            candidates = select_top_n(signals, int(top_n))
            total = len(candidates)
            horizon_beyond = candidates[status_column].eq("horizon_beyond_data")
            entry_invalid = candidates["entry_status"].ne("valid") & ~horizon_beyond
            exit_missing = candidates[status_column].eq("exit_close_missing")
            valid = candidates.loc[candidates[status_column].eq("valid")].copy()
            valid["net_return"] = net_return(valid[return_column], roundtrip_cost)
            valid["month"] = valid[f"exit_date_{horizon}d"].dt.strftime("%Y-%m")
            daily_returns = benchmark_daily.set_index("date")["benchmark_return"]
            valid["benchmark_return"] = valid["date"].map(daily_returns)
            valid["excess_net_return"] = valid["net_return"] - valid["benchmark_return"]
            benchmark_mean = (
                float(valid["benchmark_return"].mean())
                if valid["benchmark_return"].notna().any()
                else float("nan")
            )
            gross = valid[return_column]
            net = valid["net_return"]
            mae = valid[mae_column].dropna()
            signal_metrics.append(
                {
                    "top_n": int(top_n),
                    "horizon": int(horizon),
                    "candidate_count": total,
                    "signal_count": len(valid),
                    "entry_excluded": int(entry_invalid.sum()),
                    "horizon_excluded": int(horizon_beyond.sum()),
                    "exit_unavailable": int(exit_missing.sum()),
                    "win_rate_net": float(net.gt(0).mean()) if len(net) else float("nan"),
                    "mean_return_gross": float(gross.mean()) if len(gross) else float("nan"),
                    "median_return_gross": float(gross.median()) if len(gross) else float("nan"),
                    "mean_return_net": float(net.mean()) if len(net) else float("nan"),
                    "median_return_net": float(net.median()) if len(net) else float("nan"),
                    "mean_mae": float(mae.mean()) if len(mae) else float("nan"),
                    "worst_mae": float(mae.min()) if len(mae) else float("nan"),
                    "benchmark_mean_return": benchmark_mean,
                    "excess_net_return": (
                        float(valid["excess_net_return"].mean()) if len(valid) else float("nan")
                    ),
                }
            )
            for month, rows in valid.groupby("month", dropna=True):
                monthly_rows.append(
                    {
                        "top_n": int(top_n),
                        "horizon": int(horizon),
                        "month": str(month),
                        "count": len(rows),
                        "mean_return_net": float(rows["net_return"].mean()),
                        "benchmark_mean_return": float(rows["benchmark_return"].mean()),
                        "excess_net_return": float(rows["excess_net_return"].mean()),
                    }
                )

    return (
        signals.sort_values(["date", "score", "code"], ascending=[True, False, True]),
        pd.DataFrame(signal_metrics),
        pd.DataFrame(monthly_rows),
        benchmarks,
    )


def yearly_tax(
    yearly_realized_pnl: Mapping[int, float], tax_rate: float
) -> tuple[dict[int, float], float]:
    """年内実現損益を通算し、黒字年だけに税を課す。"""
    tax_by_year = {
        int(year): max(float(pnl), 0.0) * tax_rate
        for year, pnl in yearly_realized_pnl.items()
    }
    return tax_by_year, sum(tax_by_year.values())


def percent(value: float) -> str:
    if not np.isfinite(value):
        return "—"
    return f"{value:.2%}"

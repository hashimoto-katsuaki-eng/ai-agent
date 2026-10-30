"""10万円を初期資金とする2方式の現物ポートフォリオシミュレーション。"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from jpbt.entries import is_upper_limit_open
from jpbt.evaluate import yearly_tax
from jpbt.signals import select_top_n


def _cagr(equity: pd.Series, dates: pd.Series) -> float:
    if equity.empty or equity.iloc[0] <= 0 or equity.iloc[-1] < 0:
        return float("nan")
    elapsed_days = (pd.Timestamp(dates.iloc[-1]) - pd.Timestamp(dates.iloc[0])).days
    if elapsed_days <= 0:
        return 0.0
    if equity.iloc[-1] == 0:
        return -1.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (365.25 / elapsed_days) - 1)


def _drawdown(equity: pd.Series) -> tuple[float, float]:
    peaks = equity.cummax()
    drawdowns = peaks - equity
    drawdown_percent = drawdowns.div(peaks.where(peaks > 0))
    return (
        float(drawdowns.max()) if not drawdowns.empty else 0.0,
        float(drawdown_percent.max()) if not drawdown_percent.empty else 0.0,
    )


def _monthly_pnl(equity: pd.DataFrame) -> pd.DataFrame:
    if equity.empty:
        return pd.DataFrame(columns=["month", "pnl", "equity"])
    month_ends = equity.assign(month=equity["date"].dt.strftime("%Y-%m")).groupby(
        "month", as_index=False
    ).tail(1)
    month_ends = month_ends.sort_values("date").copy()
    month_ends["pnl"] = month_ends["equity"].diff()
    if len(month_ends):
        month_ends.loc[month_ends.index[0], "pnl"] = (
            month_ends.iloc[0]["equity"] - equity.iloc[0]["equity"]
        )
    return month_ends[["month", "pnl", "equity"]].reset_index(drop=True)


def simulate_portfolio(
    panel: pd.DataFrame,
    signals: pd.DataFrame,
    trading_dates: Sequence[pd.Timestamp | str],
    horizon: int,
    portfolio_config: Mapping[str, Any],
    mode: str,
    cost: float,
    start_index: int = 0,
) -> dict[str, Any]:
    """指定方式で、翌日始値エントリー・t+N終値決済を模擬する。"""
    if mode not in {"A", "B"}:
        raise ValueError("modeは'A'または'B'を指定してください。")
    dates = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique()
    dates = dates.sort_values()
    if panel.empty or len(dates) <= start_index:
        raise ValueError("シミュレーション可能な株価データがありません。")
    initial_capital = float(portfolio_config["initial_capital"])
    entry_fee_rate = cost / 2
    exit_fee_rate = cost / 2
    selected = select_top_n(signals, int(portfolio_config["top_n"]))
    date_to_index = {trading_date: index for index, trading_date in enumerate(dates)}
    bars_by_key = panel.set_index(["date", "code"], drop=False)
    candidates_by_entry: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in selected.to_dict("records"):
        signal_date = pd.Timestamp(record["date"]).normalize()
        signal_index = date_to_index.get(signal_date)
        if signal_index is None:
            continue
        entry_index = signal_index + 1
        exit_index = signal_index + int(horizon)
        if entry_index < len(dates) and exit_index < len(dates):
            candidates_by_entry[entry_index].append(record)

    cash = initial_capital
    positions: dict[str, dict[str, Any]] = {}
    equity_rows: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    realized_by_year: dict[int, float] = defaultdict(float)
    candidate_attempts = 0
    price_skipped = 0
    cash_min = initial_capital
    max_open_positions = 0
    max_open_shares = 0

    for day_index in range(start_index, len(dates)):
        trading_date = dates[day_index]
        today_candidates = candidates_by_entry.get(day_index, [])
        today_candidates.sort(key=lambda item: (-float(item["score"]), str(item["code"])))
        for candidate in today_candidates:
            code = str(candidate["code"])
            candidate_attempts += 1
            if code in positions:
                continue
            signal_index = date_to_index[pd.Timestamp(candidate["date"]).normalize()]
            if signal_index + int(horizon) >= len(dates):
                continue
            try:
                bar = bars_by_key.loc[(trading_date, code)]
            except KeyError:
                continue
            if isinstance(bar, pd.DataFrame):
                bar = bar.iloc[-1]
            open_price = bar["open"]
            entry_volume = bar["volume"]
            upper_limit = bar["upper_limit"]
            if pd.isna(open_price) or open_price <= 0:
                continue
            if pd.isna(entry_volume) or entry_volume <= 0:
                continue
            if is_upper_limit_open(open_price, bar["high"], upper_limit):
                continue

            if mode == "B":
                maximum = int(portfolio_config["max_positions_b"])
                if len(positions) >= maximum:
                    continue
                allocation = cash / (maximum - len(positions))
                shares = math.floor(allocation / (float(open_price) * (1 + entry_fee_rate)))
                if shares <= 0:
                    price_skipped += 1
                    continue
            else:
                lot_cost = float(open_price) * 100 * (1 + entry_fee_rate)
                shares = 100 if lot_cost > 0 and lot_cost <= cash else 0
                if shares <= 0:
                    price_skipped += 1
                    continue

            notional = shares * float(open_price)
            entry_fee = notional * entry_fee_rate
            total_cost = notional + entry_fee
            if total_cost > cash + 1e-8:
                price_skipped += 1
                continue
            cash -= total_cost
            positions[code] = {
                "code": code,
                "shares": int(shares),
                "entry_date": trading_date,
                "entry_price": float(open_price),
                "entry_notional": notional,
                "entry_fee": entry_fee,
                "exit_index": signal_index + int(horizon),
                "last_close": float(open_price),
                "score": float(candidate["score"]),
            }
            cash_min = min(cash_min, cash)
            max_open_positions = max(max_open_positions, len(positions))
            max_open_shares = max(
                max_open_shares,
                sum(position["shares"] for position in positions.values()),
            )

        for code, position in list(positions.items()):
            try:
                bar = bars_by_key.loc[(trading_date, code)]
            except KeyError:
                bar = None
            if isinstance(bar, pd.DataFrame):
                bar = bar.iloc[-1]
            if bar is not None and not pd.isna(bar["close"]) and bar["close"] > 0:
                close_price = float(bar["close"])
                position["last_close"] = close_price
                if day_index >= position["exit_index"]:
                    exit_notional = position["shares"] * close_price
                    exit_fee = exit_notional * exit_fee_rate
                    cash += exit_notional - exit_fee
                    realized = (
                        exit_notional
                        - exit_fee
                        - position["entry_notional"]
                        - position["entry_fee"]
                    )
                    realized_by_year[trading_date.year] += realized
                    trades.append(
                        {
                            "code": code,
                            "entry_date": position["entry_date"],
                            "exit_date": trading_date,
                            "shares": position["shares"],
                            "entry_price": position["entry_price"],
                            "exit_price": close_price,
                            "realized_pnl": realized,
                            "score": position["score"],
                        }
                    )
                    del positions[code]

        market_value = sum(
            position["shares"] * position["last_close"] for position in positions.values()
        )
        equity_rows.append(
            {
                "date": trading_date,
                "equity": cash + market_value,
                "cash": cash,
                "market_value": market_value,
                "open_positions": len(positions),
            }
        )

    equity = pd.DataFrame(equity_rows)
    monthly = _monthly_pnl(equity)
    max_drawdown, max_drawdown_percent = _drawdown(equity["equity"])
    tax_by_year, total_tax = yearly_tax(
        dict(realized_by_year), float(portfolio_config["tax_rate"])
    )
    final_equity = float(equity["equity"].iloc[-1])
    metrics = {
        "mode": mode,
        "horizon": int(horizon),
        "cost": cost,
        "initial_equity": initial_capital,
        "final_equity": final_equity,
        "cagr": _cagr(equity["equity"], equity["date"]),
        "max_drawdown_yen": max_drawdown,
        "max_drawdown_percent": max_drawdown_percent,
        "trade_count": len(trades),
        "after_tax_pnl": final_equity - initial_capital - total_tax,
        "tax_by_year": tax_by_year,
        "yearly_realized_pnl": dict(realized_by_year),
        "open_positions_at_end": len(positions),
        "candidate_attempts": candidate_attempts,
        "price_skipped": price_skipped,
        "price_skip_ratio": price_skipped / candidate_attempts if candidate_attempts else 0.0,
        "cash_min": cash_min,
        "max_open_positions": max_open_positions,
        "max_open_shares": max_open_shares,
    }
    return {
        "metrics": metrics,
        "equity": equity,
        "monthly": monthly,
        "trades": pd.DataFrame(trades),
    }


def simulate_equal_weight_benchmark(
    panel: pd.DataFrame,
    trading_dates: Sequence[pd.Timestamp | str],
    initial_capital: float,
    start_index: int = 0,
) -> dict[str, Any]:
    """前営業日時点の流動性適格銘柄を均等加重する日次ベンチマーク。"""
    dates = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique()
    dates = dates.sort_values()
    daily_by_date = {
        trading_date: frame.set_index("code")
        for trading_date, frame in panel.groupby("date", sort=False)
    }
    equity = float(initial_capital)
    rows = [
        {
            "date": dates[start_index],
            "equity": equity,
            "daily_return": 0.0,
        }
    ]
    for day_index in range(start_index + 1, len(dates)):
        previous_date = dates[day_index - 1]
        current_date = dates[day_index]
        previous = daily_by_date.get(previous_date)
        current = daily_by_date.get(current_date)
        returns: list[float] = []
        if previous is not None and current is not None:
            eligible = previous.loc[previous["liquidity_pass"].fillna(False)]
            for code, previous_bar in eligible.iterrows():
                if code not in current.index:
                    continue
                current_bar = current.loc[code]
                if isinstance(current_bar, pd.DataFrame):
                    current_bar = current_bar.iloc[-1]
                previous_close = previous_bar["close"]
                current_close = current_bar["close"]
                if (
                    pd.notna(previous_close)
                    and previous_close > 0
                    and pd.notna(current_close)
                    and current_close > 0
                ):
                    returns.append(float(current_close / previous_close - 1))
        daily_return = float(np.mean(returns)) if returns else 0.0
        equity *= 1 + daily_return
        rows.append(
            {
                "date": current_date,
                "equity": equity,
                "daily_return": daily_return,
            }
        )

    equity_frame = pd.DataFrame(rows)
    monthly = _monthly_pnl(equity_frame)
    max_drawdown, max_drawdown_percent = _drawdown(equity_frame["equity"])
    metrics = {
        "final_equity": float(equity_frame["equity"].iloc[-1]),
        "cagr": _cagr(equity_frame["equity"], equity_frame["date"]),
        "max_drawdown_yen": max_drawdown,
        "max_drawdown_percent": max_drawdown_percent,
    }
    return {"metrics": metrics, "equity": equity_frame, "monthly": monthly}

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fxbt.benchmark import random_benchmark
from fxbt.portfolio import PortfolioResult, annual_tax, portfolio_stats, simulate_portfolio


def test_random_benchmark_is_reproducible_samples_matching_group_counts() -> None:
    rule = pd.DataFrame(
        {
            "pair": ["USDJPY", "USDJPY", "EURUSD"],
            "direction": ["long", "long", "short"],
            "pnl_pips": [3.0, -1.0, 2.0],
            "pnl_pips_swap": [2.0, -2.0, 1.0],
        }
    )
    pool = pd.DataFrame(
        {
            "pair": ["USDJPY", "USDJPY", "USDJPY", "EURUSD", "EURUSD"],
            "direction": ["long", "long", "long", "short", "short"],
            "pnl_pips": [1.0, 5.0, -3.0, 4.0, -2.0],
            "pnl_pips_swap": [0.0, 4.0, -4.0, 3.0, -3.0],
        }
    )

    result = random_benchmark(rule, pool, 40, np.random.default_rng(17))
    same = random_benchmark(rule, pool, 40, np.random.default_rng(17))
    other = random_benchmark(rule, pool, 40, np.random.default_rng(18))
    rng = np.random.default_rng(17)
    expected_sums = np.zeros(40)
    for (pair, direction), group in sorted(rule.groupby(["pair", "direction"]), key=lambda item: item[0]):
        candidates = pool[(pool["pair"] == pair) & (pool["direction"] == direction)]
        sampled_indices = rng.integers(0, len(candidates), size=(40, len(group)))
        expected_sums += candidates["pnl_pips"].to_numpy()[sampled_indices].sum(axis=1)

    assert result == same
    assert result != other
    assert result["n_trades"] == len(rule)
    assert result["pnl_pips"]["random_mean"] == pytest.approx((expected_sums / len(rule)).mean())
    assert 0 < result["pnl_pips"]["p_value"] <= 1


def make_bars(dates: pd.DatetimeIndex, price: float) -> pd.DataFrame:
    return pd.DataFrame({"open": price, "high": price, "low": price, "close": price}, index=dates)


def trade(
    pair: str,
    direction: str,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    entry_price: float,
    stop_price: float,
    exit_price: float,
    signal_date: pd.Timestamp | None = None,
) -> dict:
    return {
        "pair": pair,
        "direction": direction,
        "signal_date": signal_date or entry_date - pd.Timedelta(days=1),
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "exit_price": exit_price,
        "exit_reason": "time",
        "swap_pips": 0.0,
    }


def portfolio_config(**overrides) -> dict:
    return {
        "initial_capital": 100000,
        "risk_per_trade": 0.01,
        "max_leverage": 1.0,
        "max_positions": 3,
        "max_positions_per_pair": 1,
        **overrides,
    }


def run_portfolio(trades: pd.DataFrame, bars: dict[str, pd.DataFrame], **kwargs) -> PortfolioResult:
    dates = next(iter(bars.values())).index
    return simulate_portfolio(
        trades,
        bars,
        kwargs.pop("conv_bars", None),
        kwargs.pop("pcfg", portfolio_config()),
        kwargs.pop("spreads", {pair: 0.0 for pair in bars}),
        kwargs.pop("pips", {pair: 0.01 if pair.endswith("JPY") else 0.0001 for pair in bars}),
        dates[0],
        dates[-1],
        kwargs.pop("min_unit", 1),
        **kwargs,
    )


def test_portfolio_sizes_to_floor_of_risk_and_leverage_cap() -> None:
    dates = pd.bdate_range("2024-01-01", periods=3)
    bars = {"USDJPY": make_bars(dates, 150.0)}
    trades = pd.DataFrame([trade("USDJPY", "long", dates[1], dates[2], 150.0, 149.0, 150.0)])

    result = run_portfolio(trades, bars, min_unit=100)

    assert result.trades.loc[0, "units"] == 600


def test_portfolio_leverage_stays_at_or_below_one_with_short_and_eurusd_positions() -> None:
    dates = pd.bdate_range("2024-01-01", periods=8)
    bars = {
        "USDJPY": make_bars(dates, 150.0),
        "EURUSD": make_bars(dates, 1.1),
        "EURJPY": make_bars(dates, 160.0),
        "AUDJPY": make_bars(dates, 95.0),
    }
    trades = pd.DataFrame(
        [
            trade("USDJPY", "long", dates[1], dates[3], 150, 140, 151),
            trade("EURUSD", "short", dates[1], dates[3], 1.1, 1.2, 1.09),
            trade("EURJPY", "short", dates[2], dates[4], 160, 170, 159),
            trade("AUDJPY", "long", dates[4], dates[6], 95, 85, 96),
        ]
    )

    result = run_portfolio(trades, bars, conv_bars=bars["USDJPY"])

    assert len(result.trades) == 4
    assert set(result.trades["direction"]) == {"long", "short"}
    assert (result.equity["leverage"] <= 1.0 + 1e-12).all()


def test_portfolio_skips_trade_when_minimum_unit_is_too_large() -> None:
    dates = pd.bdate_range("2024-01-01", periods=3)
    bars = {"USDJPY": make_bars(dates, 150.0)}
    trades = pd.DataFrame([trade("USDJPY", "long", dates[1], dates[2], 150, 149, 150)])

    result = run_portfolio(trades, bars, pcfg=portfolio_config(initial_capital=1000), min_unit=1000)

    assert result.skips["unit_too_small"] == 1
    assert result.trades.empty


def test_portfolio_skips_fourth_simultaneous_position_at_max_positions() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    pairs = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY"]
    prices = [150.0, 160.0, 190.0, 95.0]
    bars = {pair: make_bars(dates, price) for pair, price in zip(pairs, prices, strict=True)}
    trades = pd.DataFrame(
        [trade(pair, "long", dates[1], dates[3], price, price - 10, price) for pair, price in zip(pairs, prices, strict=True)]
    )

    result = run_portfolio(trades, bars, pcfg=portfolio_config(max_positions=3))

    assert result.skips["max_positions"] == 1
    assert len(result.trades) == 3


def test_portfolio_records_gap_loss_at_actual_open_exit_price() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.0, 95.0, 100.0],
            "high": [100.0, 101.0, 100.0, 101.0],
            "low": [100.0, 99.0, 94.0, 99.0],
            "close": [100.0, 100.0, 96.0, 100.0],
        },
        index=dates,
    )
    gap = {
        **trade("USDJPY", "long", dates[1], dates[2], 100.0, 98.0, 95.0),
        "exit_reason": "stop_gap",
    }

    result = run_portfolio(pd.DataFrame([gap]), {"USDJPY": bars})

    assert result.trades.loc[0, "exit_price"] == 95.0
    assert result.trades.loc[0, "pnl_jpy"] < -500


def test_annual_tax_applies_loss_carryforward_and_20_315_percent_rate() -> None:
    trades = pd.DataFrame(
        {
            "exit_date": pd.to_datetime(["2020-12-01", "2021-12-01", "2022-12-01", "2024-12-01"]),
            "pnl_jpy": [-1000.0, 600.0, 300.0, 500.0],
        }
    )

    total_tax, yearly = annual_tax(trades, 0.20315, 3)

    assert yearly[2021]["taxable"] == 0
    assert yearly[2022]["taxable"] == 0
    assert yearly[2024]["taxable"] == 500
    assert total_tax == pytest.approx(500 * 0.20315)


def test_portfolio_stats_calculates_drawdown_on_known_equity_path() -> None:
    dates = pd.date_range("2024-01-01", periods=4)
    equity = pd.DataFrame(
        {"equity": [120.0, 90.0, 110.0, 80.0], "leverage": [0.5, 0.7, 0.6, 0.8]},
        index=dates,
    )
    result = PortfolioResult(equity, pd.DataFrame(), {}, 0, 0, 100.0)

    stats = portfolio_stats(result)

    assert stats["max_dd_jpy"] == 40
    assert stats["max_dd_pct"] == pytest.approx(1 / 3)

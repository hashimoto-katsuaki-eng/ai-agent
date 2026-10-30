from __future__ import annotations

import numpy as np
import pytest

from fxbt.trades import TradeParams, simulate_trade


def prices(size: int = 8) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = np.full(size, 100.0)
    return values.copy(), values + 0.5, values - 0.5, values.copy()


def params(**overrides) -> TradeParams:
    values = {"holding_days": 3, "stop_atr_mult": 2, "pip": 0.01}
    values.update(overrides)
    return TradeParams(**values)


def test_entry_is_next_open_and_time_exit_is_t_plus_n_close() -> None:
    o, h, l, c = prices()
    o[1] = 100.25
    c[3] = 101.5
    h[3] = 102.0

    result = simulate_trade(o, h, l, c, np.arange(len(o)) % 7, 0, 1, 1.0, params(spread_pips=2))

    assert result is not None
    assert result["entry_price"] == pytest.approx(100.27)
    assert result["exit_price"] == pytest.approx(101.5)
    assert result["exit_idx"] == 3
    assert result["exit_reason"] == "time"
    assert result["bars_held"] == 3


@pytest.mark.parametrize("stop_idx", [1, 2])
def test_intraday_stop_exits_at_stop_price_including_entry_day(stop_idx: int) -> None:
    o, h, l, c = prices()
    l[stop_idx] = 97.5

    result = simulate_trade(o, h, l, c, np.zeros(len(o), dtype=int), 0, 1, 1.0, params())

    assert result is not None
    assert result["exit_idx"] == stop_idx
    assert result["exit_price"] == pytest.approx(98.0)
    assert result["exit_reason"] == "stop"


def test_gap_through_stop_exits_at_next_open() -> None:
    o, h, l, c = prices()
    o[2] = 95.0
    h[2] = 100.0
    l[2] = 94.0

    result = simulate_trade(o, h, l, c, np.zeros(len(o), dtype=int), 0, 1, 1.0, params())

    assert result is not None
    assert result["exit_idx"] == 2
    assert result["exit_price"] == 95.0
    assert result["exit_reason"] == "stop_gap"


def test_stop_wins_when_stop_and_take_profit_touch_same_bar() -> None:
    o, h, l, c = prices()
    h[2] = 102.0
    l[2] = 97.0

    result = simulate_trade(
        o,
        h,
        l,
        c,
        np.zeros(len(o), dtype=int),
        0,
        1,
        1.0,
        params(take_profit_atr_mult=1.5),
    )

    assert result is not None
    assert result["exit_reason"] == "stop"
    assert result["exit_price"] == pytest.approx(98.0)


@pytest.mark.parametrize(("direction", "adverse_price"), [(1, 98.5), (-1, 101.5)])
def test_mae_uses_lows_for_long_and_highs_for_short(direction: int, adverse_price: float) -> None:
    o, h, l, c = prices()
    if direction > 0:
        l[2] = adverse_price
    else:
        h[2] = adverse_price

    result = simulate_trade(
        o,
        h,
        l,
        c,
        np.zeros(len(o), dtype=int),
        0,
        direction,
        1.0,
        params(stop_atr_mult=10),
    )

    assert result is not None
    assert result["mae_pips"] == pytest.approx(150.0)


def test_short_exit_pays_spread_and_wednesday_swap_is_triple() -> None:
    o, h, l, c = prices()
    c[4] = 99.0
    l[4] = 98.5
    weekdays = np.array([0, 1, 2, 3, 4, 5, 6, 0])

    result = simulate_trade(
        o,
        h,
        l,
        c,
        weekdays,
        0,
        -1,
        1.0,
        params(holding_days=4, spread_pips=0.5, swap_short_pips=-0.2),
    )

    assert result is not None
    assert result["exit_price"] == pytest.approx(99.005)
    assert result["pnl_pips"] == pytest.approx(99.5)
    assert result["swap_days"] == 5
    assert result["swap_pips"] == pytest.approx(-1.0)
    assert result["pnl_pips_swap"] == pytest.approx(98.5)


def test_returns_none_when_holding_period_exceeds_data() -> None:
    o, h, l, c = prices(size=3)

    assert simulate_trade(o, h, l, c, np.zeros(3, dtype=int), 0, 1, 1.0, params()) is None

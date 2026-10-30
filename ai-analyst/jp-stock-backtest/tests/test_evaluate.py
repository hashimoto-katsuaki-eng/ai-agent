from __future__ import annotations

import pandas as pd

from jpbt.evaluate import add_forward_returns, evaluate_signals, yearly_tax


def test_return_is_next_open_to_t_plus_n_close_and_mae_uses_entry_through_exit() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    panel = pd.DataFrame(
        {
            "date": dates,
            "code": ["1000"] * 5,
            "open": [9, 10, 11, 11, 12],
            "high": [10, 12, 12, 13, 13],
            "low": [8, 9, 8, 10, 11],
            "close": [9, 11, 10, 12, 12],
            "volume": [100] * 5,
            "upper_limit": [0] * 5,
            "signal": [True, False, False, False, False],
            "score": [1.0, 0, 0, 0, 0],
            "liquidity_pass": [True] * 5,
        }
    )
    evaluated = add_forward_returns(panel, dates, [3])
    first = evaluated.iloc[0]

    assert first["entry_date"] == dates[1]
    assert first["exit_date_3d"] == dates[3]
    assert first["return_3d"] == 12 / 10 - 1
    assert first["mae_3d"] == 8 / 10 - 1


def test_upper_limit_and_missing_open_entries_are_excluded_and_counted() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    rows = []
    for code in ("1000", "2000"):
        for index, trading_date in enumerate(dates):
            rows.append(
                {
                    "date": trading_date,
                    "code": code,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.0 + index,
                    "volume": 100.0,
                    "upper_limit": 0.0,
                    "signal": index == 0,
                    "score": 1.0 if index == 0 else 0.0,
                    "liquidity_pass": True,
                }
            )
    panel = pd.DataFrame(rows)
    panel.loc[(panel["code"] == "1000") & (panel["date"] == dates[1]), "open"] = float("nan")
    panel.loc[
        (panel["code"] == "2000") & (panel["date"] == dates[1]), "upper_limit"
    ] = 1.0
    _, metrics, _, _ = evaluate_signals(panel, dates, [2], [3], 0.002)
    result = metrics.iloc[0]

    assert result["candidate_count"] == 2
    assert result["entry_excluded"] == 2
    assert result["signal_count"] == 0


def test_horizon_beyond_data_end_is_excluded_and_counted() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    panel = pd.DataFrame(
        {
            "date": dates,
            "code": ["1000"] * 5,
            "open": [10.0] * 5,
            "high": [11.0] * 5,
            "low": [9.0] * 5,
            "close": [10.0] * 5,
            "volume": [100.0] * 5,
            "upper_limit": [0.0] * 5,
            "signal": [False, False, False, True, True],
            "score": [0.0, 0.0, 0.0, 1.0, 1.0],
            "liquidity_pass": [True] * 5,
        }
    )

    _, metrics, _, _ = evaluate_signals(panel, dates, [10], [3], 0.002)

    assert metrics.loc[0, "candidate_count"] == 2
    assert metrics.loc[0, "horizon_excluded"] == 2
    assert metrics.loc[0, "signal_count"] == 0


def test_yearly_tax_nets_only_within_each_calendar_year() -> None:
    tax_by_year, total = yearly_tax(
        {2023: 1000.0, 2024: -500.0, 2025: 500.0}, 0.20315
    )

    assert tax_by_year[2023] == 203.15
    assert tax_by_year[2024] == 0
    assert tax_by_year[2025] == 101.575
    assert total == 304.725

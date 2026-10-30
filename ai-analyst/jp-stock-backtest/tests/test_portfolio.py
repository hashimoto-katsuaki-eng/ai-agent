from __future__ import annotations

import pandas as pd

from jpbt.portfolio import simulate_portfolio


def test_portfolio_modes_respect_cash_lots_positions_and_integer_shares() -> None:
    dates = pd.bdate_range("2024-01-01", periods=9)
    rows = []
    signals = []
    for code_index, code in enumerate(("1000", "2000", "3000")):
        price = 400.0 + code_index * 100
        for index, trading_date in enumerate(dates):
            close = price + index
            rows.append(
                {
                    "date": trading_date,
                    "code": code,
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000.0,
                    "turnover": 1_000_000_000.0,
                    "upper_limit": 0.0,
                    "liquidity_pass": True,
                }
            )
            if index in (0, 1, 2, 3, 4):
                signals.append(
                    {
                        "date": trading_date,
                        "code": code,
                        "score": 3 - code_index,
                    }
                )
    panel = pd.DataFrame(rows)
    signal_frame = pd.DataFrame(signals)
    config = {
        "initial_capital": 100_000,
        "max_positions_b": 2,
        "tax_rate": 0.20315,
        "top_n": 3,
    }
    result_a = simulate_portfolio(panel, signal_frame, dates, 3, config, "A", 0.002)
    result_b = simulate_portfolio(panel, signal_frame, dates, 3, config, "B", 0.005)

    assert result_a["metrics"]["cash_min"] >= -1e-8
    assert result_a["metrics"]["max_open_positions"] >= 1
    assert all(shares % 100 == 0 for shares in result_a["trades"]["shares"])
    assert result_b["metrics"]["cash_min"] >= -1e-8
    assert result_b["metrics"]["max_open_positions"] <= 2
    assert all(float(shares).is_integer() for shares in result_b["trades"]["shares"])
    assert (result_a["equity"]["equity"] >= 0).all()
    assert (result_b["equity"]["equity"] >= 0).all()


def test_portfolio_a_buys_one_lot_per_eligible_candidate() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    panel = pd.DataFrame(
        [
            {
                "date": trading_date,
                "code": code,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1000.0,
                "upper_limit": 0.0,
            }
            for code in ("1000", "2000", "3000")
            for trading_date in dates
        ]
    )
    signals = pd.DataFrame(
        {
            "date": [dates[0]] * 3,
            "code": ["1000", "2000", "3000"],
            "score": [3.0, 2.0, 1.0],
        }
    )
    config = {
        "initial_capital": 100_000,
        "max_positions_b": 3,
        "tax_rate": 0.20315,
        "top_n": 3,
    }

    result = simulate_portfolio(panel, signals, dates, 3, config, "A", 0.002)

    assert len(result["trades"]) == 3
    assert result["trades"]["code"].nunique() == 3
    assert result["trades"]["shares"].tolist() == [100, 100, 100]


def test_portfolio_uses_open_at_upper_limit_proxy() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    panel = pd.DataFrame(
        {
            "date": dates,
            "code": ["1000"] * 5,
            "open": [10.0] * 5,
            "high": [11.0, 11.0, 11.0, 11.0, 11.0],
            "low": [9.0] * 5,
            "close": [10.0] * 5,
            "volume": [100.0] * 5,
            "upper_limit": [0.0, 1.0, 0.0, 0.0, 0.0],
        }
    )
    signals = pd.DataFrame({"date": [dates[0]], "code": ["1000"], "score": [1.0]})
    config = {
        "initial_capital": 100_000,
        "max_positions_b": 1,
        "tax_rate": 0.20315,
        "top_n": 1,
    }

    intraday_limit = simulate_portfolio(panel, signals, dates, 3, config, "A", 0.002)
    panel.loc[panel["date"] == dates[1], "high"] = 10.0
    opening_limit = simulate_portfolio(panel, signals, dates, 3, config, "A", 0.002)

    assert len(intraday_limit["trades"]) == 1
    assert len(opening_limit["trades"]) == 0

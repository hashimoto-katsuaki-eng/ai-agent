from __future__ import annotations

from datetime import date

import pandas as pd
import yaml

from backtest import main
from tests.conftest import make_trending_bars


class FakeJQuantsClient:
    def __init__(self, bars: pd.DataFrame) -> None:
        self.bars = bars

    def fetch_calendar(self, start_date: date, end_date: date) -> pd.DataFrame:
        del start_date, end_date
        dates = sorted(self.bars["date"].drop_duplicates())
        return pd.DataFrame({"Date": dates, "HolDiv": ["1"] * len(dates)})

    def fetch_daily_bars(self, trading_date: date) -> pd.DataFrame:
        return self.bars.loc[self.bars["date"].dt.date == trading_date].copy()


def test_full_pipeline_writes_csv_and_markdown_without_network(tmp_path) -> None:
    dates = pd.bdate_range("2024-01-01", periods=270)
    bars = make_trending_bars(dates, codes=("1000", "2000"), breakout_index=260)
    config_path = tmp_path / "config.yaml"
    config = {
        "history_years": 2,
        "free_delay_days": 84,
        "start_date": dates[0].strftime("%Y-%m-%d"),
        "end_date": dates[-1].strftime("%Y-%m-%d"),
        "cache_dir": str(tmp_path / "cache"),
        "output_dir": str(tmp_path / "output"),
        "rate_limit_sleep_seconds": 0,
        "max_retries": 1,
        "retry_backoff_seconds": 0,
        "screening": {
            "liquidity_window": 20,
            "min_average_turnover": 500_000_000,
            "volume_window": 20,
            "min_volume_ratio": 2.0,
            "breakout_window": 20,
            "ma_short_window": 25,
            "ma_long_window": 75,
            "max_ma_deviation": 0.25,
            "high_52w_window": 250,
            "high_52w_bonus": 0.1,
            "top_n": [2],
            "horizons": [3, 5],
            "roundtrip_cost": 0.002,
        },
        "portfolio": {
            "initial_capital": 100_000,
            "cost_a": 0.002,
            "cost_b": 0.005,
            "max_positions_b": 3,
            "tax_rate": 0.20315,
            "sensitivity_costs": [0.001, 0.002],
            "top_n": 2,
        },
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    assert (
        main(
            ["--config", str(config_path)],
            client=FakeJQuantsClient(bars),
        )
        == 0
    )
    signal_path = tmp_path / "output" / "signals.csv"
    summary_path = tmp_path / "output" / "summary.md"

    assert signal_path.exists()
    assert summary_path.exists()
    assert len(pd.read_csv(signal_path)) > 0
    summary = summary_path.read_text(encoding="utf-8")
    assert "資金10万円でのポートフォリオ比較" in summary
    assert "UL" in summary

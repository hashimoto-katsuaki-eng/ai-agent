from __future__ import annotations

import pandas as pd

from jpbt.signals import apply_signal_conditions, build_feature_panel
from tests.conftest import default_screening_config, make_trending_bars


def test_each_screening_condition_respects_its_boundary() -> None:
    baseline = {
        "average_turnover": 500_000_000,
        "volume_ratio": 2.0,
        "close": 102.0,
        "prior_20d_high": 101.0,
        "ma_short": 100.0,
        "ma_long": 99.0,
        "ma_deviation": 0.25,
        "is_52w_high": False,
    }
    cases = [
        ("liquidity_pass", "average_turnover", 499_999_999, "liquidity_pass"),
        ("volume_surge_pass", "volume_ratio", 1.999, "volume_surge_pass"),
        ("breakout_pass", "close", 101.0, "breakout_pass"),
        ("trend_pass", "ma_short", 102.0, "trend_pass"),
        ("not_overheated_pass", "ma_deviation", 0.250001, "not_overheated_pass"),
    ]
    frame = pd.DataFrame([baseline, *[
        {**baseline, field: boundary_value}
        for _, field, boundary_value, _ in cases
    ]])
    config = default_screening_config()
    result = apply_signal_conditions(frame, config)

    assert result.loc[0, "signal"]
    for index, (condition, _, _, _) in enumerate(cases, start=1):
        assert not result.loc[index, condition]
        assert not result.loc[index, "signal"]
    assert result.loc[0, "not_overheated_pass"]
    assert result.loc[0, "liquidity_pass"]
    assert result.loc[0, "volume_surge_pass"]


def test_twenty_day_high_excludes_current_day() -> None:
    dates = pd.bdate_range("2024-01-01", periods=270)
    bars = make_trending_bars(dates, breakout_index=-1)
    target = dates[260]
    bars.loc[bars["date"].eq(target), "high"] = 999_999
    panel = build_feature_panel(bars, dates, default_screening_config())
    row = panel.loc[(panel["code"] == "1000") & (panel["date"] == target)].iloc[0]
    previous_twenty_high = bars.loc[
        (bars["date"] >= dates[240]) & (bars["date"] < target), "high"
    ].max()

    assert row["prior_20d_high"] == previous_twenty_high
    assert row["prior_20d_high"] != 999_999


def test_mutating_or_dropping_future_rows_does_not_change_past_signals() -> None:
    dates = pd.bdate_range("2023-01-02", periods=300)
    bars = make_trending_bars(dates, breakout_index=270)
    cutoff = dates[270]
    config = default_screening_config()
    original = build_feature_panel(bars, dates, config)

    mutated = bars.copy()
    future = mutated["date"] > cutoff
    mutated.loc[future, ["open", "high", "low", "close", "volume", "turnover"]] *= 20
    mutated_panel = build_feature_panel(mutated, dates, config)
    truncated_panel = build_feature_panel(
        bars.loc[bars["date"] <= cutoff], dates[dates <= cutoff], config
    )
    columns = ["date", "code", "signal", "score"]
    original_past = original.loc[original["date"] <= cutoff, columns].reset_index(drop=True)
    mutated_past = mutated_panel.loc[
        mutated_panel["date"] <= cutoff, columns
    ].reset_index(drop=True)
    truncated_past = truncated_panel.loc[
        truncated_panel["date"] <= cutoff, columns
    ].reset_index(drop=True)

    pd.testing.assert_frame_equal(original_past, mutated_past)
    pd.testing.assert_frame_equal(original_past, truncated_past)

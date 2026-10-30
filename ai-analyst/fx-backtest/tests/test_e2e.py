from __future__ import annotations

import calendar
import lzma
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import yaml

import fx_backtest
from fxbt.config import point_scale
from fxbt.data import BI5_DTYPE, DukascopyFetcher, HttpResponse


class SyntheticBi5Client:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, timeout: float) -> HttpResponse:
        self.urls.append(url)
        parts = urlparse(url).path.strip("/").split("/")
        pair, year, month_zero = parts[-4], int(parts[-3]), int(parts[-2])
        month = month_zero + 1
        start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
        count = calendar.monthrange(year, month)[1] * 24
        scale = point_scale(pair)
        base = {"USDJPY": 105.0, "EURJPY": 115.0, "GBPJPY": 140.0, "AUDJPY": 90.0, "EURUSD": 1.05}[pair]
        step = 0.02 if pair.endswith("JPY") else 0.0001
        pad = 0.005 if pair.endswith("JPY") else 0.00005
        tick_records = []
        for hour in range(count):
            seconds = hour * 3600
            stamp = start + pd.Timedelta(seconds=seconds)
            session_date = (stamp.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)).normalize()
            day_number = (session_date.date() - date(2019, 1, 1)).days
            close = round((base + step * day_number) * scale)
            open_price = round((base + step * day_number - step / 2) * scale)
            high = round((base + step * day_number + pad) * scale)
            low = round((base + step * day_number - pad) * scale)
            tick_records.append((seconds, open_price, close, low, high, 1.0))
        raw = lzma.compress(np.array(tick_records, dtype=BI5_DTYPE).tobytes(), format=lzma.FORMAT_ALONE)
        return HttpResponse(200, raw)


def test_run_generates_outputs_using_only_synthetic_bi5(tmp_path: Path) -> None:
    config_path = Path(__file__).resolve().parents[1] / "fx_config.yaml"
    with config_path.open(encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    cfg["_base_dir"] = str(config_path.parent)
    cfg["data"]["start"] = "2019-01-01"
    cfg["data"]["end"] = "2020-12-01"
    cfg["data"]["cache_dir"] = str(tmp_path / "cache")
    cfg["data"]["request_interval_sec"] = 0
    cfg["output"]["dir"] = str(tmp_path / "output")
    cfg["exit"]["holding_days"] = [3]
    cfg["benchmark"]["n_runs"] = 20
    cfg["portfolio"]["min_units"] = [1]
    client = SyntheticBi5Client()
    fetcher = DukascopyFetcher(
        cfg["data"],
        tmp_path / "cache",
        client=client,
        sleep=lambda _delay: None,
        today=date(2021, 1, 15),
    )

    result = fx_backtest.run(cfg, fetcher=fetcher, today=date(2021, 1, 15))
    output = result["out_dir"]

    assert (output / "fx_trades.csv").is_file()
    assert (output / "fx_summary.md").is_file()
    assert (output / "fx_equity.csv").is_file()
    assert (output / "fx_portfolio_trades.csv").is_file()
    assert (output / "fx_monthly.csv").is_file()
    assert "主結果" in (output / "fx_summary.md").read_text(encoding="utf-8")
    assert len(client.urls) == 5 * 24

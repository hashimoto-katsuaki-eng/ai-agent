from __future__ import annotations

import lzma
from datetime import date

import numpy as np
import pandas as pd
import pytest

from fxbt.data import BI5_DTYPE, DukascopyFetcher, FetchError, HttpResponse, decode_hour_bi5, hourly_to_daily, quality_check


def pack_bi5(records: list[tuple]) -> bytes:
    return lzma.compress(np.array(records, dtype=BI5_DTYPE).tobytes(), format=lzma.FORMAT_ALONE)


class FakeHttpClient:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str, timeout: float) -> HttpResponse:
        self.urls.append(url)
        if self.responses:
            return self.responses.pop(0)
        raise AssertionError("HTTP 応答がありません")


def fetch_config(**overrides) -> dict:
    return {
        "base_url": "http://datafeed.dukascopy.com/datafeed/",
        "price_side": "BID",
        "max_retries": 2,
        "backoff_base_sec": 1,
        "request_interval_sec": 0,
        **overrides,
    }


@pytest.mark.parametrize(
    ("pair", "scale", "expected"),
    [("USDJPY", 1000, 150.123), ("EURUSD", 100000, 1.08765)],
)
def test_decode_hour_bi5_roundtrip(pair: str, scale: int, expected: float) -> None:
    raw = pack_bi5(
        [
            (0, int(expected * scale), int(expected * scale), int(expected * scale), int(expected * scale), 1.0),
            (3600, int(expected * scale), int(expected * scale), int(expected * scale), int(expected * scale), 2.0),
            (86400, int(expected * scale), int(expected * scale), int(expected * scale), int(expected * scale), 3.0),
        ]
    )

    frame = decode_hour_bi5(raw, 2024, 2, scale)

    assert frame["ts"].tolist() == [
        pd.Timestamp("2024-02-01 00:00:00", tz="UTC"),
        pd.Timestamp("2024-02-01 01:00:00", tz="UTC"),
        pd.Timestamp("2024-02-02 00:00:00", tz="UTC"),
    ]
    assert frame["open"].tolist() == pytest.approx([expected] * 3)
    assert frame["high"].tolist() == pytest.approx([expected] * 3)
    assert frame["low"].tolist() == pytest.approx([expected] * 3)
    assert frame["close"].tolist() == pytest.approx([expected] * 3)
    assert frame["volume"].tolist() == [1.0, 2.0, 3.0]
    assert pair in {"USDJPY", "EURUSD"}


def test_decode_empty_bytes_returns_empty_hourly_frame() -> None:
    frame = decode_hour_bi5(b"", 2024, 1, 1000)

    assert frame.empty
    assert frame.columns.tolist() == ["ts", "open", "high", "low", "close", "volume"]
    assert str(frame["ts"].dtype) == "datetime64[ns, UTC]"


def test_fetcher_formats_month_url_and_retries_with_retry_after(tmp_path) -> None:
    raw = pack_bi5([(0, 150000, 150100, 149900, 150200, 1.0)])
    client = FakeHttpClient(
        [
            HttpResponse(429, b"", {"Retry-After": "4"}),
            HttpResponse(503, b""),
            HttpResponse(200, raw),
        ]
    )
    waits: list[float] = []
    fetcher = DukascopyFetcher(
        fetch_config(backoff_base_sec=0.25),
        tmp_path,
        client=client,
        sleep=waits.append,
        today=date(2024, 4, 1),
    )

    frame = fetcher.fetch_month("USDJPY", 2024, 1)

    assert frame is not None
    assert client.urls == ["http://datafeed.dukascopy.com/datafeed/USDJPY/2024/00/BID_candles_hour_1.bi5"] * 3
    assert fetcher.stats.requests == 3
    assert fetcher.stats.retries == 2
    assert 4.0 in waits
    assert frame.loc[0, "close"] == pytest.approx(150.1)


def test_fetcher_records_404_as_missing_month(tmp_path) -> None:
    client = FakeHttpClient([HttpResponse(404, b"")])
    fetcher = DukascopyFetcher(fetch_config(), tmp_path, client=client, sleep=lambda _delay: None, today=date(2024, 4, 1))

    assert fetcher.fetch_month("USDJPY", 2024, 1) is None
    assert fetcher.stats.missing_months == ["USDJPY 2024-01"]


def test_fetcher_caches_completed_month_but_not_current_month(tmp_path) -> None:
    raw = pack_bi5([(0, 150000, 150100, 149900, 150200, 1.0)])
    client = FakeHttpClient([HttpResponse(200, raw), HttpResponse(200, raw)])
    fetcher = DukascopyFetcher(fetch_config(), tmp_path, client=client, sleep=lambda _delay: None, today=date(2024, 4, 15))

    first = fetcher.fetch_month("USDJPY", 2024, 1)
    cached = fetcher.fetch_month("USDJPY", 2024, 1)
    current = fetcher.fetch_month("USDJPY", 2024, 4)

    assert first is not None and cached is not None and current is not None
    assert fetcher.cache_path("USDJPY", 2024, 1).exists()
    assert pd.testing.assert_frame_equal(first, cached) is None
    assert not fetcher.cache_path("USDJPY", 2024, 4).exists()
    assert fetcher.stats.cache_hits == 1
    assert fetcher.stats.requests == 2


def test_fetcher_raises_after_persistent_failure_and_counts_retries(tmp_path) -> None:
    client = FakeHttpClient([HttpResponse(503, b"")] * 3)
    fetcher = DukascopyFetcher(fetch_config(max_retries=2), tmp_path, client=client, sleep=lambda _delay: None)

    with pytest.raises(FetchError, match="2 回再試行"):
        fetcher.fetch_month("USDJPY", 2024, 1)

    assert fetcher.stats.requests == 3
    assert fetcher.stats.retries == 2


def test_hourly_to_daily_observes_ny_close_dst_and_weekend_labels() -> None:
    hourly = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2024-01-15 21:00Z",
                    "2024-01-15 22:00Z",
                    "2024-07-15 21:00Z",
                    "2024-01-07 21:00Z",
                    "2024-01-07 22:00Z",
                    "2024-01-16 22:00Z",
                ],
                utc=True,
            ),
            "open": [10, 20, 30, 40, 50, 60],
            "high": [11, 21, 31, 41, 51, 61],
            "low": [9, 19, 29, 39, 49, 59],
            "close": [10.5, 20.5, 30.5, 40.5, 50.5, 60.5],
            "volume": [1, 1, 1, 1, 1, 0],
        }
    )

    daily, info = hourly_to_daily(hourly)

    assert pd.Timestamp("2024-01-15") in daily.index
    assert pd.Timestamp("2024-01-16") in daily.index
    assert pd.Timestamp("2024-07-16") in daily.index
    assert pd.Timestamp("2024-01-08") in daily.index
    assert pd.Timestamp("2024-01-07") not in daily.index
    assert daily.loc[pd.Timestamp("2024-01-15"), "close"] == 10.5
    assert daily.loc[pd.Timestamp("2024-01-16"), "open"] == 20
    assert daily.loc[pd.Timestamp("2024-07-16"), "open"] == 30
    assert info == {"zero_volume_hours": 1, "weekend_days_dropped": 1}
    assert daily.loc[pd.Timestamp("2024-01-08"), "open"] == 50


def test_quality_check_counts_spike_missing_business_day_and_bad_ohlc() -> None:
    dates = pd.bdate_range("2024-01-08", "2024-01-17").delete(2)
    close = np.full(len(dates), 100.0)
    close[-2:] = [200.0, 201.0]
    daily = pd.DataFrame(
        {
            "open": close.copy(),
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "n_hours": 24,
        },
        index=dates,
    )
    daily.loc[dates[-1], "high"] = daily.loc[dates[-1], "close"] - 1

    result = quality_check(daily, {"spike_window": 3, "spike_zscore": 2, "min_hours_per_day": 20})

    assert result["missing_business_days"] == 1
    assert result["missing_dates"] == ["2024-01-10"]
    assert result["bad_ohlc"] == 1
    assert result["spikes"] >= 1

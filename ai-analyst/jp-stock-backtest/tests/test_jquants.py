from __future__ import annotations

from datetime import date

import pandas as pd

from jpbt.jquants import (
    JQuantsClient,
    MasterParquetCache,
    ParquetCache,
    filter_common_stock_bars,
    normalize_daily_bars,
)


class FakeDailyClient:
    def __init__(self) -> None:
        self.calls: list[date] = []

    def fetch_daily_bars(self, trading_date: date) -> pd.DataFrame:
        self.calls.append(trading_date)
        return pd.DataFrame(
            {
                "Date": [trading_date.isoformat()],
                "Code": ["1000"],
                "AdjO": [10],
                "AdjH": [11],
                "AdjL": [9],
                "AdjC": [10],
                "AdjVo": [100],
                "Va": [1_000_000],
                "UL": ["0"],
            }
        )


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.status_code = 200
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "params": params.copy(),
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class FakeMasterClient:
    def __init__(self, frames: dict[date, pd.DataFrame]) -> None:
        self.frames = frames
        self.calls: list[date] = []

    def fetch_master(self, snapshot_date: date) -> pd.DataFrame:
        self.calls.append(snapshot_date)
        return self.frames[snapshot_date].copy()


def test_normalize_uses_v2_adjusted_daily_fields() -> None:
    frame = normalize_daily_bars(
        pd.DataFrame(
            {
                "Date": ["2024-01-01"],
                "Code": ["72030"],
                "AdjO": [100],
                "AdjH": [105],
                "AdjL": [99],
                "AdjC": [103],
                "AdjVo": [200],
                "Va": [20_000],
                "UL": ["1"],
            }
        )
    )

    row = frame.iloc[0]
    assert row["code"] == "72030"
    assert row["open"] == 100
    assert row["volume"] == 200
    assert row["upper_limit"] == 1


def test_v2_client_paginates_daily_bars_without_network() -> None:
    session = FakeSession(
        [
            FakeResponse(
                {
                    "data": [
                        {
                            "Date": "2024-01-04",
                            "Code": "1000",
                            "AdjO": 10,
                            "AdjH": 11,
                            "AdjL": 9,
                            "AdjC": 10,
                            "AdjVo": 100,
                            "Va": 1_000_000,
                            "UL": "0",
                        }
                    ],
                    "pagination_key": "next-page",
                }
            ),
            FakeResponse(
                {
                    "data": [
                        {
                            "Date": "2024-01-04",
                            "Code": "2000",
                            "AdjO": 20,
                            "AdjH": 21,
                            "AdjL": 19,
                            "AdjC": 20,
                            "AdjVo": 200,
                            "Va": 2_000_000,
                            "UL": "0",
                        }
                    ]
                }
            ),
        ]
    )
    client = JQuantsClient(
        api_key="test-key",
        session=session,
        rate_limit_sleep_seconds=0,
    )

    bars = client.fetch_daily_bars(date(2024, 1, 4))

    assert bars["code"].tolist() == ["1000", "2000"]
    assert session.calls[0]["url"] == "https://api.jquants.com/v2/equities/bars/daily"
    assert session.calls[0]["headers"] == {"x-api-key": "test-key"}
    assert session.calls[0]["params"] == {"date": "20240104"}
    assert session.calls[1]["params"] == {
        "date": "20240104",
        "pagination_key": "next-page",
    }


def test_parquet_cache_fetches_only_missing_dates(tmp_path) -> None:
    client = FakeDailyClient()
    cache = ParquetCache(tmp_path, client)
    first = date(2024, 1, 4)
    second = date(2024, 1, 5)

    cache.fetch_dates([first])
    cache.fetch_dates([first, second])

    assert client.calls == [first, second]
    assert cache.path_for(first).exists()
    assert cache.path_for(second).exists()


def test_master_cache_filters_etf_and_tpm_and_keeps_missing_codes(tmp_path) -> None:
    first = date(2024, 1, 4)
    second = date(2024, 2, 1)
    first_master = pd.DataFrame(
        {
            "Code": ["10000", "13060", "20000"],
            "ProdCat": ["011", "014", "011"],
            "Mkt": ["0105", "0111", "0105"],
        }
    )
    latest_master = pd.DataFrame(
        {
            "Code": ["10000", "13060", "20000"],
            "ProdCat": ["011", "014", "011"],
            "Mkt": ["0111", "0111", "0105"],
        }
    )
    client = FakeMasterClient({first: first_master, second: latest_master})
    cache = MasterParquetCache(tmp_path, client)
    snapshots = cache.fetch_dates([first, second])
    cache.fetch_dates([first])
    bars = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-02-02")] * 4,
            "code": ["10000", "13060", "20000", "30000"],
            "open": [10.0] * 4,
            "high": [11.0] * 4,
            "low": [9.0] * 4,
            "close": [10.0] * 4,
            "volume": [100.0] * 4,
            "turnover": [1_000_000.0] * 4,
            "upper_limit": [0.0] * 4,
        }
    )

    filtered, missing_count = filter_common_stock_bars(bars, snapshots)

    assert client.calls == [first, second]
    assert cache.path_for(first) == tmp_path / "master" / "2024-01-04.parquet"
    assert cache.path_for(first).exists()
    assert filtered["code"].tolist() == ["10000", "30000"]
    assert missing_count == 1

"""J-Quants API V2 クライアントと日次Parquetキャッシュ。"""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

API_BASE_URL = "https://api.jquants.com/v2"
DAILY_COLUMNS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover",
    "upper_limit",
]
BAR_FIELDS = {
    "Date": "date",
    "Code": "code",
    "AdjO": "open",
    "AdjH": "high",
    "AdjL": "low",
    "AdjC": "close",
    "AdjVo": "volume",
    "Va": "turnover",
    "UL": "upper_limit",
}


def normalize_daily_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """V2レスポンスを調整後価格を使う共通列名に変換する。"""
    if frame.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS)

    renamed = frame.rename(columns=BAR_FIELDS).copy()
    for column in DAILY_COLUMNS:
        if column not in renamed:
            renamed[column] = pd.NA
    renamed = renamed[DAILY_COLUMNS]
    renamed["date"] = pd.to_datetime(renamed["date"], errors="coerce").dt.normalize()
    renamed["code"] = renamed["code"].map(_normalize_code)
    for column in DAILY_COLUMNS[2:]:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
    return renamed.dropna(subset=["date", "code"]).reset_index(drop=True)


def filter_common_stock_bars(
    bars: pd.DataFrame, master_snapshots: pd.DataFrame
) -> tuple[pd.DataFrame, int]:
    normalized = normalize_daily_bars(bars)
    if normalized.empty:
        return normalized, 0
    if master_snapshots.empty or "Code" not in master_snapshots:
        return normalized, normalized["code"].nunique()

    master = master_snapshots.copy()
    master["code"] = master["Code"].map(_normalize_code)
    master = master.dropna(subset=["code"])
    if "_snapshot_date" in master:
        master = master.sort_values(["code", "_snapshot_date"], kind="stable")
    latest = master.drop_duplicates("code", keep="last")
    known_codes = set(latest["code"])
    missing_codes = set(normalized["code"]) - known_codes

    if "ProdCat" not in latest:
        eligible_codes = known_codes
    else:
        product_category = latest["ProdCat"].map(_normalize_code).str.zfill(3)
        eligible = product_category.eq("011") & latest["code"].str.endswith("0")
        if "Mkt" in latest:
            market = latest["Mkt"].map(_normalize_code).str.zfill(4)
            eligible &= market.ne("0105")
        eligible_codes = set(latest.loc[eligible, "code"])

    keep_codes = eligible_codes | missing_codes
    filtered = normalized.loc[normalized["code"].isin(keep_codes)].reset_index(drop=True)
    return filtered, len(missing_codes)


def _normalize_code(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().removesuffix(".0")


class JQuantsClient:
    """x-api-key認証、ページング、Freeプラン向けレート制御に対応する。"""

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        rate_limit_sleep_seconds: float = 12.1,
        max_retries: int = 5,
        retry_backoff_seconds: float = 2.0,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("JQUANTS_API_KEY")
        if not self.api_key:
            raise RuntimeError("環境変数 JQUANTS_API_KEY を設定してください。")
        self.session = session or requests.Session()
        self.rate_limit_sleep_seconds = rate_limit_sleep_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request_at: float | None = None

    def _pace(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.rate_limit_sleep_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _get_json(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{API_BASE_URL}{endpoint}"
        for attempt in range(self.max_retries + 1):
            self._pace()
            self._last_request_at = time.monotonic()
            response = self.session.get(
                url,
                headers={"x-api-key": self.api_key},
                params=params,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 0.0
                except ValueError:
                    delay = 0.0
                if delay <= 0:
                    delay = self.retry_backoff_seconds * (2**attempt)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("J-Quants APIのリトライ上限に達しました。")

    def _fetch_all(self, endpoint: str, params: dict[str, str]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        query = dict(params)
        while True:
            payload = self._get_json(endpoint, query)
            records.extend(payload.get("data", []))
            pagination_key = payload.get("pagination_key")
            if not pagination_key:
                return records
            query["pagination_key"] = pagination_key

    def fetch_calendar(self, start_date: date, end_date: date) -> pd.DataFrame:
        """取引カレンダーの営業日区分1を取得する。"""
        records = self._fetch_all(
            "/markets/calendar",
            {
                "from": start_date.strftime("%Y%m%d"),
                "to": end_date.strftime("%Y%m%d"),
            },
        )
        return pd.DataFrame(records, columns=["Date", "HolDiv"])

    def fetch_master(self, as_of: date | None = None) -> pd.DataFrame:
        """指定日の上場銘柄一覧を取得する。"""
        params = {"date": as_of.strftime("%Y%m%d")} if as_of else {}
        return pd.DataFrame(self._fetch_all("/equities/master", params))

    def fetch_daily_bars(self, trading_date: date) -> pd.DataFrame:
        """指定日の全銘柄日足を取得し、調整後OHLCVに変換する。"""
        records = self._fetch_all(
            "/equities/bars/daily",
            {"date": trading_date.strftime("%Y%m%d")},
        )
        return normalize_daily_bars(pd.DataFrame(records))


class ParquetCache:
    """日付ごとに株価を保存し、存在する日付は再取得しない。"""

    def __init__(self, cache_dir: str | Path, client: Any) -> None:
        self.cache_dir = Path(cache_dir)
        self.client = client
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, trading_date: date) -> Path:
        return self.cache_dir / f"{trading_date.isoformat()}.parquet"

    def get(self, trading_date: date) -> pd.DataFrame:
        path = self.path_for(trading_date)
        if path.exists():
            return pd.read_parquet(path)
        frame = normalize_daily_bars(self.client.fetch_daily_bars(trading_date))
        frame.to_parquet(path, index=False)
        return frame

    def fetch_dates(self, trading_dates: list[date]) -> pd.DataFrame:
        frames = [self.get(trading_date) for trading_date in trading_dates]
        nonempty = [frame for frame in frames if not frame.empty]
        if not nonempty:
            return pd.DataFrame(columns=DAILY_COLUMNS)
        return pd.concat(nonempty, ignore_index=True).drop_duplicates(
            ["date", "code"], keep="last"
        )


class MasterParquetCache:
    """月初の上場銘柄マスタを日付ごとに保存し、既存分を再利用する。"""

    def __init__(self, cache_dir: str | Path, client: Any) -> None:
        self.cache_dir = Path(cache_dir) / "master"
        self.client = client
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, snapshot_date: date) -> Path:
        return self.cache_dir / f"{snapshot_date.isoformat()}.parquet"

    def get(self, snapshot_date: date) -> pd.DataFrame:
        path = self.path_for(snapshot_date)
        if path.exists():
            return pd.read_parquet(path)
        frame = pd.DataFrame(self.client.fetch_master(snapshot_date))
        if frame.empty and len(frame.columns) == 0:
            frame = pd.DataFrame(columns=["Date", "Code", "ProdCat", "Mkt"])
        frame.to_parquet(path, index=False)
        return frame

    def fetch_dates(self, snapshot_dates: list[date]) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for snapshot_date in snapshot_dates:
            frame = self.get(snapshot_date).copy()
            frame["_snapshot_date"] = pd.Timestamp(snapshot_date)
            frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=["Code", "ProdCat", "Mkt", "_snapshot_date"])
        return pd.concat(frames, ignore_index=True)

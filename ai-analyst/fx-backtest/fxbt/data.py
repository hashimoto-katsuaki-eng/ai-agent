"""Dukascopy の 1 時間足取得・Parquet キャッシュ・NY クローズ日足の生成・データ品質チェック。"""

from __future__ import annotations

import logging
import lzma
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from .config import point_scale

log = logging.getLogger(__name__)

# Dukascopy の *_candles_hour_1.bi5 は LZMA 圧縮された 24 バイト固定長レコード
# (月初からの経過秒, 始値, 終値, 安値, 高値, 出来高)。価格は整数（JPY 建ては 1/1000、その他は 1/100000）。
BI5_DTYPE = np.dtype([("t", ">u4"), ("open", ">i4"), ("close", ">i4"), ("low", ">i4"), ("high", ">i4"), ("volume", ">f4")])
HOURLY_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


@dataclass
class HttpResponse:
    status: int
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)


class HttpClient(Protocol):
    def get(self, url: str, timeout: float) -> HttpResponse: ...


class RequestsClient:
    def __init__(self, user_agent: str = "ai-agent-fx-backtest/0.1 (personal research)") -> None:
        import requests

        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent

    def get(self, url: str, timeout: float) -> HttpResponse:
        r = self._session.get(url, timeout=timeout)
        return HttpResponse(r.status_code, r.content, dict(r.headers))


def empty_hourly() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype="float64") for c in HOURLY_COLUMNS})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def decode_hour_bi5(raw: bytes, year: int, month: int, scale: int) -> pd.DataFrame:
    """月次 1 時間足ファイルをデコードする。month は 1 始まり。"""
    if not raw:
        return empty_hourly()
    data = lzma.decompress(raw)
    if len(data) % BI5_DTYPE.itemsize != 0:
        raise FetchError(f"bi5 のサイズが不正です: {len(data)} bytes")
    rec = np.frombuffer(data, dtype=BI5_DTYPE)
    start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    df = pd.DataFrame(
        {
            "ts": start + pd.to_timedelta(rec["t"].astype("int64"), unit="s"),
            "open": rec["open"].astype("float64") / scale,
            "high": rec["high"].astype("float64") / scale,
            "low": rec["low"].astype("float64") / scale,
            "close": rec["close"].astype("float64") / scale,
            "volume": rec["volume"].astype("float64"),
        }
    )
    return df[HOURLY_COLUMNS]


def month_range(start: date, end: date) -> list[tuple[int, int]]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def last_complete_month(today: date) -> date:
    first = today.replace(day=1)
    prev = first - pd.Timedelta(days=1)
    return prev.replace(day=1)


@dataclass
class FetchStats:
    requests: int = 0
    retries: int = 0
    cache_hits: int = 0
    missing_months: list[str] = field(default_factory=list)


class DukascopyFetcher:
    """月単位で 1 時間足を取得し、完了済みの月は Parquet にキャッシュする（差分取得）。"""

    def __init__(
        self,
        data_cfg: dict,
        cache_dir: Path,
        client: HttpClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
        today: date | None = None,
    ) -> None:
        self.cfg = data_cfg
        self.cache_dir = Path(cache_dir)
        self.client = client
        self.sleep = sleep
        self.today = today or pd.Timestamp.now(tz="UTC").date()
        self.stats = FetchStats()
        self._last_request = 0.0

    def _client(self) -> HttpClient:
        if self.client is None:
            self.client = RequestsClient()
        return self.client

    def month_url(self, pair: str, year: int, month: int) -> str:
        side = self.cfg.get("price_side", "BID").upper()
        base = self.cfg["base_url"].rstrip("/")
        return f"{base}/{pair}/{year:04d}/{month - 1:02d}/{side}_candles_hour_1.bi5"

    def cache_path(self, pair: str, year: int, month: int) -> Path:
        side = self.cfg.get("price_side", "BID").upper()
        return self.cache_dir / "hourly" / side / pair / f"{year:04d}-{month:02d}.parquet"

    def _is_complete(self, year: int, month: int) -> bool:
        return (year, month) < (self.today.year, self.today.month)

    def _get_with_retry(self, url: str) -> HttpResponse:
        max_retries = int(self.cfg.get("max_retries", 6))
        backoff = float(self.cfg.get("backoff_base_sec", 2.0))
        interval = float(self.cfg.get("request_interval_sec", 0.5))
        timeout = float(self.cfg.get("timeout_sec", 30))
        last_err: str = ""
        for attempt in range(max_retries + 1):
            wait = interval - (time.monotonic() - self._last_request)
            if wait > 0:
                self.sleep(wait)
            self.stats.requests += 1
            try:
                resp = self._client().get(url, timeout=timeout)
                self._last_request = time.monotonic()
            except Exception as e:  # noqa: BLE001 - ネットワーク例外は種類を問わずリトライ
                self._last_request = time.monotonic()
                last_err = f"{type(e).__name__}: {e}"
                resp = None
            if resp is not None and resp.status not in RETRY_STATUS:
                return resp
            if resp is not None:
                last_err = f"HTTP {resp.status}"
            if attempt == max_retries:
                break
            delay = backoff * (2**attempt)
            if resp is not None and resp.status == 429:
                ra = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
                if ra and str(ra).isdigit():
                    delay = max(delay, float(ra))
            self.stats.retries += 1
            log.warning("取得失敗 (%s)。%.1f 秒待って再試行: %s", last_err, delay, url)
            self.sleep(delay)
        raise FetchError(f"{url} の取得に失敗しました（{max_retries} 回再試行）: {last_err}")

    def fetch_month(self, pair: str, year: int, month: int) -> pd.DataFrame | None:
        """1 か月分の 1 時間足。データが存在しない（404）場合は None。"""
        path = self.cache_path(pair, year, month)
        if path.exists():
            self.stats.cache_hits += 1
            return pd.read_parquet(path)
        resp = self._get_with_retry(self.month_url(pair, year, month))
        if resp.status == 404:
            self.stats.missing_months.append(f"{pair} {year:04d}-{month:02d}")
            return None
        if resp.status != 200:
            raise FetchError(f"想定外の HTTP {resp.status}: {self.month_url(pair, year, month)}")
        df = decode_hour_bi5(resp.content, year, month, point_scale(pair))
        if self._is_complete(year, month):
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path, index=False)
        return df

    def load_hourly(self, pair: str, start: date, end: date) -> pd.DataFrame:
        frames = []
        for y, m in month_range(start, end):
            df = self.fetch_month(pair, y, m)
            if df is not None and len(df):
                frames.append(df)
        if not frames:
            return empty_hourly()
        return pd.concat(frames, ignore_index=True).sort_values("ts").reset_index(drop=True)


def resolve_date_range(data_cfg: dict, today: date) -> tuple[date, date]:
    start = pd.Timestamp(data_cfg["start"]).date().replace(day=1)
    end_cfg = data_cfg.get("end")
    end = pd.Timestamp(end_cfg).date().replace(day=1) if end_cfg else last_complete_month(today)
    return start, end


def hourly_to_daily(hourly: pd.DataFrame, tz: str = "America/New_York", boundary_hour: int = 17) -> tuple[pd.DataFrame, dict]:
    """1 時間足を NY 時間 boundary_hour 区切りの日足にする。

    日足のラベルは「その日の boundary_hour（NY 時間）に終わるセッション」の日付。
    出来高 0 の 1 時間足（Dukascopy が休場時間を埋める横ばい足）は除外する。
    """
    info = {"zero_volume_hours": 0, "weekend_days_dropped": 0}
    if hourly.empty:
        cols = ["open", "high", "low", "close", "n_hours"]
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], name="date")), info
    h = hourly[hourly["volume"] > 0]
    info["zero_volume_hours"] = int(len(hourly) - len(h))
    local = h["ts"].dt.tz_convert(tz).dt.tz_localize(None)
    label = (local + pd.Timedelta(hours=24 - boundary_hour)).dt.normalize()
    g = h.assign(date=label.values).groupby("date", sort=True)
    daily = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
            "n_hours": g["open"].size(),
        }
    )
    weekend = daily.index.dayofweek >= 5
    info["weekend_days_dropped"] = int(weekend.sum())
    daily = daily[~weekend]
    daily.index.name = "date"
    return daily, info


def quality_check(daily: pd.DataFrame, qcfg: dict) -> dict:
    """欠損・異常値（スパイク）の検出。データは書き換えず件数と日付を記録するだけ。"""
    res: dict = {"days": len(daily)}
    if daily.empty:
        res.update(missing_business_days=0, missing_dates=[], short_days=0, bad_ohlc=0, spikes=0, spike_dates=[])
        return res
    bdays = pd.bdate_range(daily.index.min(), daily.index.max())
    bdays = bdays[~(((bdays.month == 12) & (bdays.day == 25)) | ((bdays.month == 1) & (bdays.day == 1)))]
    missing = bdays.difference(daily.index)
    res["first_date"] = daily.index.min().date().isoformat()
    res["last_date"] = daily.index.max().date().isoformat()
    res["missing_business_days"] = len(missing)
    res["missing_dates"] = [d.date().isoformat() for d in missing]
    res["short_days"] = int((daily["n_hours"] < int(qcfg.get("min_hours_per_day", 20))).sum())
    o, h, l, c = (daily[k] for k in ("open", "high", "low", "close"))
    bad = (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (daily[["open", "high", "low", "close"]] <= 0).any(axis=1)
    res["bad_ohlc"] = int(bad.sum())
    r = np.log(c).diff()
    sd = r.shift(1).rolling(int(qcfg.get("spike_window", 60))).std()
    spike = r.abs() > float(qcfg.get("spike_zscore", 8.0)) * sd
    res["spikes"] = int(spike.sum())
    res["spike_dates"] = [d.date().isoformat() for d in daily.index[spike.fillna(False).to_numpy()]]
    return res

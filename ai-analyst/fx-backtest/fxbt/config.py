"""設定ファイルの読み込み。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    base = Path(path).resolve().parent
    cfg["_base_dir"] = str(base)
    return cfg


def resolve_path(cfg: dict[str, Any], p: str) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return Path(cfg.get("_base_dir", ".")) / path


def quote_currency(pair: str) -> str:
    return pair[3:]


def base_currency(pair: str) -> str:
    return pair[:3]


def pip_size(pair: str) -> float:
    return 0.01 if quote_currency(pair) == "JPY" else 0.0001


def point_scale(pair: str) -> int:
    """Dukascopy の価格整数をこの値で割ると実価格になる。"""
    return 1000 if quote_currency(pair) == "JPY" else 100000

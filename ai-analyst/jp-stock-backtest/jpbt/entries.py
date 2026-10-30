from __future__ import annotations

from typing import Any

import pandas as pd


def is_upper_limit_open(
    open_price: Any,
    high_price: Any,
    upper_limit: Any,
) -> bool | pd.Series:
    if isinstance(open_price, pd.Series):
        return upper_limit.eq(1) & open_price.eq(high_price)
    return bool(
        pd.notna(upper_limit)
        and upper_limit == 1
        and pd.notna(open_price)
        and pd.notna(high_price)
        and open_price == high_price
    )

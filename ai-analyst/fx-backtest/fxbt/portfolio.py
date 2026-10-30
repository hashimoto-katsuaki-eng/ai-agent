"""資金 10 万円でのシミュレーション（実効レバレッジ 1 倍以下、リスク % によるサイズ決定）。

実効レバレッジ = 保有ポジションの想定元本（円換算、日々の終値で評価）の合計 / 時価評価の資産。

新規エントリーの上限は「全ポジションが損切り価格まで動いても実効レバレッジ 1 倍以下」になるように決める。
資産 E = 実現済み資金 C + Σ含み損益 とすると、max_leverage = 1 のとき
  買い u 通貨（約定 e）: 想定元本 − 含み損益 = u·e（価格によらず一定）
  売り u 通貨（約定 e, 損切り幅 d）: 想定元本 − 含み損益 = u·(2p − e) ≤ u·(e + 2d)（p ≤ 損切り価格）
なので Σ（買い u·e + 売り u·(e + 2d)）≤ C を満たせば、損切り前の終値評価では常に 1 倍以下になる。
窓開けで損切り価格を越えた損失や円換算レートの変動でそれでも上限を超えた日は、
その日の終値で全ポジションを同じ比率で縮小する（安全装置、件数を記録）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import base_currency, quote_currency

SKIP_REASONS = ("max_positions", "pair_held", "currency_limit", "unit_too_small", "leverage_cap")


@dataclass
class Position:
    pair: str
    s: int
    units: float
    entry: float
    dist: float
    req_per_unit: float
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str
    swap_pips: float
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp

    @property
    def req(self) -> float:
        return self.units * self.req_per_unit


@dataclass
class PortfolioResult:
    equity: pd.DataFrame
    trades: pd.DataFrame
    skips: dict
    reduced_entries: int
    leverage_reductions: int
    initial_capital: float


class FxConverter:
    """決済通貨（quote）→ 円の換算レート。JPY 建ては 1、USD 建ては USDJPY を使う。"""

    def __init__(self, calendar: pd.DatetimeIndex, conv_bars: pd.DataFrame | None) -> None:
        if conv_bars is not None and len(conv_bars):
            close = conv_bars["close"].reindex(calendar).ffill()
            opn = conv_bars["open"].reindex(calendar).fillna(close.shift(1)).ffill()
            self.close, self.open = close.bfill(), opn.bfill()
        else:
            self.close = self.open = None

    def rate(self, pair: str, d: pd.Timestamp, field: str = "close") -> float:
        q = quote_currency(pair)
        if q == "JPY":
            return 1.0
        if q != "USD" or self.close is None:
            raise ValueError(f"{pair} の円換算レートがありません（USDJPY が必要）")
        return float((self.open if field == "open" else self.close)[d])


def _legs(pair: str, s: int) -> list[tuple[str, int]]:
    return [(base_currency(pair), s), (quote_currency(pair), -s)]


def simulate_portfolio(
    trades: pd.DataFrame,
    bars: dict[str, pd.DataFrame],
    conv_bars: pd.DataFrame | None,
    pcfg: dict,
    spreads: dict[str, float],
    pips: dict[str, float],
    start: pd.Timestamp,
    end: pd.Timestamp,
    min_unit: float,
    include_swap: bool = True,
    pair_order: list[str] | None = None,
) -> PortfolioResult:
    initial = float(pcfg.get("initial_capital", 100000))
    risk = float(pcfg.get("risk_per_trade", 0.01))
    lev_max = float(pcfg.get("max_leverage", 1.0))
    max_pos = int(pcfg.get("max_positions", 3))
    per_pair = int(pcfg.get("max_positions_per_pair", 1))
    per_ccy = pcfg.get("max_positions_per_currency")
    pair_order = pair_order or sorted(bars)

    if len(trades):
        end = max(end, trades["exit_date"].max())
    cal = pd.DatetimeIndex(sorted(set().union(*[b.index for b in bars.values()])))
    cal = cal[(cal >= start) & (cal <= end)]
    fx = FxConverter(cal, conv_bars)
    close = {p: b["close"].reindex(cal).ffill().bfill() for p, b in bars.items()}

    by_entry = {d: g for d, g in trades.groupby("entry_date")} if len(trades) else {}
    cash, prev_equity = initial, initial
    positions: list[Position] = []
    skips = dict.fromkeys(SKIP_REASONS, 0)
    reduced, lev_reductions = 0, 0
    closed_rows, eq_rows = [], []

    def record(pos: Position, d, units, price, reason, fx_rate, swap_included):
        pnl = pos.s * units * (price - pos.entry) * fx_rate
        swap = pos.swap_pips * pips[pos.pair] * units * fx_rate if swap_included else 0.0
        closed_rows.append(
            {
                "signal_date": pos.signal_date,
                "entry_date": pos.entry_date,
                "exit_date": d,
                "pair": pos.pair,
                "direction": "long" if pos.s > 0 else "short",
                "units": units,
                "entry_price": pos.entry,
                "exit_price": price,
                "pnl_jpy": pnl + swap,
                "swap_jpy": swap,
                "exit_reason": reason,
            }
        )
        return pnl + swap

    for d in cal:
        # 1) 始値でエントリー（前日終値時点の資産でサイズ決定）
        if d in by_entry:
            cands = by_entry[d].assign(_o=by_entry[d]["pair"].map({p: i for i, p in enumerate(pair_order)}))
            for tr in cands.sort_values(["_o", "direction"]).itertuples():
                s = 1 if tr.direction == "long" else -1
                if len(positions) >= max_pos:
                    skips["max_positions"] += 1
                    continue
                if sum(p.pair == tr.pair for p in positions) >= per_pair:
                    skips["pair_held"] += 1
                    continue
                if per_ccy is not None:
                    held = [leg for p in positions for leg in _legs(p.pair, p.s)]
                    if any(held.count(leg) >= int(per_ccy) for leg in _legs(tr.pair, s)):
                        skips["currency_limit"] += 1
                        continue
                rate = fx.rate(tr.pair, d, "open")
                dist = abs(tr.entry_price - tr.stop_price)
                units_risk = risk * prev_equity / (dist * rate)
                req_per_unit = (tr.entry_price + (2 * dist if s < 0 else 0.0)) * rate
                avail = max(lev_max * cash - sum(p.req for p in positions), 0.0)
                units_cap = avail / req_per_unit
                if units_risk < min_unit:
                    skips["unit_too_small"] += 1
                    continue
                units = math.floor(min(units_risk, units_cap) / min_unit) * min_unit
                if units < min_unit:
                    skips["leverage_cap"] += 1
                    continue
                if units_cap < units_risk:
                    reduced += 1
                positions.append(
                    Position(
                        tr.pair,
                        s,
                        float(units),
                        tr.entry_price,
                        dist,
                        req_per_unit,
                        tr.exit_date,
                        tr.exit_price,
                        tr.exit_reason,
                        tr.swap_pips,
                        tr.signal_date,
                        tr.entry_date,
                    )
                )
        # 2) その日に決済されるポジション（損切り・時間エグジット）
        still = []
        for pos in positions:
            if pos.exit_date == d:
                cash += record(pos, d, pos.units, pos.exit_price, pos.exit_reason, fx.rate(pos.pair, d), include_swap)
            else:
                still.append(pos)
        positions = still

        # 3) 終値で時価評価
        def marks(positions: list[Position], d: pd.Timestamp) -> tuple[float, float]:
            unreal = notional = 0.0
            for pos in positions:
                px = close[pos.pair][d] + (spreads[pos.pair] * pips[pos.pair] if pos.s < 0 else 0.0)
                r = fx.rate(pos.pair, d)
                unreal += pos.s * pos.units * (px - pos.entry) * r
                notional += pos.units * px * r
            return unreal, notional

        unreal, notional = marks(positions, d)
        equity = cash + unreal
        if positions and (equity <= 0 or notional > lev_max * equity * (1 + 1e-12)):
            f = max(lev_max * equity / notional, 0.0) if equity > 0 else 0.0
            lev_reductions += 1
            kept = []
            for pos in positions:
                new_u = math.floor(pos.units * f / min_unit) * min_unit
                cut = pos.units - new_u
                if cut > 0:
                    px = close[pos.pair][d] + (spreads[pos.pair] * pips[pos.pair] if pos.s < 0 else 0.0)
                    cash += record(pos, d, cut, px, "leverage_reduce", fx.rate(pos.pair, d), False)
                    pos.units = float(new_u)
                if pos.units > 0:
                    kept.append(pos)
            positions = kept
            unreal, notional = marks(positions, d)
            equity = cash + unreal
        eq_rows.append(
            {
                "date": d,
                "cash": cash,
                "equity": equity,
                "notional": notional,
                "leverage": notional / equity if equity > 0 else (0.0 if notional == 0 else np.inf),
                "n_positions": len(positions),
            }
        )
        prev_equity = equity

    eq = (
        pd.DataFrame(eq_rows).set_index("date")
        if eq_rows
        else pd.DataFrame(columns=["cash", "equity", "notional", "leverage", "n_positions"])
    )
    return PortfolioResult(eq, pd.DataFrame(closed_rows), skips, reduced, lev_reductions, initial)


def portfolio_stats(res: PortfolioResult, tax_rate: float = 0.20315, carry_years: int = 3) -> dict:
    eq = res.equity["equity"]
    init = res.initial_capital
    if eq.empty:
        return {"final_equity": init, "total_pnl": 0.0, "n_trades": 0}
    final = float(eq.iloc[-1])
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    peak = np.maximum.accumulate(np.concatenate([[init], eq.to_numpy()]))[1:]
    dd = peak - eq.to_numpy()
    tax_total, yearly = annual_tax(res.trades, tax_rate, carry_years)
    lev = res.equity["leverage"]
    return {
        "final_equity": final,
        "total_pnl": final - init,
        "total_return": final / init - 1,
        "annual_return": (final / init) ** (365.25 / days) - 1 if final > 0 else -1.0,
        "max_dd_jpy": float(dd.max()),
        "max_dd_pct": float((dd / peak).max()),
        "max_leverage": float(lev.max()),
        "days_over_leverage": int((lev > 1.0 + 1e-9).sum()),
        "n_trades": int((res.trades["exit_reason"] != "leverage_reduce").sum()) if len(res.trades) else 0,
        "tax": tax_total,
        "after_tax_pnl": (final - init) - tax_total,
        "skips": dict(res.skips),
        "reduced_entries": res.reduced_entries,
        "leverage_reductions": res.leverage_reductions,
        "yearly_tax": yearly,
    }


def annual_tax(trades: pd.DataFrame, rate: float, carry_years: int) -> tuple[float, dict]:
    """暦年ごとの実現損益に課税（申告分離 20.315%、損失は carry_years 年繰越）。"""
    if trades is None or trades.empty:
        return 0.0, {}
    by_year = trades.groupby(trades["exit_date"].dt.year)["pnl_jpy"].sum()
    losses: list[list[float]] = []  # [year, 残額]
    total, out = 0.0, {}
    for y in range(int(by_year.index.min()), int(by_year.index.max()) + 1):
        pnl = float(by_year.get(y, 0.0))
        losses = [lo for lo in losses if y - lo[0] <= carry_years and lo[1] > 0]
        taxable = 0.0
        if pnl > 0:
            taxable = pnl
            for lo in losses:
                use = min(lo[1], taxable)
                lo[1] -= use
                taxable -= use
        elif pnl < 0:
            losses.append([y, -pnl])
        tax = taxable * rate
        total += tax
        out[y] = {"pnl": pnl, "taxable": taxable, "tax": tax}
    return total, out


def monthly_pnl(res: PortfolioResult) -> pd.DataFrame:
    eq = res.equity["equity"]
    if eq.empty:
        return pd.DataFrame(columns=["equity", "pnl", "max_leverage"])
    m = eq.groupby(eq.index.to_period("M")).last()
    pnl = m.diff()
    pnl.iloc[0] = m.iloc[0] - res.initial_capital
    lev = res.equity["leverage"].groupby(eq.index.to_period("M")).max()
    return pd.DataFrame({"equity": m, "pnl": pnl, "max_leverage": lev})

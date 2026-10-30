"""FX 短期ブレイクアウト条件のバックテスト (AI-239)。

使い方: python fx_backtest.py --config fx_config.yaml
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from fxbt.benchmark import random_benchmark
from fxbt.config import load_config, pip_size, quote_currency, resolve_path
from fxbt.data import DukascopyFetcher, hourly_to_daily, quality_check, resolve_date_range
from fxbt.portfolio import monthly_pnl, portfolio_stats, simulate_portfolio
from fxbt.report import PCT_COLS, PERIOD_LABEL, bench_rows, group_stats, md_table, portfolio_row, stats_rows
from fxbt.signals import compute_indicators, generate_signals
from fxbt.trades import TradeParams, evaluate_all

log = logging.getLogger("fx_backtest")


def load_daily(cfg: dict, fetcher: DukascopyFetcher, pairs: list[str], today: date):
    start, end = resolve_date_range(cfg["data"], today)
    tz = cfg["data"].get("day_boundary_tz", "America/New_York")
    hour = int(cfg["data"].get("day_boundary_hour", 17))
    daily, quality = {}, {}
    for pair in pairs:
        log.info("取得: %s %s〜%s", pair, start, end)
        hourly = fetcher.load_hourly(pair, start, end)
        d, info = hourly_to_daily(hourly, tz, hour)
        if d.empty:
            raise RuntimeError(f"{pair} のデータが取得できませんでした")
        daily[pair] = d
        quality[pair] = {**info, **quality_check(d, cfg.get("quality", {}))}
        cache = resolve_path(cfg, cfg["data"].get("cache_dir", "data")) / "daily" / f"{pair}.parquet"
        cache.parent.mkdir(parents=True, exist_ok=True)
        d.to_parquet(cache)
    return daily, quality, (start, end)


def compute_split(daily: dict[str, pd.DataFrame], split_cfg) -> pd.Timestamp:
    if split_cfg:
        return pd.Timestamp(split_cfg)
    lo = min(d.index.min() for d in daily.values())
    hi = max(d.index.max() for d in daily.values())
    return (lo + (hi - lo) / 2).normalize()


def build_trades(cfg: dict, daily: dict, pairs: list[str], split: pd.Timestamp, conv_pair: str | None):
    sc, ec, cc = cfg["signal"], cfg["exit"], cfg["costs"]
    pool_frames, rule_frames = [], []
    conv_close = daily[conv_pair]["close"] if conv_pair else None
    for pair in pairs:
        ind = compute_indicators(daily[pair], sc)
        sig = generate_signals(ind, sc)
        swap = cc.get("swap_pips_per_day", {}).get(pair, {})
        for n in ec["holding_days"]:
            p = TradeParams(
                holding_days=int(n),
                stop_atr_mult=float(ec["stop_atr_mult"]),
                pip=pip_size(pair),
                spread_pips=float(cc["spread_pips"].get(pair, 0.0)),
                take_profit_atr_mult=ec.get("take_profit_atr_mult"),
                swap_long_pips=float(swap.get("long", 0.0)),
                swap_short_pips=float(swap.get("short", 0.0)),
                triple_swap_weekday=int(cc.get("triple_swap_weekday", 2)),
            )
            out = evaluate_all(ind, p)
            out.insert(0, "pair", pair)
            out.insert(0, "holding_days", int(n))
            out.insert(0, "period", np.where(out["signal_date"] >= split, "second", "first"))
            if quote_currency(pair) == "JPY":
                rate = 1.0
            else:
                rate = conv_close.reindex(out["exit_date"]).ffill().bfill().to_numpy()
            out["pnl_jpy_10k"] = out["pnl_pips"] * p.pip * 10000 * rate
            out["pnl_jpy_10k_swap"] = out["pnl_pips_swap"] * p.pip * 10000 * rate
            pool_frames.append(out)
            sigdir = sig.reindex(out["signal_date"]).to_numpy()
            want = np.where(out["direction"] == "long", 1, -1)
            rule_frames.append(out[sigdir == want])
    return pd.concat(pool_frames, ignore_index=True), pd.concat(rule_frames, ignore_index=True)


def run(cfg: dict, fetcher: DukascopyFetcher | None = None, today: date | None = None) -> dict:
    today = today or pd.Timestamp.now(tz="UTC").date()
    pairs = list(cfg["pairs"])
    need_conv = any(quote_currency(p) != "JPY" for p in pairs)
    conv_pair = cfg.get("conversion_pair", "USDJPY") if need_conv else None
    load_pairs = pairs + ([conv_pair] if conv_pair and conv_pair not in pairs else [])
    cache_dir = resolve_path(cfg, cfg["data"].get("cache_dir", "data"))
    fetcher = fetcher or DukascopyFetcher(cfg["data"], cache_dir, today=today)
    daily, quality, (start, end) = load_daily(cfg, fetcher, load_pairs, today)

    split = compute_split({p: daily[p] for p in pairs}, cfg.get("split", {}).get("split_date"))
    pool, rule = build_trades(cfg, daily, pairs, split, conv_pair)

    bc = cfg.get("benchmark", {})
    bench = {}
    for period_code, period in enumerate(("first", "second")):
        for n in cfg["exit"]["holding_days"]:
            rng = np.random.default_rng([int(bc.get("seed", 42)), int(n), period_code])
            r_sel = rule[(rule["period"] == period) & (rule["holding_days"] == int(n))]
            p_sel = pool[(pool["period"] == period) & (pool["holding_days"] == int(n))]
            bench[(period, int(n))] = random_benchmark(
                r_sel, p_sel, int(bc.get("n_runs", 1000)), rng, float(bc.get("alpha", 0.05))
            )

    pc = cfg["portfolio"]
    spreads = {p: float(cfg["costs"]["spread_pips"].get(p, 0.0)) for p in pairs}
    pips = {p: pip_size(p) for p in pairs}
    first_ready = pool["signal_date"].min()
    last_date = max(d.index.max() for d in daily.values())
    bounds = {"first": (first_ready, split - pd.Timedelta(days=1)), "second": (split, last_date)}
    bars = {p: daily[p] for p in pairs}
    conv_bars = daily[conv_pair] if conv_pair else None
    port = {}
    for period, (lo, hi) in bounds.items():
        for n in cfg["exit"]["holding_days"]:
            tr = rule[(rule["period"] == period) & (rule["holding_days"] == int(n))]
            for mu in pc["min_units"]:
                for swap in (True, False):
                    if not swap and mu != pc["min_units"][0]:
                        continue
                    res = simulate_portfolio(tr, bars, conv_bars, pc, spreads, pips, lo, hi, float(mu), swap, pairs)
                    st = portfolio_stats(res, float(pc.get("tax_rate", 0.20315)), int(pc.get("tax_loss_carryforward_years", 3)))
                    port[(period, int(n), mu, swap)] = (res, st)

    out_dir = resolve_path(cfg, cfg.get("output", {}).get("dir", "output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    write_outputs(cfg, out_dir, rule, bench, port, quality, split, (start, end), daily, pairs, fetcher)
    return {"out_dir": out_dir, "rule": rule, "pool": pool, "bench": bench, "portfolio": port, "split": split}


TRADE_COLS = [
    "period",
    "holding_days",
    "signal_date",
    "entry_date",
    "exit_date",
    "pair",
    "direction",
    "entry_price",
    "exit_price",
    "stop_price",
    "atr",
    "pnl_pips",
    "swap_days",
    "swap_pips",
    "pnl_pips_swap",
    "pnl_jpy_10k",
    "pnl_jpy_10k_swap",
    "mae_pips",
    "exit_reason",
    "bars_held",
]


def write_outputs(cfg, out_dir: Path, rule, bench, port, quality, split, rng_months, daily, pairs, fetcher):
    rule.sort_values(["holding_days", "signal_date", "pair"])[TRADE_COLS].to_csv(
        out_dir / "fx_trades.csv", index=False, date_format="%Y-%m-%d"
    )
    pc = cfg["portfolio"]
    mu0 = pc["min_units"][0]
    eq_frames, pt_frames, monthly = [], [], {}
    for (period, n, mu, swap), (res, _st) in port.items():
        if mu == mu0 and swap:
            eq_frames.append(res.equity.assign(period=period, holding_days=n))
            if len(res.trades):
                pt_frames.append(res.trades.assign(period=period, holding_days=n))
            monthly[(period, n)] = monthly_pnl(res)
    if eq_frames:
        pd.concat(eq_frames).to_csv(out_dir / "fx_equity.csv", date_format="%Y-%m-%d")
    if pt_frames:
        pd.concat(pt_frames).to_csv(out_dir / "fx_portfolio_trades.csv", index=False, date_format="%Y-%m-%d")
    rule.assign(month=rule["signal_date"].dt.to_period("M")).pipe(
        lambda df: pd.concat([group_stats(g, "month").assign(holding_days=n) for n, g in df.groupby("holding_days")])
    ).to_csv(out_dir / "fx_monthly.csv", index=False)

    L = []
    w = L.append
    first = min(d.index.min() for d in daily.values()).date()
    last = max(d.index.max() for d in daily.values()).date()
    w("# FX 短期ブレイクアウト バックテスト結果（AI-239）\n")
    w(f"- 生成日時: {pd.Timestamp.now(tz='Asia/Tokyo'):%Y-%m-%d %H:%M} JST")
    w(
        f"- データ: Dukascopy 1 時間足（{cfg['data'].get('price_side', 'BID')}）→ NY 17:00（America/New_York, DST 考慮）区切りの日足"
    )
    w(f"- 期間: {first} 〜 {last}（取得月 {rng_months[0]:%Y-%m}〜{rng_months[1]:%Y-%m}）")
    w(f"- 前半/後半の分割日: {split.date()}（シグナル日がこの日以降なら後半。後半が主結果）")
    w(f"- 通貨ペア: {', '.join(pairs)}")
    sc, ec = cfg["signal"], cfg["exit"]
    w(
        f"- シグナル: 前日までの{sc['breakout_lookback']}日高値/安値ブレイク + 終値・{sc['ma_short']}日線・{sc['ma_long']}日線の並び、"
        f"当日値幅 > ATR({sc['atr_period']})×{sc['overheat_atr_mult']} は除外"
    )
    w(
        f"- エグジット: 保有 {ec['holding_days']} 営業日の終値、損切り ATR×{ec['stop_atr_mult']}、利確 {ec.get('take_profit_atr_mult') or 'なし'}"
    )
    w(
        f"- 資金: {pc['initial_capital']:,} 円、1 回のリスク {pc['risk_per_trade'] * 100:.1f}%、実効レバレッジ上限 {pc['max_leverage']} 倍、"
        f"同時保有 {pc['max_positions']}、ランダム比較 {cfg['benchmark']['n_runs']} 回（seed={cfg['benchmark']['seed']}）\n"
    )

    w("## 1. 主結果（後半・検証用）\n")
    w("### トレード成績（スプレッド込み。円は 1 万通貨あたり）\n")
    w(md_table(stats_rows(rule, ("second",)), PCT_COLS))
    w("### ランダムエントリー比較\n")
    w(md_table(bench_rows(bench, ("second",)), PCT_COLS))
    w("### 資金 10 万円シミュレーション（最小取引単位 " + f"{mu0} 通貨・スワップ込み）\n")
    w(
        md_table(
            [
                portfolio_row({"保有日数": n}, st)
                for (p, n, mu, sw), (_r, st) in port.items()
                if p == "second" and mu == mu0 and sw
            ],
            PCT_COLS,
        )
    )

    w("## 2. 前半（条件調整用）\n")
    w(md_table(stats_rows(rule, ("first",)), PCT_COLS))
    w(md_table(bench_rows(bench, ("first",)), PCT_COLS))
    w(
        md_table(
            [
                portfolio_row({"保有日数": n}, st)
                for (p, n, mu, sw), (_r, st) in port.items()
                if p == "first" and mu == mu0 and sw
            ],
            PCT_COLS,
        )
    )

    w("## 3. 資金シミュレーションの比較（最小取引単位・スワップ有無）\n")
    w(
        md_table(
            [
                portfolio_row({"期間": PERIOD_LABEL[p], "保有日数": n, "最小単位": mu, "スワップ": "込" if sw else "除く"}, st)
                for (p, n, mu, sw), (_r, st) in sorted(port.items(), key=lambda x: (x[0][0] != "second",) + x[0][1:3])
            ],
            PCT_COLS,
        )
    )

    w("## 4. 資産推移・月別損益・実効レバレッジ（後半、最小単位 " + f"{mu0} 通貨・スワップ込み）\n")
    ns = [n for (p, n) in monthly if p == "second"]
    if ns:
        mrows = []
        idx = sorted(set().union(*[monthly[("second", n)].index for n in ns]))
        for m in idx:
            r = {"月": str(m)}
            for n in ns:
                df = monthly[("second", n)]
                if m in df.index:
                    r[f"{n}日 月末資産"] = df.loc[m, "equity"]
                    r[f"{n}日 月間損益"] = df.loc[m, "pnl"]
                    r[f"{n}日 最大実効レバ"] = df.loc[m, "max_leverage"]
            mrows.append(r)
        w(md_table(mrows))
    w("税引き後損益は暦年ごとの実現損益に 20.315% を課税し、損失は 3 年繰越した概算。日次の資産推移は fx_equity.csv。\n")

    w("## 5. 通貨ペア別成績\n")
    for period in ("second", "first"):
        for n, g in rule[rule["period"] == period].groupby("holding_days"):
            w(f"### {PERIOD_LABEL[period]}・保有 {n} 日\n")
            w(md_table(group_stats(g, "pair").rename(columns={"区分": "通貨ペア"}), PCT_COLS))
    w("### 方向別（後半）\n")
    for n, g in rule[rule["period"] == "second"].groupby("holding_days"):
        w(f"保有 {n} 日\n")
        w(md_table(group_stats(g, "direction").rename(columns={"区分": "方向"}), PCT_COLS))

    w("## 6. 年別成績（全期間、シグナル日の年）\n")
    for n, g in rule.groupby("holding_days"):
        w(f"### 保有 {n} 日\n")
        w(md_table(group_stats(g, g["signal_date"].dt.year).rename(columns={"区分": "年"}), PCT_COLS))
    w("月別成績は fx_monthly.csv を参照。\n")

    w("## 7. データ品質\n")
    qrows = [
        {
            "通貨ペア": p,
            "日足本数": q["days"],
            "開始": q.get("first_date"),
            "終了": q.get("last_date"),
            "欠損営業日": q["missing_business_days"],
            "1時間足が少ない日": q["short_days"],
            "OHLC不整合": q["bad_ohlc"],
            "スパイク": q["spikes"],
            "出来高0の1時間足(除外)": q["zero_volume_hours"],
            "週末ラベル日(除外)": q["weekend_days_dropped"],
        }
        for p, q in quality.items()
    ]
    w(md_table(qrows))
    for p, q in quality.items():
        if q["spike_dates"]:
            w(f"- {p} のスパイク日: {', '.join(q['spike_dates'][:20])}")
        if q["missing_dates"]:
            w(f"- {p} の欠損営業日（先頭 20 件）: {', '.join(q['missing_dates'][:20])}")
    st = fetcher.stats
    w(
        f"\n取得: HTTP リクエスト {st.requests} 回（再試行 {st.retries} 回）、キャッシュ利用 {st.cache_hits} か月、"
        f"データなし（404）{len(st.missing_months)} か月。スパイクは記録のみで除外していない。\n"
    )

    w("## 8. 制約事項\n")
    for s in (
        "価格は Dukascopy の BID 足。スプレッドは通貨ペア別の固定値（仮値）で、実際の業者の変動スプレッド・約定拒否・スリッページは考慮していない。",
        "スワップは通貨ペア・方向別の 1 日あたり固定 pips（仮値）で、期間中の金利変動を反映していない。水曜ロールオーバーを 3 日分として数える。",
        "日足は NY 17:00 区切りで、日付は「その日の 17:00（NY）に終わるセッション」。祝日などで足がない日は営業日として数えない。",
        "損切りは日足の高値・安値で判定し、足の中の値動きの順序は分からない。始値が損切り価格を越えていればその始値で約定（窓開け）。",
        "ランダム比較は、ルールと同じ通貨ペア・方向・件数で、同じ期間の候補日から一様に選んだ場合の平均損益分布。エントリーのタイミングに意味があるかだけを見ている。",
        "資金シミュレーションはシグナルの通貨ペア順（config の pairs 順）に枠を割り当てる。同一通貨の偏りは max_positions_per_currency で制限できる（既定は制限なし）。",
        "EURUSD の損益は決済日の USDJPY 終値で円換算する。",
        "Dukascopy のデータは個人・非商用利用に限られ、再配布できない。本出力も公開しないこと。",
    ):
        w(f"- {s}")
    w("\n## 出力ファイル\n")
    w("- fx_trades.csv（ルールのトレード一覧）、fx_portfolio_trades.csv、fx_equity.csv、fx_monthly.csv、fx_summary.md")
    (out_dir / "fx_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FX 短期ブレイクアウト条件のバックテスト (AI-239)")
    ap.add_argument("--config", default="fx_config.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    res = run(cfg)
    log.info("出力: %s", res["out_dir"] / "fx_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

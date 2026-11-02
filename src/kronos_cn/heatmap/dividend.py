"""Dividend heatmap for a curated universe (e.g. FTSE China A50).

Input is a small table with one row per symbol::

    code,price,dps_fy,yield_fy_pct,yield_hist_mean_pct,yield_cv,div_years,
    vol_pct,mdd_pct,win_pct,ret250_pct,above_ma10m,last_date,score

``kronos-cn dividend --csv a50_dividend.csv`` renders a colour-coded card grid.
The score column is optional; if missing it is derived with :func:`score_row`.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from kronos_cn.heatmap.market import sina_url
from kronos_cn.heatmap.theme import CSS
from kronos_cn.names import get_name

YIELD_FLOOR = 3.0
REQUIRED = ("code", "yield_fy_pct")


def compute_score(row: pd.Series) -> float:
    """Blend yield, stability, volatility, drawdown and win-rate into 0–1.

    Weights: yield 40%, low volatility 20%, low drawdown 15%, monthly win-rate
    15%, yield stability 10%. Missing values fall back to neutral.
    """
    yield_pct = float(row.get("yield_fy_pct", 0) or 0)
    vol = float(row.get("vol_pct", 0) or 0)
    mdd = abs(float(row.get("mdd_pct", 0) or 0))
    win = float(row.get("win_pct", 50) or 50)
    cv = float(row.get("yield_cv", 0.5) or 0.5)

    yield_part = min(yield_pct / 8.0, 1.0)
    vol_part = max(0.0, 1.0 - vol / 60.0)
    mdd_part = max(0.0, 1.0 - mdd / 60.0)
    win_part = min(max(win / 100.0, 0.0), 1.0)
    cv_part = max(0.0, 1.0 - cv / 1.0)
    return round(
        0.40 * yield_part + 0.20 * vol_part + 0.15 * mdd_part + 0.15 * win_part + 0.10 * cv_part,
        3,
    )


def tier(row: pd.Series) -> str:
    years = int(row.get("div_years", 0) or 0)
    above = bool(row.get("above_ma10m", False))
    yield_pct = float(row.get("yield_fy_pct", 0) or 0)
    if years >= 3 and above and yield_pct >= YIELD_FLOOR:
        return "core"
    if years >= 3 and yield_pct >= YIELD_FLOOR:
        return "watch"
    return "weak"


def _color(score: float, lo: float, hi: float) -> str:
    t = 0.0 if hi == lo else (score - lo) / (hi - lo)
    c1, c2, c3 = (0.55, 0.60, 0.66), (0.35, 0.65, 0.48), (0.10, 0.35, 0.24)
    if t < 0.5:
        k = t / 0.5
        rgb = [c1[i] + (c2[i] - c1[i]) * k for i in range(3)]
    else:
        k = (t - 0.5) / 0.5
        rgb = [c2[i] + (c3[i] - c2[i]) * k for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*(int(x * 255) for x in rgb))


def _fmt(value, spec: str = "{:.2f}", dash: str = "—") -> str:
    return dash if pd.isna(value) else spec.format(value)


def prepare(csv: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv, dtype={"code": str})
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        raise ValueError("dividend table is missing: " + ", ".join(missing))
    frame["code"] = frame["code"].str.zfill(6)
    if "score" not in frame.columns:
        frame["score"] = frame.apply(compute_score, axis=1)
    frame["tier"] = frame.apply(tier, axis=1)
    frame["name"] = frame["code"].map(lambda c: get_name(c).replace("XD", "").strip())
    return frame.sort_values("score", ascending=False).reset_index(drop=True)


def render_dividend_html(frame: pd.DataFrame, title: str = "A50 稳定红利热力图") -> str:
    if frame.empty:
        raise ValueError("empty dividend table")
    lo, hi = float(frame["score"].min()), float(frame["score"].max())
    core = frame[frame["tier"] == "core"]
    watch = frame[frame["tier"] == "watch"]
    stamp = datetime.now().strftime("%Y-%m-%d")

    cards = []
    for _, row in frame.iterrows():
        url = sina_url(row["code"])
        badge = {"core": "核心", "watch": "观察", "weak": "弱"}[row["tier"]]
        trend = "趋势在" if bool(row.get("above_ma10m", False)) else "趋势破"
        inner = f"""
      <div class="top"><span class="code">{html.escape(row['code'])}</span><span class="b {row['tier']}">{badge}</span></div>
      <div class="name">{html.escape(str(row['name']))}</div>
      <div class="yield">{_fmt(row.get('yield_fy_pct'), '{:.2f}%')}</div>
      <div class="sub">股价 {_fmt(row.get('price'))} · 历史均值 {_fmt(row.get('yield_hist_mean_pct'), '{:.2f}%')}</div>
      <div class="sub">年化波动 {_fmt(row.get('vol_pct'), '{:.1f}%')} · 最大回撤 {_fmt(row.get('mdd_pct'), '{:.0f}%')}</div>
      <div class="sub">月胜率 {_fmt(row.get('win_pct'), '{:.0f}%')} · 分红 {int(row.get('div_years', 0) or 0)} 期</div>
      <div class="foot"><span class="{'ok' if bool(row.get('above_ma10m')) else 'bad'}">{trend}</span>
        <span>分 {float(row['score']):+.2f}</span></div>"""
        style = f'background:{_color(float(row["score"]), lo, hi)}'
        if url:
            cards.append(
                f'<a class="card" href="{url}" target="_blank" rel="noopener" style="{style}" '
                f'title="稳健红利分 {row["score"]}">{inner}</a>'
            )
        else:
            cards.append(f'<div class="card" style="{style}">{inner}</div>')

    top = "、".join(
        f"{row['name']}({row['yield_fy_pct']:.1f}%)" for _, row in core.head(5).iterrows()
    ) or "无"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · {stamp}</title>
<style>
{CSS}
body {{ background:#0f1417; }}
main {{ max-width: 1400px; margin: 0 auto; padding: 24px 22px 60px; }}
h1 {{ font-size: 21px; margin: 0 0 8px; }}
.lede {{ color:#9fb0bb; font-size:13px; margin-bottom:18px; line-height:1.8; max-width: 980px; }}
.lede b {{ color:#e8eef2; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:11px; }}
.card {{ border-radius:12px; padding:11px 12px; color:#0d1418; min-height:140px;
  box-shadow:0 2px 10px rgba(0,0,0,.35); text-decoration:none; display:block;
  transition:transform .12s ease, box-shadow .12s ease; }}
a.card:hover {{ transform:translateY(-2px) scale(1.015); box-shadow:0 8px 22px rgba(0,0,0,.5); }}
.card .top {{ display:flex; justify-content:space-between; align-items:center; font-size:11px; opacity:.85; }}
.card .name {{ font-size:15px; font-weight:700; margin:2px 0 0; }}
.card .yield {{ font-size:27px; font-weight:800; line-height:1.15; }}
.card .sub {{ font-size:10.5px; opacity:.8; line-height:1.55; }}
.card .foot {{ display:flex; justify-content:space-between; font-size:10.5px; margin-top:4px; opacity:.9; }}
.b {{ border-radius:9px; padding:1px 7px; font-size:10px; }}
.b.core {{ background:#f5c542; color:#1b1b1b; }}
.b.watch {{ background:rgba(255,255,255,.55); }}
.b.weak {{ background:rgba(255,255,255,.3); }}
.ok {{ color:#0b5d3b; font-weight:600; }}
.bad {{ color:#8a2d1f; font-weight:600; }}
.legend {{ margin:14px 0 18px; font-size:12px; color:#9fb0bb; display:flex; gap:16px; flex-wrap:wrap; }}
</style></head><body>
<main>
<h1>{html.escape(title)} · {stamp}</h1>
<div class="lede">
数字是<b>最近完整年度股息率</b>，色深是<b>稳健红利分</b>（股息率 40% + 低波动 20% + 低回撤 15% + 月胜率 15% + 稳定性 10%）。<br>
<b>核心</b> = 连续分红 ≥3 期、股息率 ≥{YIELD_FLOOR:.0f}%、且月线仍在 10 月线上方。当前核心：{html.escape(top)}。
</div>
<div class="legend"><span>核心 {len(core)} 只</span><span>观察 {len(watch)} 只</span><span>合计 {len(frame)} 只</span></div>
<div class="grid">{''.join(cards)}</div>
</main></body></html>
"""


def write_dividend_heatmap(csv: str | Path, out: str | Path, title: str = "A50 稳定红利热力图") -> Path:
    frame = prepare(csv)
    out = Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_dividend_html(frame, title=title), encoding="utf-8")
    return out

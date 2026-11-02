"""Market heatmap: weekly / monthly / quarterly / yearly moves in one page.

Each square is one symbol. Colour is the period change, area is the traded
amount (volume) in that period. Clicking a square opens the Sina quote page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from kronos_cn.config import Settings, is_a_share
from kronos_cn.heatmap.theme import CSS, JS, METRIC_LABELS, color_for, foreground, legend_items
from kronos_cn.names import get_name

METRICS = ("wk", "mo", "qtd", "ytd")
MIN_ROWS = 25
SINA_A = "https://finance.sina.com.cn/realstock/company/{prefix}{code}/nc.shtml"
SINA_US = "https://stock.finance.sina.com.cn/usstock/quotes/{ticker}.html"


@dataclass(frozen=True)
class Snapshot:
    code: str
    name: str
    close: float
    as_of: date | None
    wk: float
    mo: float
    qtd: float
    ytd: float
    wk_vol: float
    mo_vol: float
    qtd_vol: float
    ytd_vol: float
    trend: str  # "up" | "down" | "flat" | "n/a"
    url: str | None

    def change(self, metric: str) -> float:
        return float(getattr(self, metric))

    def volume(self, metric: str) -> float:
        return float(getattr(self, f"{metric}_vol"))


def sina_url(code: str) -> str | None:
    """Deep link to the Sina quote page, or ``None`` for unsupported symbols."""
    code = str(code).strip().upper()
    if is_a_share(code):
        prefix = "sh" if code.startswith(("60", "68", "90")) else (
            "bj" if code.startswith(("4", "8")) else "sz"
        )
        return SINA_A.format(prefix=prefix, code=code)
    if code.endswith("USA"):
        ticker = code[:-3]
        if ticker in {"BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"}:
            return None
        return SINA_US.format(ticker=ticker)
    return None


def _pct(latest: float, previous: float) -> float:
    return float("nan") if not previous else (latest / previous - 1.0) * 100.0


def compute_snapshot(code: str, frame: pd.DataFrame, name: str | None = None) -> Snapshot | None:
    """Build one heatmap row from a canonical daily frame."""
    if "date" not in frame.columns or len(frame) < MIN_ROWS:
        return None
    if "close" not in frame.columns or "volume" not in frame.columns:
        return None

    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    if len(frame) < MIN_ROWS:
        return None

    series = frame.set_index("date")["close"].astype(float)
    weekly = series.resample("W-FRI").last().dropna()
    monthly = series.resample("ME").last().dropna()
    quarterly = series.resample("QE").last().dropna()
    yearly = series.resample("YE").last().dropna()
    if len(weekly) < 2 or len(monthly) < 2:
        return None

    latest = float(series.iloc[-1])
    volumes = frame.set_index("date")["volume"].astype(float)

    trend = "n/a"
    if len(weekly) >= 15:
        ma = weekly.rolling(10).mean()
        if latest > ma.iloc[-1] and ma.iloc[-1] > ma.iloc[-6]:
            trend = "up"
        elif latest < ma.iloc[-1] and ma.iloc[-1] < ma.iloc[-6]:
            trend = "down"
        else:
            trend = "flat"

    return Snapshot(
        code=code,
        name=name or get_name(code),
        close=latest,
        as_of=series.index[-1].date(),
        wk=_pct(float(weekly.iloc[-1]), float(weekly.iloc[-2])),
        mo=_pct(latest, float(monthly.iloc[-2])),
        qtd=_pct(latest, float(quarterly.iloc[-2])) if len(quarterly) >= 2 else 0.0,
        ytd=_pct(latest, float(yearly.iloc[-2])) if len(yearly) >= 2 else 0.0,
        wk_vol=float(volumes.resample("W-FRI").sum().iloc[-1]),
        mo_vol=float(volumes.resample("ME").sum().iloc[-1]),
        qtd_vol=float(volumes.resample("QE").sum().iloc[-1]),
        ytd_vol=float(volumes.resample("YE").sum().iloc[-1]),
        trend=trend,
        url=sina_url(code),
    )


def load_snapshots(data_dir: str | Path) -> tuple[list[Snapshot], list[tuple[str, str]]]:
    """Read every ``*_kronos.csv`` in a directory."""
    directory = Path(data_dir).expanduser()
    snapshots: list[Snapshot] = []
    skipped: list[tuple[str, str]] = []

    for path in sorted(directory.glob("*_kronos.csv")):
        code = path.name[: -len("_kronos.csv")]
        try:
            frame = pd.read_csv(path)
        except (OSError, pd.errors.ParserError) as exc:
            skipped.append((code, f"unreadable: {exc}"))
            continue
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        snapshot = compute_snapshot(code, frame)
        if snapshot is None:
            reason = "no date column" if "date" not in frame.columns else "too few rows"
            skipped.append((code, reason))
            continue
        snapshots.append(snapshot)

    return snapshots, skipped


def _cell(snapshot: Snapshot, metric: str, max_volume: float, scheme: str = "cn") -> str:
    value = snapshot.change(metric)
    share = snapshot.volume(metric) / max_volume if max_volume else 0.0
    size = 42 + 150 * (share**0.7)
    background = color_for(value, metric, scheme)
    trend = {"up": "▲", "down": "▼", "flat": "—"}.get(snapshot.trend, "")
    label = html.escape(f"{snapshot.code} {snapshot.name} {value:+.2f}%")
    name_length = max(len(snapshot.name), 1)
    font_size = min(13.0, max(8.0, (size - 12) / name_length))
    show_code = size >= 58
    show_trend = size >= 70 and bool(snapshot.trend)
    inner = (
        (f'<div class="code">{html.escape(snapshot.code)}</div>' if show_code else "")
        + f'<div class="name" style="font-size:{font_size:.1f}px">{html.escape(snapshot.name)}</div>'
        + f'<div class="pct">{value:+.1f}%</div>'
        + (f'<div class="trend">{trend}</div>' if show_trend else "")
    )
    attrs = (
        f'class="cell" data-code="{html.escape(snapshot.code)}" '
        f'data-name="{html.escape(snapshot.name)}" data-chg="{value:.4f}" '
        f'data-vol="{snapshot.volume(metric):.0f}" data-size="{size:.0f}" '
        f'style="width:{size:.0f}px;height:{size:.0f}px;background:{background};'
        f'color:{foreground(value)}" title="{label}"'
    )
    if snapshot.url:
        return f'<a {attrs} href="{snapshot.url}" target="_blank" rel="noopener">{inner}</a>'
    return f'<div {attrs}>{inner}</div>'


def _legend(metric: str, scheme: str = "cn") -> str:
    return "".join(
        f'<span><i class="sw" style="background:{colour}"></i>{html.escape(label)}</span>'
        for label, colour in legend_items(metric, scheme)
    )


def render_html(
    snapshots: list[Snapshot],
    title: str = "Kronos 市场云图",
    initial: str = "wk",
    note: str = "",
    scheme: str = "cn",
) -> str:
    if not snapshots:
        raise ValueError("no snapshots to render")

    as_of = max((s.as_of for s in snapshots if s.as_of), default=None)
    weekly = [s.wk for s in snapshots if pd.notna(s.wk)]
    up = sum(1 for v in weekly if v > 0)
    down = sum(1 for v in weekly if v < 0)
    flat = len(weekly) - up - down
    median = sorted(weekly)[len(weekly) // 2] if weekly else 0.0
    total = max(up + down + flat, 1)
    up_pct, down_pct = up / total * 100, down / total * 100

    grids = {}
    for metric in METRICS:
        ordered = sorted(snapshots, key=lambda s: s.change(metric), reverse=True)
        max_volume = max((s.volume(metric) for s in ordered), default=0.0)
        cells = "\n".join(_cell(s, metric, max_volume, scheme) for s in ordered)
        hidden = "" if metric == initial else ' style="display:none"'
        grids[metric] = f'<div class="grid" id="grid-{metric}"{hidden}>\n{cells}\n</div>'

    options = "".join(
        f'<option value="{m}"{" selected" if m == initial else ""}>{html.escape(METRIC_LABELS[m])}</option>'
        for m in METRICS
    )
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    up_colour, down_colour = (("#E53935", "#2E7D32") if scheme == "cn" else ("#2E7D32", "#E53935"))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <div>
    <h1>{html.escape(title)}</h1>
    <div class="meta">{len(snapshots)} 个标的 · 数据截至 {as_of or "-"} · 生成于 {generated}</div>
  </div>
  <div class="spacer"></div>
  <div class="controls">
    <input id="q" type="search" placeholder="搜索代码 / 名称" autocomplete="off">
    <select id="sort" title="排序">
      <option value="abs">按涨跌幅绝对值</option>
      <option value="chg">按涨幅从高到低</option>
      <option value="vol">按成交量</option>
      <option value="name">按名称</option>
    </select>
    <select id="metric" title="切换周期">{options}</select>
    <label class="meta"><input type="checkbox" id="size" checked> 面积=成交量</label>
  </div>
</header>
<div class="summary">
  <div class="stat"><b>{len(snapshots)}</b>标的</div>
  <div class="stat"><b style="color:{up_colour}">{up}</b>上涨</div>
  <div class="stat"><b style="color:{down_colour}">{down}</b>下跌</div>
  <div class="stat"><b>{flat}</b>平盘</div>
  <div class="stat"><b>{median:+.2f}%</b>周涨跌中位数</div>
  <div class="breadth"><i style="width:{up_pct:.1f}%;background:{up_colour}"></i><i style="width:{down_pct:.1f}%;background:{down_colour}"></i></div>
</div>
<div class="legend" id="legend">{_legend(initial, scheme)}</div>
<main>
{''.join(grids[m] for m in METRICS)}
</main>
<footer>{html.escape(note) if note else ""}<br>
格子颜色=周期涨跌幅，面积=该周期成交量；▲/▼ 表示价格相对 10 周均线的位置。<br>
数据仅用于研究与教学，不构成任何投资建议。</footer>
<script>
const LEGENDS = {{
{",".join(f'"{m}": `{_legend(m, scheme)}`' for m in METRICS)}
}};
const metricSel = document.getElementById('metric');
function switchMetric() {{
  const m = metricSel.value;
  document.querySelectorAll('.grid').forEach(g => {{
    g.style.display = (g.id === 'grid-' + m) ? 'flex' : 'none';
  }});
  document.getElementById('legend').innerHTML = LEGENDS[m];
  applySort();
}}
metricSel.addEventListener('change', switchMetric);
{JS}
</script>
</body>
</html>
"""


def write_heatmap(
    data_dir: str | Path,
    out: str | Path,
    title: str = "Kronos 市场云图",
    initial: str = "wk",
    note: str = "",
    scheme: str = "cn",
) -> tuple[Path, list[Snapshot], list[tuple[str, str]]]:
    """Generate the heatmap file. Returns (path, snapshots, skipped)."""
    if initial not in METRICS:
        raise ValueError(f"initial metric must be one of {METRICS}")
    snapshots, skipped = load_snapshots(data_dir)
    if not snapshots:
        raise ValueError(f"no usable data under {data_dir} (run `kronos-cn validate`)")
    out = Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_html(snapshots, title=title, initial=initial, note=note, scheme=scheme), encoding="utf-8"
    )
    return out, snapshots, skipped


def write_sample_heatmap(settings: Settings | None = None) -> Path:
    """Convenience wrapper used by ``kronos-cn demo``."""
    settings = (settings or Settings.load()).ensure_dirs()
    out = settings.output_dir / "heatmap.html"
    write_heatmap(settings.data_dir, out)
    return out

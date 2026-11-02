"""Shared palette and CSS for the HTML heatmaps.

Two colour conventions are supported:

``cn``   red = up, green = down (mainland China convention) — default
``intl`` green = up, red = down (western convention)

Thresholds are the same in both; only the colour ramp is swapped.
"""

from __future__ import annotations

UP_DEEP = "#B71C1C"
UP = "#E53935"
UP_LIGHT = "#EF9A9A"
FLAT = "#BDBDBD"
DOWN_LIGHT = "#66BB6A"
DOWN = "#2E7D32"
DOWN_DEEP = "#1B5E20"

#: Change buckets per metric, in percent, high → low.
BUCKETS: dict[str, dict[str, list[float]]] = {
    "wk": {"pos": [3, 1.5, 0.5], "neg": [-1.5, -3, -999]},
    "mo": {"pos": [8, 4, 1], "neg": [-4, -8, -999]},
    "qtd": {"pos": [15, 8, 2], "neg": [-8, -15, -999]},
    "ytd": {"pos": [30, 15, 5], "neg": [-15, -30, -999]},
}

SCHEMES = {
    "cn": {"pos": (UP_DEEP, UP, UP_LIGHT), "neg": (DOWN_LIGHT, DOWN, DOWN_DEEP), "flat": FLAT},
    "intl": {"pos": (DOWN_DEEP, DOWN, DOWN_LIGHT), "neg": (UP_LIGHT, UP, UP_DEEP), "flat": FLAT},
}

METRIC_LABELS = {
    "wk": "周涨幅",
    "mo": "月涨幅 (MTD)",
    "qtd": "季涨幅 (QTD)",
    "ytd": "年涨幅 (YTD)",
}

CSS = """
:root {
  --bg: #0b0d12;
  --panel: #141824;
  --panel-2: #1b2030;
  --line: #2a3142;
  --text: #e8eef2;
  --muted: #93a1b1;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, "PingFang SC", "Heiti SC", "Microsoft YaHei", sans-serif;
}
header {
  position: sticky; top: 0; z-index: 20; backdrop-filter: blur(8px);
  background: rgba(11, 13, 18, .86); border-bottom: 1px solid var(--line);
  padding: 14px 22px; display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
}
h1 { font-size: 17px; margin: 0; font-weight: 650; letter-spacing: .2px; }
.meta { color: var(--muted); font-size: 12px; }
.spacer { flex: 1; }
.controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
select, input[type="search"] {
  background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
  border-radius: 8px; padding: 7px 10px; font-size: 13px; outline: none;
}
input[type="search"] { width: 190px; }
input[type="search"]:focus, select:focus { border-color: #4b5b78; }
.summary { padding: 14px 22px 4px; display: flex; gap: 22px; flex-wrap: wrap; align-items: baseline; }
.stat { font-size: 13px; color: var(--muted); }
.stat b { font-size: 20px; color: var(--text); font-weight: 650; margin-right: 4px; }
.breadth { height: 6px; width: 180px; border-radius: 4px; overflow: hidden; display: flex; }
.breadth i { display: block; height: 100%; }
main { padding: 10px 18px 40px; }
.grid { display: flex; flex-wrap: wrap; gap: 7px; align-content: flex-start; }
.cell {
  border-radius: 8px; display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 4px; text-decoration: none; color: inherit;
  transition: transform .12s ease, box-shadow .12s ease; overflow: hidden;
}
.cell:hover { transform: scale(1.07); z-index: 10; box-shadow: 0 0 0 2px rgba(255,255,255,.55); }
.code { font-size: 10.5px; opacity: .82; letter-spacing: .3px; }
.name {
  font-weight: 700; margin: 2px 0; text-align: center; line-height: 1.1;
  white-space: nowrap; max-width: 100%;
}
.pct { font-size: 11.5px; font-variant-numeric: tabular-nums; }
.trend { font-size: 9px; opacity: .75; margin-top: 1px; }
.legend { padding: 6px 22px 0; display: flex; gap: 12px; flex-wrap: wrap; color: var(--muted); font-size: 12px; }
.legend .sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 5px; vertical-align: -2px; }
.empty { color: var(--muted); padding: 40px; }
footer { color: var(--muted); font-size: 11.5px; padding: 0 22px 30px; line-height: 1.7; }
@media (max-width: 720px) { header { padding: 12px; } main { padding: 8px; } .cell .trend { display: none; } }
"""

JS = """
const cells = Array.from(document.querySelectorAll('.cell'));
const search = document.getElementById('q');
const sortSel = document.getElementById('sort');
const grids = Array.from(document.querySelectorAll('.grid'));
const sizer = document.getElementById('size');

function activeGrid() { return grids.find(g => g.style.display !== 'none'); }

function applyFilter() {
  const q = (search.value || '').trim().toLowerCase();
  cells.forEach(c => {
    const hit = !q || c.dataset.code.includes(q) || (c.dataset.name || '').toLowerCase().includes(q);
    c.style.display = hit ? '' : 'none';
  });
}

function applySort() {
  const g = activeGrid();
  if (!g) return;
  const mode = sortSel.value;
  const kids = Array.from(g.children);
  kids.sort((a, b) => {
    if (mode === 'name') return (a.dataset.name || '').localeCompare(b.dataset.name || '', 'zh');
    if (mode === 'vol') return Number(b.dataset.vol) - Number(a.dataset.vol);
    if (mode === 'chg') return Number(b.dataset.chg) - Number(a.dataset.chg);
    return Math.abs(Number(b.dataset.chg)) - Math.abs(Number(a.dataset.chg));
  });
  kids.forEach(k => g.appendChild(k));
}

function applySize() {
  const on = sizer.checked;
  cells.forEach(c => {
    const px = on ? Number(c.dataset.size) : 96;
    c.style.width = px + 'px';
    c.style.height = px + 'px';
  });
}

search.addEventListener('input', applyFilter);
sortSel.addEventListener('change', applySort);
sizer.addEventListener('change', applySize);
applySize();
"""


def color_for(value: float, metric: str, scheme: str = "cn") -> str:
    """Pick the background colour for a period change."""
    palette = SCHEMES.get(scheme, SCHEMES["cn"])
    buckets = BUCKETS[metric]
    for threshold, colour in zip(buckets["pos"], palette["pos"], strict=True):
        if value >= threshold:
            return colour
    for threshold, colour in zip(buckets["neg"], palette["neg"], strict=True):
        if value <= threshold:
            return colour
    return palette["flat"]


def foreground(value: float) -> str:
    return "#ffffff" if abs(value) >= 1.5 else "#161a22"


def legend_items(metric: str, scheme: str = "cn") -> list[tuple[str, str]]:
    """(label, colour) pairs for the legend, high → flat → low."""
    palette = SCHEMES.get(scheme, SCHEMES["cn"])
    buckets = BUCKETS[metric]
    items = [
        (f"≥ {threshold:+g}%", colour)
        for threshold, colour in zip(buckets["pos"], palette["pos"], strict=True)
    ]
    items.append(("平盘", palette["flat"]))
    items.extend(
        (f"≤ {threshold:+g}%", colour)
        for threshold, colour in zip(buckets["neg"][:2], palette["neg"][:2], strict=True)
    )
    items.append(("深跌", palette["neg"][2]))
    return items

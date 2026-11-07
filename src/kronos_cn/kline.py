"""Candlestick charts for daily / weekly / monthly bars."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from kronos_cn.config import normalize_code
from kronos_cn.data.convert import to_period
from kronos_cn.names import get_name

PERIOD_LABELS = {"D": "日K", "W": "周K", "M": "月K"}
DEFAULT_BARS = {"D": 180, "W": 120, "M": 60}
UP = "#d33b3b"
DOWN = "#2a9d5c"
GRID = "#e6e6e6"


def _candles(ax, frame: pd.DataFrame) -> None:
    x = np.arange(len(frame))
    opens = frame["open"].to_numpy(float)
    closes = frame["close"].to_numpy(float)
    highs = frame["high"].to_numpy(float)
    lows = frame["low"].to_numpy(float)

    colours = np.where(closes >= opens, UP, DOWN)
    ax.vlines(x, lows, highs, color=colours, linewidth=0.9, zorder=3)

    span = float(np.nanmax(highs) - np.nanmin(lows)) or 1.0
    bodies = np.maximum(np.abs(closes - opens), span * 0.0012)
    bottoms = np.minimum(opens, closes)
    ax.bar(
        x,
        bodies,
        bottom=bottoms,
        width=0.62,
        color=colours,
        edgecolor=colours,
        linewidth=0.4,
        zorder=4,
    )


def _ticks(ax, frame: pd.DataFrame, period: str) -> None:
    dates = pd.to_datetime(frame["date"])
    step = max(len(frame) // 5, 1)
    positions = list(range(0, len(frame), step))
    if positions[-1] != len(frame) - 1:
        positions.append(len(frame) - 1)
    labels = [
        dates.iloc[i].strftime("%y-%m" if period == "M" else "%y-%m-%d")
        for i in positions
    ]
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=8)


def _volume_formatter(value, _position=None) -> str:
    if value >= 1e8:
        return f"{value / 1e8:.1f}亿"
    if value >= 1e4:
        return f"{value / 1e4:.0f}万"
    return f"{value:.0f}"


def _panel(price_ax, volume_ax, frame: pd.DataFrame, period: str) -> None:
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    _candles(price_ax, frame)

    for window, colour in ((5, "#e08a3c"), (10, "#4a7ebb"), (20, "#7d5ba6")):
        if len(frame) >= window:
            price_ax.plot(
                np.arange(len(frame)),
                frame["close"].rolling(window).mean(),
                color=colour,
                linewidth=0.9,
                alpha=0.75,
                label=f"MA{window}",
            )

    price_ax.grid(True, color=GRID, linewidth=0.7, alpha=0.8)
    price_ax.set_axisbelow(True)
    price_ax.set_ylabel("Price", fontsize=9)
    price_ax.tick_params(axis="x", labelbottom=False)
    price_ax.legend(loc="upper left", fontsize=7, frameon=False, ncol=3)

    closes = frame["close"].to_numpy(float)
    opens = frame["open"].to_numpy(float)
    colours = np.where(closes >= opens, UP, DOWN)
    volume_ax.bar(np.arange(len(frame)), frame["volume"], color=colours, width=0.62, alpha=0.45)
    volume_ax.grid(True, color=GRID, linewidth=0.7, alpha=0.8)
    volume_ax.set_axisbelow(True)
    volume_ax.set_ylabel("Volume", fontsize=8)
    volume_ax.yaxis.set_major_formatter(FuncFormatter(_volume_formatter))
    volume_ax.yaxis.set_major_locator(MaxNLocator(3))
    volume_ax.tick_params(axis="y", labelsize=7)
    _ticks(volume_ax, frame, period)


def plot_kline_grid(
    daily: pd.DataFrame,
    code: str,
    out: str | Path,
    periods: tuple[str, ...] = ("D", "W", "M"),
    bars: dict[str, int] | None = None,
    dpi: int = 150,
) -> Path:
    """Render one candlestick panel per period and save a single PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    bars = {**DEFAULT_BARS, **(bars or {})}
    frames = {}
    for period in periods:
        frame = to_period(daily, period)
        frames[period] = frame.tail(bars.get(period, DEFAULT_BARS[period])).reset_index(drop=True)

    rows = len(periods) * 2
    height = 3.6 * len(periods) + 1.0
    figure, axes = plt.subplots(
        rows,
        1,
        figsize=(14, height),
        gridspec_kw={"height_ratios": [3, 1] * len(periods)},
    )
    axes = np.atleast_1d(axes)
    figure.subplots_adjust(left=0.065, right=0.985, top=0.93, bottom=0.05, hspace=0.55)

    for index, period in enumerate(periods):
        frame = frames[period]
        price_ax = axes[index * 2]
        volume_ax = axes[index * 2 + 1]
        _panel(price_ax, volume_ax, frame, period)
        latest = frame.iloc[-1]
        previous = frame["close"].iloc[-2] if len(frame) > 1 else frame["open"].iloc[-1]
        change = (latest["close"] / previous - 1) * 100
        price_ax.set_title(
            f"{PERIOD_LABELS.get(period, period)} · {len(frame)} 根 · "
            f"收 {latest['close']:.2f}（{change:+.2f}%）",
            fontsize=10,
            loc="left",
            pad=8,
        )
        if index < len(periods) - 1:
            volume_ax.set_xlabel("")

    name = get_name(normalize_code(code))
    as_of = pd.to_datetime(daily["date"].iloc[-1]).strftime("%Y-%m-%d")
    figure.suptitle(f"{normalize_code(code)} {name} · K 线 · 数据截至 {as_of}", fontsize=13, y=0.985)

    out = Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(figure)
    return out

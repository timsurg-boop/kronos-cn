"""Forecast chart: history, prediction and projected change."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def plot_forecast(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    out: str | Path,
    title: str = "",
    lookback: int = 120,
    dpi: int = 150,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    past = history.tail(lookback).reset_index(drop=True)
    x_hist = list(range(len(past)))
    x_pred = list(range(len(past) - 1, len(past) + len(forecast)))

    figure, (price_ax, volume_ax) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    price_ax.plot(x_hist, past["close"], color="#2f6fb3", lw=1.3, label="History")
    price_ax.plot(
        [x_hist[-1]] + x_pred[1:],
        [float(past["close"].iloc[-1])] + list(forecast["close"]),
        color="#c0392b",
        lw=2,
        ls="--",
        label="Forecast",
    )

    prices = np.concatenate([past["close"].to_numpy(float), forecast["close"].to_numpy(float)])
    span = float(prices.max() - prices.min()) or max(float(prices.max()) * 0.02, 1.0)
    steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    target = span / 8
    step = min(steps, key=lambda s: abs(s - target))
    price_ax.yaxis.set_major_locator(ticker.MultipleLocator(step))
    price_ax.grid(alpha=0.3)
    price_ax.set_ylabel("Price")
    price_ax.legend(loc="upper left")

    change_ax = price_ax.twinx()
    base = float(past["close"].iloc[-1])
    change_ax.plot(x_hist, (past["close"] / base - 1) * 100, color="#7fbf7f", lw=0.9, ls=":", label="Hist %")
    change_ax.plot(
        [x_hist[-1]] + x_pred[1:],
        [0.0] + [(float(v) / base - 1) * 100 for v in forecast["close"]],
        color="#1e6b3a",
        lw=1.4,
        label="Forecast %",
    )
    change_ax.axhline(0, color="gray", lw=0.8, alpha=0.5)
    change_ax.set_ylabel("Change (%)")

    volume_ax.bar(x_hist, past["volume"], color="#4a7ebb", alpha=0.6, label="History volume")
    volume_ax.bar(x_pred[1:], forecast["volume"], color="#e08a3c", alpha=0.45, label="Forecast volume")
    volume_ax.set_ylabel("Volume")
    volume_ax.grid(alpha=0.3)
    volume_ax.legend(loc="upper left", fontsize=8)

    if title:
        price_ax.set_title(title, fontsize=12)

    figure.tight_layout()
    out = Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(figure)
    return out

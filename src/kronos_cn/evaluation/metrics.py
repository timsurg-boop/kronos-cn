"""Pure evaluation maths — no model, no I/O, easy to unit-test."""

from __future__ import annotations

import numpy as np
import pandas as pd


def spearman(a, b) -> float:
    """Spearman rank correlation; NaN when fewer than three pairs."""
    left = pd.Series(list(a), dtype="float64")
    right = pd.Series(list(b), dtype="float64")
    mask = left.notna() & right.notna()
    if mask.sum() < 3:
        return float("nan")
    return float(left[mask].rank().corr(right[mask].rank()))


def forward_return(close: pd.Series, index: int, horizon: int) -> float:
    """Percent return from ``index`` to ``index + horizon``."""
    if index + horizon >= len(close) or index < 0:
        raise IndexError("horizon exceeds the series")
    base = float(close.iloc[index])
    return (float(close.iloc[index + horizon]) / base - 1.0) * 100.0


def top_mean(frame: pd.DataFrame, column: str, k: int, ascending: bool = False) -> float:
    """Mean of the k best-ranked rows by ``column`` (NaN if too few rows)."""
    if len(frame) < k:
        return float("nan")
    ordered = frame.sort_values(column, ascending=ascending)
    return float(ordered.head(k)["actual"].mean())


def summarize_ic(series: pd.Series) -> dict[str, float]:
    values = pd.Series(series).dropna()
    if values.empty:
        return {"mean": float("nan"), "std": float("nan"), "ir": float("nan"), "hit": float("nan")}
    std = float(values.std(ddof=1)) if len(values) > 1 else float("nan")
    return {
        "mean": float(values.mean()),
        "std": std,
        "ir": float(values.mean() / std) if std and not np.isnan(std) else float("nan"),
        "hit": float((values > 0).mean() * 100),
    }


def net_value(returns_pct: pd.Series) -> pd.Series:
    """Compound percent returns into a net-value curve starting at 1.0."""
    return (1.0 + pd.Series(returns_pct).fillna(0.0) / 100.0).cumprod()


def max_drawdown(nav: pd.Series) -> float:
    values = pd.Series(nav).dropna()
    if values.empty:
        return float("nan")
    peak = values.cummax()
    return float((values / peak - 1.0).min() * 100.0)

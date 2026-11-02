"""Normalization and period aggregation.

The on-disk format is intentionally boring::

    date,open,high,low,close,volume,amount

That is exactly what Kronos expects, and it keeps heatmap/eval code free of
provider quirks.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from kronos_cn.config import REQUIRED_COLUMNS

RENAME = {
    "trade_date": "date",
    "datetime": "date",
    "time": "date",
    "vol": "volume",
    "turnover": "amount",
}

AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "amount": "sum",
}

PERIODS = {"D": None, "W": "W-FRI", "M": "ME", "Q": "QE", "Y": "YE"}


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename provider columns, coerce types, sort and de-duplicate."""
    frame = frame.rename(columns={k: v for k, v in RENAME.items() if k in frame.columns})
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError("missing columns: " + ", ".join(missing))

    out = frame.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date")
        out = out.drop_duplicates(subset=["date"], keep="last")
    for column in REQUIRED_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    columns = (["date"] if "date" in out.columns else []) + list(REQUIRED_COLUMNS)
    return out[columns].reset_index(drop=True)


def to_period(frame: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Aggregate daily bars into weekly/monthly/quarterly/yearly bars."""
    if freq not in PERIODS:
        raise ValueError(f"freq must be one of {sorted(PERIODS)}")
    if PERIODS[freq] is None:
        return normalize(frame)
    if "date" not in frame.columns:
        raise ValueError("a 'date' column is required to aggregate periods")

    indexed = normalize(frame).set_index("date")
    out = indexed.resample(PERIODS[freq]).agg(AGG).dropna(subset=["close"]).reset_index()
    return out


def convert_file(src: str | Path, dst: str | Path, freq: str = "D") -> int:
    """Read a provider export, normalize it and write the canonical CSV."""
    frame = pd.read_csv(src)
    out = to_period(frame, freq) if freq != "D" else normalize(frame)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dst, index=False)
    return len(out)

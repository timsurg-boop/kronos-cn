"""Data-quality checks for ``*_kronos.csv`` files.

Catching a broken series here is much cheaper than debugging a silently wrong
heatmap later, so the CLI exposes this as ``kronos-cn validate``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from kronos_cn.config import REQUIRED_COLUMNS

MAX_GAP_DAYS = 30  # long holidays and trading halts are legitimate
CRYPTO = {"BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"}


def _is_crypto(code: str) -> bool:
    code = code.upper()
    return code.endswith("USA") and code[:-3] in CRYPTO


@dataclass
class Report:
    code: str
    rows: int = 0
    start: date | None = None
    end: date | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def load_frame(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame


def validate_frame(frame: pd.DataFrame, code: str = "") -> Report:
    report = Report(code=code, rows=len(frame))
    if frame.empty:
        report.issues.append("empty file")
        return report

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        report.issues.append("missing columns: " + ", ".join(missing))
    if "date" not in frame.columns:
        report.issues.append("missing 'date' column (dates were lost on export)")
        return report

    dates = frame["date"]
    if dates.isna().any():
        report.issues.append(f"{int(dates.isna().sum())} unparsable dates")
    valid = dates.dropna()
    if valid.empty:
        return report

    report.start, report.end = valid.min().date(), valid.max().date()

    if not valid.is_monotonic_increasing:
        report.issues.append("dates are not strictly increasing")
    duplicates = int(valid.duplicated().sum())
    if duplicates:
        report.issues.append(f"{duplicates} duplicated dates")

    if len(valid) > 1:
        gaps = valid.diff().dt.days.dropna()
        longest = int(gaps.max())
        if longest > MAX_GAP_DAYS:
            report.issues.append(f"gap of {longest} days")

    for column in ("open", "high", "low", "close"):
        if column in frame.columns:
            if frame[column].isna().any():
                report.issues.append(f"null values in {column}")
            if (frame[column] <= 0).any():
                report.issues.append(f"non-positive values in {column}")

    if {"high", "low"}.issubset(frame.columns):
        broken = int((frame["high"] < frame["low"]).sum())
        if broken:
            report.issues.append(f"{broken} rows with high < low")

    if "volume" in frame.columns and (frame["volume"] <= 0).any():
        report.issues.append(f"{int((frame['volume'] <= 0).sum())} rows with zero volume")

    weekend = valid[valid.dt.dayofweek >= 5]
    if len(weekend) and not _is_crypto(code):
        report.issues.append(f"{len(weekend)} weekend rows (only crypto should have these)")

    return report


def scan(directory: str | Path, pattern: str = "*_kronos.csv") -> list[Report]:
    directory = Path(directory).expanduser()
    reports = []
    for path in sorted(directory.glob(pattern)):
        code = path.name[: -len("_kronos.csv")]
        try:
            reports.append(validate_frame(load_frame(path), code=code))
        except (OSError, pd.errors.ParserError) as exc:
            reports.append(Report(code=code, issues=[f"unreadable: {exc}"]))
    return reports


def format_table(reports: list[Report]) -> str:
    if not reports:
        return "no files found"
    width = max(len(r.code) for r in reports)
    lines = [f"{'code'.ljust(width)}  rows  span                    status"]
    for report in reports:
        span = f"{report.start} ~ {report.end}" if report.start else "-"
        status = "ok" if report.ok else "; ".join(report.issues)
        lines.append(f"{report.code.ljust(width)}  {report.rows:>4}  {span:<23} {status}")
    bad = sum(1 for r in reports if not r.ok)
    lines.append(f"\n{len(reports) - bad} ok, {bad} with issues")
    return "\n".join(lines)

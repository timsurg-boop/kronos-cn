"""Data health report: staleness, length, duplicates and broken files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

REQUIRED = ("date", "open", "high", "low", "close", "volume")


@dataclass
class SymbolReport:
    code: str
    path: Path
    rows: int = 0
    last: date | None = None
    stale_days: int | None = None
    broken: bool = False
    short: bool = False
    stale: bool = False
    issues: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.broken:
            return "broken"
        if self.short:
            return "short"
        if self.stale:
            return "stale"
        return "ok"


def inspect_file(path: Path, today: date, min_rows: int, max_stale_days: int) -> SymbolReport:
    report = SymbolReport(code=path.name.replace("_kronos.csv", ""), path=path)
    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 - report, never raise
        report.broken = True
        report.issues.append(f"unreadable: {type(exc).__name__}")
        return report

    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        report.broken = True
        report.issues.append(f"missing columns: {', '.join(missing)}")
        return report

    report.rows = len(frame)
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if dates.empty:
        report.broken = True
        report.issues.append("unreadable: no valid dates")
        return report
    duplicates = int(dates.duplicated().sum())
    if duplicates:
        report.broken = True
        report.issues.append(f"duplicated dates: {duplicates}")

    last = dates.max().date()
    report.last = last
    report.stale_days = (today - last).days
    if report.stale_days > max_stale_days:
        report.stale = True
        report.issues.append(f"stale: {report.stale_days} days")
    if report.rows < min_rows:
        report.short = True
        report.issues.append(f"short: {report.rows} rows")
    return report


def scan(
    data_dir: str | Path,
    today: date | None = None,
    min_rows: int = 25,
    max_stale_days: int = 10,
) -> list[SymbolReport]:
    today = today or date.today()
    root = Path(os.path.expandvars(str(data_dir))).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"data directory not found: {root}")
    return [
        inspect_file(path, today, min_rows, max_stale_days)
        for path in sorted(root.glob("*_kronos.csv"))
    ]


def summarize(reports: list[SymbolReport]) -> dict[str, int]:
    counts = {"ok": 0, "stale": 0, "short": 0, "broken": 0}
    for report in reports:
        counts[report.status] += 1
    return counts


def format_table(reports: list[SymbolReport], limit: int = 15) -> str:
    counts = summarize(reports)
    lines = [
        f"{len(reports)} symbols · "
        f"{counts['ok']} ok · {counts['stale']} stale · "
        f"{counts['short']} short · {counts['broken']} broken"
    ]
    problems = [report for report in reports if report.status != "ok"]
    problems.sort(key=lambda report: report.stale_days or -1, reverse=True)
    if problems:
        lines.append("")
        lines.append(f"{'code':<10}{'rows':>7}  {'last':<12}{'stale':>6}  issue")
        for report in problems[:limit]:
            last = report.last.isoformat() if report.last else "-"
            stale = f"{report.stale_days}d" if report.stale_days is not None else "-"
            lines.append(
                f"{report.code:<10}{report.rows:>7}  {last:<12}{stale:>6}  {'; '.join(report.issues)}"
            )
        if len(problems) > limit:
            lines.append(f"... {len(problems) - limit} more")
    return "\n".join(lines)


def to_json(reports: list[SymbolReport]) -> str:
    payload = {
        "summary": summarize(reports),
        "symbols": [
            {
                "code": report.code,
                "rows": report.rows,
                "last": report.last.isoformat() if report.last else None,
                "stale_days": report.stale_days,
                "status": report.status,
                "issues": report.issues,
            }
            for report in reports
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def run_doctor(
    data_dir: str | Path,
    min_rows: int = 25,
    max_stale_days: int = 10,
    as_json: bool = False,
    today: date | None = None,
) -> tuple[int, str]:
    reports = scan(data_dir, today=today, min_rows=min_rows, max_stale_days=max_stale_days)
    text = to_json(reports) if as_json else format_table(reports)
    counts = summarize(reports)
    return (1 if counts["broken"] or counts["short"] else 0), text

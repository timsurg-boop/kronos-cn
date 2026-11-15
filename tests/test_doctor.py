import json
from datetime import date, timedelta

import pandas as pd

from kronos_cn.doctor import format_table, run_doctor, scan


def _write(path, days: int, end: date, rows: int | None = None):
    dates = pd.bdate_range(end=end, periods=rows or days)
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [1.0] * len(dates),
            "high": [2.0] * len(dates),
            "low": [0.5] * len(dates),
            "close": [1.5] * len(dates),
            "volume": [100.0] * len(dates),
        }
    )
    frame.to_csv(path, index=False)


def test_statuses(tmp_path):
    today = date(2026, 11, 15)
    _write(tmp_path / "600519_kronos.csv", 60, today)
    _write(tmp_path / "000001_kronos.csv", 60, today - timedelta(days=40))
    _write(tmp_path / "000002_kronos.csv", 10, today, rows=10)
    (tmp_path / "000003_kronos.csv").write_text("foo,bar\n1,2\n")

    reports = {report.code: report for report in scan(tmp_path, today=today, max_stale_days=10)}
    assert reports["600519"].status == "ok"
    assert reports["000001"].status == "stale"
    assert reports["000002"].status == "short"
    assert reports["000003"].status == "broken"


def test_exit_code_and_json(tmp_path):
    today = date(2026, 11, 15)
    _write(tmp_path / "600519_kronos.csv", 60, today - timedelta(days=40))
    code, text = run_doctor(tmp_path, today=today, max_stale_days=10)
    assert code == 0
    assert "stale" in text

    code, text = run_doctor(tmp_path, today=today, max_stale_days=10, as_json=True)
    payload = json.loads(text)
    assert payload["summary"]["stale"] == 1
    assert payload["symbols"][0]["code"] == "600519"


def test_broken_returns_one(tmp_path):
    (tmp_path / "bad_kronos.csv").write_text("date,close\n2024-01-02,1\n")
    code, _ = run_doctor(tmp_path, today=date(2026, 11, 15))
    assert code == 1


def test_table_limits_rows(tmp_path):
    today = date(2026, 11, 15)
    for index in range(20):
        _write(tmp_path / f"{index:06d}_kronos.csv", 60, today - timedelta(days=40 + index))
    reports = scan(tmp_path, today=today)
    text = format_table(reports, limit=5)
    assert "more" in text

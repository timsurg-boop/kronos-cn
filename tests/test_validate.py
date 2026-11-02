import pandas as pd

from kronos_cn.data.validate import format_table, validate_frame


def _frame(days=30):
    dates = pd.date_range("2024-01-01", periods=days, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [1.0] * days,
            "high": [2.0] * days,
            "low": [0.5] * days,
            "close": [1.5] * days,
            "volume": [100.0] * days,
            "amount": [150.0] * days,
        }
    )


def test_clean_frame_passes():
    report = validate_frame(_frame(), "600519")
    assert report.ok, report.issues
    assert report.rows == 30
    assert str(report.end) == "2024-02-09"


def test_duplicate_dates_flagged():
    frame = _frame()
    frame.loc[5, "date"] = frame.loc[4, "date"]
    report = validate_frame(frame, "X")
    assert any("duplicated" in issue for issue in report.issues)


def test_missing_date_flagged():
    frame = _frame().drop(columns=["date"])
    report = validate_frame(frame, "X")
    assert any("date" in issue for issue in report.issues)


def test_bad_ohlc_flagged():
    frame = _frame()
    frame.loc[3, "high"] = 0.1
    report = validate_frame(frame, "X")
    assert any("high < low" in issue for issue in report.issues)


def test_empty_frame():
    report = validate_frame(pd.DataFrame(), "X")
    assert not report.ok


def test_table_rendering():
    text = format_table([validate_frame(_frame(), "600519")])
    assert "600519" in text
    assert "1 ok, 0 with issues" in text

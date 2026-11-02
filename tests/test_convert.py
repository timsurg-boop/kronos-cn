import pandas as pd
import pytest

from kronos_cn.data.convert import normalize, to_period


def test_normalize_renames_and_sorts():
    raw = pd.DataFrame(
        {
            "trade_date": ["20240103", "20240102"],
            "open": [2, 1],
            "high": [3, 2],
            "low": [1, 0.5],
            "close": [2.5, 1.5],
            "vol": [200, 100],
            "amount": [20.0, 10.0],
        }
    )
    out = normalize(raw)
    assert list(out.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
    assert out["date"].is_monotonic_increasing
    assert out["volume"].tolist() == [100, 200]


def test_normalize_drops_duplicate_dates():
    raw = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02"],
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [1, 2],
            "amount": [1, 2],
        }
    )
    out = normalize(raw)
    assert len(out) == 1
    assert out["close"].iloc[0] == 2


def test_normalize_requires_columns():
    with pytest.raises(ValueError, match="missing columns"):
        normalize(pd.DataFrame({"date": ["2024-01-02"], "close": [1]}))


def test_weekly_aggregation():
    dates = pd.date_range("2024-01-01", periods=7, freq="B")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": range(1, 8),
            "high": range(2, 9),
            "low": range(0, 7),
            "close": range(1, 8),
            "volume": [10] * 7,
            "amount": [100] * 7,
        }
    )
    weekly = to_period(frame, "W")
    assert len(weekly) == 2
    first = weekly.iloc[0]
    assert first["open"] == 1
    assert first["close"] == 5
    assert first["high"] == 6
    assert first["low"] == 0
    assert first["volume"] == 50

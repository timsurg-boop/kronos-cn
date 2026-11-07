import pandas as pd

from kronos_cn.kline import plot_kline_grid


def _frame(days: int = 400) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=days)
    close = [100 + i * 0.1 for i in range(days)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": [c - 0.2 for c in close],
            "high": [c + 0.8 for c in close],
            "low": [c - 0.8 for c in close],
            "close": close,
            "volume": [1000 + i for i in range(days)],
            "amount": [10000.0] * days,
        }
    )


def test_plot_kline_grid(tmp_path):
    out = tmp_path / "kline.png"
    saved = plot_kline_grid(_frame(), "600519", out, periods=("D", "W", "M"))
    assert saved == out
    assert out.exists()
    assert out.stat().st_size > 20_000


def test_plot_single_period(tmp_path):
    out = tmp_path / "weekly.png"
    plot_kline_grid(_frame(), "000001", out, periods=("W",), bars={"W": 40})
    assert out.exists()

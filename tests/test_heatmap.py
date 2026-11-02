from datetime import date

import pandas as pd

from kronos_cn.heatmap.market import compute_snapshot, load_snapshots, render_html, sina_url


def _frame(days=120, start="2024-01-01", step=1.0):
    dates = pd.bdate_range(start, periods=days)
    close = [100 + i * step for i in range(days)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": [c + 1 for c in close],
            "low": [c - 1 for c in close],
            "close": close,
            "volume": [1000.0] * days,
            "amount": [100000.0] * days,
        }
    )


def test_snapshot_math():
    snapshot = compute_snapshot("600519", _frame())
    assert snapshot is not None
    assert snapshot.name == "贵州茅台"
    assert snapshot.close == 219
    assert snapshot.as_of == date(2024, 6, 14)
    # 5 trading days ~ 7 calendar days; weekly last vs previous week
    assert -2 < snapshot.wk < 6
    assert snapshot.mo != 0
    assert snapshot.wk_vol > 0


def test_snapshot_rejects_short_or_dateless():
    assert compute_snapshot("X", _frame(days=10)) is None
    assert compute_snapshot("X", _frame().drop(columns=["date"])) is None


def test_render_contains_symbols_and_summary():
    snapshots = [compute_snapshot(c, _frame()) for c in ("600519", "000001")]
    html = render_html([s for s in snapshots if s], title="测试云图")
    assert "测试云图" in html
    assert "600519" in html and "000001" in html
    assert "上涨" in html
    assert html.count('class="grid"') == 4


def test_render_escapes_untrusted_name():
    snapshots = [compute_snapshot("600519", _frame())]
    snapshots[0] = snapshots[0].__class__(**{**snapshots[0].__dict__, "name": "<script>x</script>"})
    html = render_html(snapshots)
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_sina_url_rules():
    assert sina_url("600519").endswith("/sh600519/nc.shtml")
    assert sina_url("000001").endswith("/sz000001/nc.shtml")
    assert sina_url("830799").endswith("/bj830799/nc.shtml")
    assert "NVDA" in sina_url("NVDAUSA")
    assert sina_url("BTCUSA") is None
    assert sina_url("ABC") is None


def test_load_snapshots_skips_bad_files(tmp_path):
    _frame().to_csv(tmp_path / "600519_kronos.csv", index=False)
    (tmp_path / "000001_kronos.csv").write_text("open,high,low,close,volume,amount\n1,1,1,1,1,1\n")
    snapshots, skipped = load_snapshots(tmp_path)
    assert [s.code for s in snapshots] == ["600519"]
    assert skipped[0][0] == "000001"

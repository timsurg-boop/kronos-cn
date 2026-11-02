import pandas as pd

from kronos_cn.heatmap.dividend import compute_score, prepare, tier, write_dividend_heatmap


def _row(**overrides):
    base = {
        "code": "601166",
        "price": 18.0,
        "dps_fy": 1.0,
        "yield_fy_pct": 5.5,
        "yield_hist_mean_pct": 4.0,
        "yield_cv": 0.3,
        "div_years": 4,
        "vol_pct": 20.0,
        "mdd_pct": -30.0,
        "win_pct": 55.0,
        "above_ma10m": True,
        "score": 0.8,
    }
    base.update(overrides)
    return pd.Series(base)


def test_tier_rules():
    assert tier(_row()) == "core"
    assert tier(_row(above_ma10m=False)) == "watch"
    assert tier(_row(div_years=1)) == "weak"
    assert tier(_row(yield_fy_pct=1.0)) == "weak"


def test_score_prefers_higher_yield_and_lower_risk():
    strong = compute_score(_row(yield_fy_pct=7.0, vol_pct=10, mdd_pct=-10, win_pct=80, yield_cv=0.1))
    weak = compute_score(_row(yield_fy_pct=1.0, vol_pct=55, mdd_pct=-55, win_pct=35, yield_cv=0.9))
    assert 0 <= weak < strong <= 1


def test_render_and_prepare(tmp_path):
    source = tmp_path / "div.csv"
    pd.DataFrame([_row().to_dict(), _row(code="000568", score=0.2, above_ma10m=False).to_dict()]).to_csv(
        source, index=False
    )
    frame = prepare(source)
    assert frame["tier"].tolist() == ["core", "watch"]

    out = write_dividend_heatmap(source, tmp_path / "div.html")
    html = out.read_text(encoding="utf-8")
    assert "兴业银行" in html
    assert "核心 1 只" in html

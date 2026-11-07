from pathlib import Path

from kronos_cn.cli import main

REPO = Path(__file__).resolve().parents[1]
SAMPLES = REPO / "examples" / "data"


def test_validate_samples(capsys):
    code = main(["validate", "--data-dir", str(SAMPLES)])
    output = capsys.readouterr().out
    assert code in (0, 1)
    assert "ok" in output


def test_demo_writes_html(tmp_path, capsys):
    out = tmp_path / "heatmap.html"
    code = main(["demo", "--data-dir", str(SAMPLES), "--out", str(out)])
    assert code == 0
    assert out.exists()
    assert "Kronos 市场云图" in out.read_text(encoding="utf-8")
    assert "标的" in capsys.readouterr().out


def test_heatmap_explicit(tmp_path):
    out = tmp_path / "custom.html"
    assert main(["heatmap", "--data-dir", str(SAMPLES), "--out", str(out), "--metric", "mo"]) == 0
    html = out.read_text(encoding="utf-8")
    assert 'id="grid-mo"' in html
    assert "selected" in html


def test_chart_writes_png(tmp_path):
    out = tmp_path / "600519.png"
    code = main(
        [
            "chart",
            "600519",
            "--period",
            "D",
            "W",
            "M",
            "--data-dir",
            str(SAMPLES),
            "--out",
            str(out),
            "--no-open",
        ]
    )
    assert code == 0
    assert out.exists()
    assert out.stat().st_size > 20_000

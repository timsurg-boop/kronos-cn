import numpy as np
import pandas as pd
import pytest

from kronos_cn.evaluation.metrics import (
    forward_return,
    max_drawdown,
    net_value,
    spearman,
    summarize_ic,
    top_mean,
)


def test_spearman_perfect_and_inverse():
    a = [1, 2, 3, 4, 5]
    assert spearman(a, a) == pytest.approx(1.0)
    assert spearman(a, list(reversed(a))) == pytest.approx(-1.0)


def test_spearman_needs_three_pairs():
    assert np.isnan(spearman([1, 2], [1, 2]))


def test_forward_return():
    close = pd.Series([10.0, 11.0, 12.0])
    assert forward_return(close, 0, 2) == pytest.approx(20.0)
    with pytest.raises(IndexError):
        forward_return(close, 1, 5)


def test_top_mean():
    frame = pd.DataFrame({"pred": [3, 2, 1], "actual": [1.0, 2.0, 3.0]})
    assert top_mean(frame, "pred", 1) == pytest.approx(1.0)
    assert top_mean(frame, "pred", 1, ascending=True) == pytest.approx(3.0)
    assert np.isnan(top_mean(frame, "pred", 10))


def test_net_value_and_drawdown():
    nav = net_value(pd.Series([10.0, -10.0, 10.0]))
    assert nav.iloc[-1] == pytest.approx(1.089)
    assert max_drawdown(nav) == pytest.approx(-10.0)


def test_summarize_ic():
    summary = summarize_ic(pd.Series([0.1, -0.1, 0.2, 0.0]))
    assert summary["mean"] == pytest.approx(0.05)
    assert summary["hit"] == pytest.approx(50.0)

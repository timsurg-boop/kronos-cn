"""Rolling RankIC evaluation for Kronos forecasts.

The harness never trains and never touches the network. It walks a shared
trading calendar, predicts ``pred_len`` bars ahead for every symbol, and scores
the cross-section against realised forward returns.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from kronos_cn.config import Settings
from kronos_cn.data.validate import load_frame
from kronos_cn.evaluation.metrics import (
    forward_return,
    max_drawdown,
    net_value,
    spearman,
    summarize_ic,
    top_mean,
)

REQUIRED = ("open", "high", "low", "close", "volume", "amount")


@dataclass
class EvalConfig:
    pred_len: int = 20
    step: int = 20
    top_n: int = 5
    max_symbols: int = 50
    samples: int = 3
    start: str = "2025-01-02"
    temperature: float = 0.15
    top_p: float = 0.2
    lookback: int = 512
    gate: bool = True
    min_rows: int = 700


@dataclass
class EvalResult:
    per_date: pd.DataFrame
    symbols: int
    rebalances: int
    elapsed: float
    summary: dict = field(default_factory=dict)
    csv: Path | None = None
    png: Path | None = None


def gate_ok(frame: pd.DataFrame, window_weeks: int = 10, slope: int = 4) -> bool:
    """Weekly and monthly trend filter (both above rising MAs)."""
    if len(frame) < 300:
        return False
    series = frame.set_index("date")["close"].astype(float)
    weekly = series.resample("W-FRI").last().dropna()
    monthly = series.resample("ME").last().dropna()
    if len(weekly) < window_weeks + slope or len(monthly) < window_weeks + 3:
        return False
    weekly_ma = weekly.rolling(window_weeks).mean()
    monthly_ma = monthly.rolling(window_weeks).mean()
    return bool(
        weekly.iloc[-1] > weekly_ma.iloc[-1]
        and weekly_ma.iloc[-1] > weekly_ma.iloc[-1 - slope]
        and monthly.iloc[-1] > monthly_ma.iloc[-1]
        and monthly_ma.iloc[-1] > monthly_ma.iloc[-1 - 3]
    )


def build_universe(data_dir: str | Path, config: EvalConfig) -> dict[str, pd.DataFrame]:
    directory = Path(data_dir).expanduser()
    frames: dict[str, pd.DataFrame] = {}
    for path in sorted(directory.glob("*_kronos.csv")):
        code = path.name[: -len("_kronos.csv")]
        if not code.isdigit():  # A-shares only
            continue
        try:
            frame = load_frame(path)
        except (OSError, pd.errors.ParserError):
            continue
        if "date" not in frame.columns or len(frame) < config.min_rows:
            continue
        frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
        frames[code] = frame.reset_index(drop=True)
    # Prefer the longest histories; ties broken by code for determinism.
    codes = sorted(frames, key=lambda c: (-len(frames[c]), c))[: config.max_symbols]
    return {c: frames[c] for c in codes}


def _rebalance_dates(frames: dict[str, pd.DataFrame], config: EvalConfig) -> list[pd.Timestamp]:
    calendar = sorted(set().union(*[set(f["date"]) for f in frames.values()]))
    calendar = [d for d in calendar if d >= pd.Timestamp(config.start)]
    return calendar[:: config.step]


def run_evaluation(
    config: EvalConfig,
    settings: Settings | None = None,
    model_name: str = "Kronos-mini",
    tokenizer_name: str = "Kronos-Tokenizer-2k",
    model_dir: str | Path | None = None,
    device: str = "cpu",
    progress=print,
) -> EvalResult:
    """Walk the calendar and score Kronos against forward returns."""
    from kronos_cn.predict import load_predictor

    settings = settings or Settings.load()
    frames = build_universe(settings.data_dir, config)
    if len(frames) < config.top_n:
        raise ValueError(f"need at least {config.top_n} symbols, found {len(frames)}")

    dates = _rebalance_dates(frames, config)
    if not dates:
        raise ValueError("no rebalance dates after `start`")

    progress(
        f"A 股标的 {len(frames)} 只；调仓 {len(dates)} 次（{dates[0].date()} ~ {dates[-1].date()}）；"
        f"预测 {config.pred_len} 日；samples={config.samples}"
    )
    predictor = load_predictor(
        model_name=model_name,
        tokenizer_name=tokenizer_name,
        model_dir=model_dir or settings.model_dir,
        device=device,
        lookback=config.lookback,
    )

    rows: list[dict] = []
    started = time.time()
    for index, day in enumerate(dates, 1):
        batch, meta = [], []
        for code, frame in frames.items():
            positions = frame.index[frame["date"] <= day]
            if len(positions) < config.lookback + 1:
                continue
            i = int(positions[-1])
            if i + config.pred_len >= len(frame):
                continue
            history = frame.iloc[i - config.lookback + 1 : i + 1].reset_index(drop=True)
            batch.append(history[list(REQUIRED)])
            meta.append(
                {
                    "code": code,
                    "current": float(frame["close"].iloc[i]),
                    "actual": forward_return(frame["close"], i, config.pred_len),
                    "gate": gate_ok(frame.iloc[: i + 1]) if config.gate else True,
                }
            )
        if len(batch) < config.top_n:
            progress(f"[{index}/{len(dates)}] {day.date()} 样本不足({len(batch)})，跳过")
            continue

        xs = [list(range(len(b))) for b in batch]
        ys = [list(range(len(b), len(b) + config.pred_len)) for b in batch]
        outputs = predictor.predict_batch(
            batch,
            xs,
            ys,
            pred_len=config.pred_len,
            T=config.temperature,
            top_p=config.top_p,
            sample_count=config.samples,
            verbose=False,
        )

        records = []
        for item, output in zip(meta, outputs, strict=True):
            predicted = (float(output["close"].values[-1]) / item["current"] - 1.0) * 100.0
            records.append({**item, "pred": predicted})
        day_frame = pd.DataFrame(records)
        gated = day_frame[day_frame["gate"]]

        ic_all = spearman(day_frame["pred"], day_frame["actual"])
        ic_gate = spearman(gated["pred"], gated["actual"]) if len(gated) >= config.top_n else float("nan")
        rows.append(
            {
                "date": day.date(),
                "n": len(day_frame),
                "ic_all": round(ic_all, 4) if ic_all == ic_all else float("nan"),
                "n_gate": len(gated),
                "ic_gate": round(ic_gate, 4) if ic_gate == ic_gate else float("nan"),
                "uni_mean": round(float(day_frame["actual"].mean()), 3),
                "top": top_mean(day_frame, "pred", config.top_n),
                "bottom": top_mean(day_frame, "pred", config.top_n, ascending=True),
                "gate_top": top_mean(gated, "pred", config.top_n),
                "gate_bottom": top_mean(gated, "pred", config.top_n, ascending=True),
            }
        )
        row = rows[-1]
        progress(
            f"[{index}/{len(dates)}] {day.date()} n={row['n']}(gate {row['n_gate']}) "
            f"IC {row['ic_all']:+.2f}/gate {row['ic_gate']:+.2f} | "
            f"Top{config.top_n} {row['top']:+.1f}% 池均 {row['uni_mean']:+.1f}%"
        )

    if not rows:
        raise ValueError("every rebalance date was skipped — check history length and start date")

    per_date = pd.DataFrame(rows)
    return EvalResult(
        per_date=per_date,
        symbols=len(frames),
        rebalances=len(per_date),
        elapsed=time.time() - started,
        summary=summarize(per_date, config.top_n),
    )


def summarize(per_date: pd.DataFrame, top_n: int = 5) -> dict:
    ic = summarize_ic(per_date["ic_all"])
    gated = summarize_ic(per_date["ic_gate"])
    top = float(per_date["top"].mean())
    bottom = float(per_date["bottom"].mean())
    return {
        "rebalances": len(per_date),
        "avg_symbols": float(per_date["n"].mean()),
        "ic_mean": ic["mean"],
        "ic_std": ic["std"],
        "ic_ir": ic["ir"],
        "ic_hit": ic["hit"],
        "gate_ic_mean": gated["mean"],
        "gate_ic_periods": int(per_date["ic_gate"].notna().sum()),
        f"top{top_n}": top,
        f"bottom{top_n}": bottom,
        "long_short": top - bottom,
        "universe_mean": float(per_date["uni_mean"].mean()),
        "top_nav": float(net_value(per_date["top"]).iloc[-1]),
        "top_mdd": max_drawdown(net_value(per_date["top"])),
        "bottom_nav": float(net_value(per_date["bottom"]).iloc[-1]),
        "universe_nav": float(net_value(per_date["uni_mean"]).iloc[-1]),
    }


def format_summary(summary: dict) -> str:
    return "\n".join(
        [
            f"调仓次数 {summary['rebalances']}，平均每期 {summary['avg_symbols']:.0f} 只",
            f"RankIC 均值 {summary['ic_mean']:+.3f}，标准差 {summary['ic_std']:.3f}，"
            f"IR {summary['ic_ir']:+.2f}，IC>0 占比 {summary['ic_hit']:.0f}%",
            f"闸门内 RankIC 均值 {summary['gate_ic_mean']:+.3f}（{summary['gate_ic_periods']} 期）",
            f"Top5 平均 {summary['top5']:+.2f}%   Bottom5 平均 {summary['bottom5']:+.2f}%   "
            f"多空差 {summary['long_short']:+.2f}%",
            f"池均 {summary['universe_mean']:+.2f}%；Top5 净值 {summary['top_nav']:.3f}"
            f"（最大回撤 {summary['top_mdd']:.1f}%）",
        ]
    )


def plot_result(per_date: pd.DataFrame, out: str | Path, top_n: int = 5, title: str = "") -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    figure, (top_ax, ic_ax) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]})
    top_ax.plot(per_date["date"], net_value(per_date["top"]), "o-", label=f"Top{top_n}", lw=1.4)
    top_ax.plot(per_date["date"], net_value(per_date["bottom"]), "s--", label=f"Bottom{top_n}", lw=1.2)
    top_ax.plot(per_date["date"], net_value(per_date["uni_mean"]), "^:", label="Universe", lw=1.2)
    top_ax.set_title(title or "Kronos RankIC evaluation")
    top_ax.set_ylabel("Net value (no fees)")
    top_ax.legend()
    top_ax.grid(alpha=0.3)

    ic_ax.bar(per_date["date"], per_date["ic_all"], color="#4a7ebb", alpha=0.85, label="RankIC")
    ic_ax.axhline(0, color="gray", lw=1)
    mean_ic = per_date["ic_all"].mean()
    ic_ax.axhline(mean_ic, color="#c0392b", ls="--", lw=1, label=f"mean {mean_ic:+.3f}")
    ic_ax.set_ylabel("RankIC")
    ic_ax.legend()
    ic_ax.grid(alpha=0.3)
    for axis in (top_ax, ic_ax):
        plt.setp(axis.get_xticklabels(), rotation=30)
    figure.tight_layout()
    figure.savefig(out, dpi=150)
    plt.close(figure)
    return out

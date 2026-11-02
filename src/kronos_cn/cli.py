"""Command line interface — ``kronos-cn --help``."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from kronos_cn import __version__
from kronos_cn.config import Settings, normalize_code
from kronos_cn.data.convert import normalize as normalize_frame
from kronos_cn.data.validate import format_table, scan
from kronos_cn.heatmap.market import METRICS, write_heatmap


def _add_data_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", help="directory with *_kronos.csv (default: $KRONOS_DATA_DIR)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kronos-cn",
        description="Kronos Workbench: K-line data, market heatmaps and forecast evaluation.",
    )
    parser.add_argument("--version", action="version", version=f"kronos-cn {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="check data quality")
    _add_data_dir(p_validate)

    p_heatmap = sub.add_parser("heatmap", help="render the market heatmap")
    _add_data_dir(p_heatmap)
    p_heatmap.add_argument("--out", help="output HTML path (default: $KRONOS_OUTPUT_DIR/heatmap.html)")
    p_heatmap.add_argument("--title", default="Kronos 市场云图")
    p_heatmap.add_argument("--metric", default="wk", choices=METRICS, help="initial period")
    p_heatmap.add_argument("--scheme", default="cn", choices=["cn", "intl"], help="red-up (cn) or green-up (intl)")
    p_heatmap.add_argument("--open", action="store_true", help="open in the browser")
    p_heatmap.add_argument("--note", default="", help="footer note")

    p_dividend = sub.add_parser("dividend", help="render the dividend heatmap from a CSV table")
    p_dividend.add_argument("--csv", required=True)
    p_dividend.add_argument("--out", default="dividend_heatmap.html")
    p_dividend.add_argument("--title", default="A50 稳定红利热力图")
    p_dividend.add_argument("--open", action="store_true")

    p_fetch = sub.add_parser("fetch", help="download one symbol")
    p_fetch.add_argument("code")
    p_fetch.add_argument("--start", default="2018-01-01")
    p_fetch.add_argument("--end")
    p_fetch.add_argument("--freq", default="D", choices=["D", "W"])
    p_fetch.add_argument("--out", help="output directory (default: $KRONOS_DATA_DIR)")

    p_predict = sub.add_parser("predict", help="forecast one symbol (needs a Kronos checkpoint)")
    p_predict.add_argument("code")
    p_predict.add_argument("--data-dir")
    p_predict.add_argument("--out-dir")
    p_predict.add_argument("--pred-len", type=int, default=30)
    p_predict.add_argument("--lookback", type=int, default=512)
    p_predict.add_argument("--samples", type=int, default=10)
    p_predict.add_argument("--temperature", type=float, default=0.1)
    p_predict.add_argument("--top-p", type=float, default=0.2)
    p_predict.add_argument("--model", default="Kronos-mini")
    p_predict.add_argument("--model-dir")
    p_predict.add_argument("--device", default="cpu")
    p_predict.add_argument("--plot", action="store_true")
    p_predict.add_argument("--open", action="store_true")

    p_eval = sub.add_parser("eval", help="rolling RankIC evaluation")
    _add_data_dir(p_eval)
    p_eval.add_argument("--pred", dest="pred_len", type=int, default=20)
    p_eval.add_argument("--step", type=int, default=20)
    p_eval.add_argument("--top", dest="top_n", type=int, default=5)
    p_eval.add_argument("--symbols", type=int, default=50)
    p_eval.add_argument("--samples", type=int, default=3)
    p_eval.add_argument("--start", default="2025-01-02")
    p_eval.add_argument("--no-gate", action="store_true")
    p_eval.add_argument("--model", default="Kronos-mini")
    p_eval.add_argument("--model-dir")
    p_eval.add_argument("--out-dir")

    p_demo = sub.add_parser("demo", help="render a heatmap from the bundled sample data")
    p_demo.add_argument("--data-dir", help="default: ./examples/data")
    p_demo.add_argument("--out", default="heatmap.html")
    p_demo.add_argument("--scheme", default="cn", choices=["cn", "intl"])
    p_demo.add_argument("--open", action="store_true")

    p_names = sub.add_parser("names", help="refresh the bundled symbol-name table")
    p_names.add_argument("--refresh", action="store_true")
    p_names.add_argument("--out")

    return parser


def _resolve_demo_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    candidates = [Path.cwd() / "examples" / "data", Path(__file__).resolve().parents[3] / "examples" / "data"]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise SystemExit("examples/data not found; run from the repository root or pass --data-dir")


def cmd_validate(args: argparse.Namespace) -> int:
    settings = Settings.load().with_data_dir(args.data_dir)
    reports = scan(settings.data_dir)
    print(format_table(reports))
    return 0 if reports and all(r.ok for r in reports) else 1


def cmd_heatmap(args: argparse.Namespace) -> int:
    settings = Settings.load().with_data_dir(args.data_dir).ensure_dirs()
    out = Path(args.out).expanduser() if args.out else settings.output_dir / "heatmap.html"
    path, snapshots, skipped = write_heatmap(
        settings.data_dir, out, title=args.title, initial=args.metric, note=args.note, scheme=args.scheme
    )
    print(f"✅ {path}\n   标的 {len(snapshots)} 个，跳过 {len(skipped)} 个")
    for code, reason in skipped[:10]:
        print(f"   - {code}: {reason}")
    if args.open:
        webbrowser.open(path.resolve().as_uri())
    return 0


def cmd_dividend(args: argparse.Namespace) -> int:
    from kronos_cn.heatmap.dividend import write_dividend_heatmap

    path = write_dividend_heatmap(args.csv, args.out, title=args.title)
    print(f"✅ {path}")
    if args.open:
        webbrowser.open(Path(path).resolve().as_uri())
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from kronos_cn.data.fetch import FetchError, fetch

    settings = Settings.load().ensure_dirs()
    target_dir = Path(args.out).expanduser() if args.out else settings.data_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    code = normalize_code(args.code)
    try:
        result = fetch(code, start=args.start, end=args.end, freq=args.freq, settings=settings)
    except FetchError as exc:
        print(f"❌ {exc}")
        return 1
    frame = normalize_frame(result.frame)
    target = target_dir / f"{code}_kronos.csv"
    frame.to_csv(target, index=False)
    first, last = frame["date"].iloc[0].date(), frame["date"].iloc[-1].date()
    print(f"✅ {code}: {len(frame)} 行 ({first} ~ {last}) via {result.source}\n   {target}")
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    from kronos_cn.data.validate import load_frame
    from kronos_cn.plot import plot_forecast
    from kronos_cn.predict import load_predictor, predict_frame

    settings = Settings.load().with_data_dir(args.data_dir).with_output_dir(args.out_dir).ensure_dirs()
    code = normalize_code(args.code)
    path = settings.data_csv(code)
    if not path.exists():
        print(f"❌ no data for {code} at {path}")
        return 1

    predictor = load_predictor(
        model_name=args.model,
        model_dir=args.model_dir or settings.model_dir,
        device=args.device,
        lookback=args.lookback,
    )
    history = load_frame(path)
    forecast = predict_frame(
        history,
        predictor,
        pred_len=args.pred_len,
        lookback=args.lookback,
        temperature=args.temperature,
        top_p=args.top_p,
        sample_count=args.samples,
    )
    out_csv = settings.pred_csv(code)
    forecast.to_csv(out_csv, index=False)
    print(f"✅ {out_csv}")

    if args.plot:
        title = f"{code} · {args.model} · T={args.temperature}"
        png = plot_forecast(history, forecast, settings.chart_png(code, "forecast"), title=title)
        print(f"✅ {png}")
        if args.open:
            webbrowser.open(png.resolve().as_uri())
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from kronos_cn.evaluation.runner import EvalConfig, format_summary, plot_result, run_evaluation

    settings = Settings.load().with_data_dir(args.data_dir).with_output_dir(args.out_dir).ensure_dirs()
    config = EvalConfig(
        pred_len=args.pred_len,
        step=args.step,
        top_n=args.top_n,
        max_symbols=args.symbols,
        samples=args.samples,
        start=args.start,
        gate=not args.no_gate,
    )
    try:
        result = run_evaluation(config, settings=settings, model_name=args.model, model_dir=args.model_dir)
    except (ImportError, ValueError, FileNotFoundError) as exc:
        print(f"❌ {exc}")
        return 1

    stamp = f"{config.pred_len}d_step{config.step}"
    csv_path = settings.output_dir / f"eval_{stamp}.csv"
    result.per_date.to_csv(csv_path, index=False)
    png_path = plot_result(
        result.per_date, settings.output_dir / f"eval_{stamp}.png", top_n=config.top_n
    )
    print("\n===== 汇总 =====")
    print(format_summary(result.summary))
    print(f"耗时 {result.elapsed:.0f}s\nCSV: {csv_path}\n图: {png_path}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    data_dir = _resolve_demo_dir(args.data_dir)
    out = Path(args.out).expanduser()
    path, snapshots, skipped = write_heatmap(
        data_dir, out, title="Kronos 市场云图 · 样例", note="样例数据，仅演示排版与配色。", scheme=args.scheme
    )
    print(f"✅ {path}\n   标的 {len(snapshots)} 个，跳过 {len(skipped)} 个")
    if args.open:
        webbrowser.open(path.resolve().as_uri())
    return 0


def cmd_names(args: argparse.Namespace) -> int:
    from kronos_cn.names import refresh_names

    if not args.refresh:
        print("nothing to do; pass --refresh to rebuild from Akshare")
        return 0
    try:
        path = refresh_names(args.out)
    except ImportError:
        print("❌ akshare is required: pip install 'kronos-cn[fetch]'")
        return 1
    print(f"✅ {path}")
    return 0


COMMANDS = {
    "validate": cmd_validate,
    "heatmap": cmd_heatmap,
    "dividend": cmd_dividend,
    "fetch": cmd_fetch,
    "predict": cmd_predict,
    "eval": cmd_eval,
    "demo": cmd_demo,
    "names": cmd_names,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS[args.command]
    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

"""Forecast with a Kronos checkpoint.

The upstream model code is *not* vendored here. Point ``KRONOS_UPSTREAM`` at a
clone of https://github.com/shiyu-coder/Kronos (or ``pip install -e`` it) and
download the weights from Hugging Face, or pass ``--model-dir`` to a local
folder containing ``Kronos-mini`` / ``Kronos-Tokenizer-2k``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

from kronos_cn.config import Settings
from kronos_cn.data.validate import load_frame

_PREDICTORS: dict[tuple, object] = {}


def _ensure_upstream_importable() -> None:
    upstream = os.environ.get("KRONOS_UPSTREAM", "").strip()
    if upstream:
        path = str(Path(upstream).expanduser())
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        import model  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on user install
        raise ImportError(
            "Kronos model code not found. Clone https://github.com/shiyu-coder/Kronos "
            "and set KRONOS_UPSTREAM=/path/to/Kronos, or `pip install -e` that repo."
        ) from exc


def _resolve(model_dir: Path, name: str) -> str:
    candidate = model_dir / name
    if candidate.exists():
        return str(candidate)
    if model_dir.exists() and any(model_dir.glob("*.safetensors")):
        return str(model_dir)
    return name  # Hugging Face repo id, e.g. NeoQuasar/Kronos-mini


def load_predictor(
    model_name: str = "Kronos-mini",
    tokenizer_name: str = "Kronos-Tokenizer-2k",
    model_dir: str | Path | None = None,
    device: str = "cpu",
    lookback: int = 512,
):
    """Load (and cache) a Kronos predictor."""
    key = (model_name, tokenizer_name, str(model_dir or ""), device, lookback)
    if key in _PREDICTORS:
        return _PREDICTORS[key]

    _ensure_upstream_importable()
    from model import Kronos, KronosPredictor, KronosTokenizer

    base = Path(model_dir).expanduser() if model_dir else Path("NeoQuasar")
    tokenizer = KronosTokenizer.from_pretrained(_resolve(base, tokenizer_name))
    model = Kronos.from_pretrained(_resolve(base, model_name))
    predictor = KronosPredictor(model, tokenizer, device=device, max_context=lookback)
    _PREDICTORS[key] = predictor
    return predictor


def predict_frame(
    frame: pd.DataFrame,
    predictor,
    pred_len: int = 30,
    lookback: int = 512,
    temperature: float = 0.1,
    top_p: float = 0.2,
    sample_count: int = 10,
    align: bool = True,
) -> pd.DataFrame:
    """Forecast the next ``pred_len`` bars from a canonical frame."""
    columns = ["open", "high", "low", "close", "volume", "amount"]
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError("missing columns: " + ", ".join(missing))
    history = frame[columns].tail(lookback).reset_index(drop=True)
    if len(history) < 30:
        raise ValueError("need at least 30 bars of history")

    x_timestamp = list(range(len(history)))
    y_timestamp = list(range(len(history), len(history) + pred_len))
    forecast = predictor.predict(
        df=history,
        x_timestamp=x_timestamp,
        y_timestamp=y_timestamp,
        pred_len=pred_len,
        T=temperature,
        top_p=top_p,
        sample_count=sample_count,
        verbose=False,
    )
    if align:
        offset = float(history["close"].iloc[-1]) - float(forecast["close"].iloc[0])
        for column in ("open", "high", "low", "close"):
            forecast[column] = forecast[column] + offset
    return forecast


def predict_symbol(
    code: str,
    settings: Settings | None = None,
    pred_len: int = 30,
    lookback: int = 512,
    temperature: float = 0.1,
    top_p: float = 0.2,
    sample_count: int = 10,
    model_name: str = "Kronos-mini",
    model_dir: str | Path | None = None,
    device: str = "cpu",
) -> pd.DataFrame:
    settings = (settings or Settings.load()).ensure_dirs()
    path = settings.data_csv(code)
    if not path.exists():
        raise FileNotFoundError(f"no data for {code} at {path}; run `kronos-cn fetch {code}` first")

    predictor = load_predictor(model_name, model_dir=model_dir or settings.model_dir, device=device, lookback=lookback)
    frame = load_frame(path)
    forecast = predict_frame(frame, predictor, pred_len, lookback, temperature, top_p, sample_count)
    forecast.to_csv(settings.pred_csv(code), index=False)
    return forecast

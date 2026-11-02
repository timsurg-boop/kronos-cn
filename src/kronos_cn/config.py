"""Runtime configuration.

Everything is overridable through environment variables so the project can be
cloned and run anywhere — no absolute paths baked into the code.

Defaults::

    KRONOS_HOME        ~/.kronos
    KRONOS_DATA_DIR    $KRONOS_HOME/data      # normalized *_kronos.csv
    KRONOS_RAW_DIR     $KRONOS_HOME/raw       # provider exports
    KRONOS_OUTPUT_DIR  $KRONOS_HOME/output    # charts, predictions, reports
    KRONOS_MODEL_DIR   $KRONOS_HOME/models    # Kronos weights (optional)
    TUSHARE_TOKEN      (empty)                # only needed for Tushare fetch
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_HOME = "~/.kronos"

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume", "amount")


def _path(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name, "").strip()
    return Path(raw).expanduser() if raw else default


def _optional_path(explicit: str | Path | None, default: Path) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser()
    return default


@dataclass(frozen=True)
class Settings:
    """Resolved paths and credentials for one run."""

    home: Path
    data_dir: Path
    raw_dir: Path
    output_dir: Path
    chart_dir: Path
    model_dir: Path
    tushare_token: str | None = None

    @classmethod
    def load(cls) -> Settings:
        home = _path("KRONOS_HOME", Path(DEFAULT_HOME).expanduser())
        output = _path("KRONOS_OUTPUT_DIR", home / "output")
        token = os.environ.get("TUSHARE_TOKEN", "").strip() or None
        return cls(
            home=home,
            data_dir=_path("KRONOS_DATA_DIR", home / "data"),
            raw_dir=_path("KRONOS_RAW_DIR", home / "raw"),
            output_dir=output,
            chart_dir=_path("KRONOS_CHARTS_DIR", output / "charts"),
            model_dir=_path("KRONOS_MODEL_DIR", home / "models"),
            tushare_token=token,
        )

    def with_data_dir(self, path: str | Path | None) -> Settings:
        """Return a copy pointing at another data directory (CLI overrides)."""
        return replace(self, data_dir=_optional_path(path, self.data_dir))

    def with_output_dir(self, path: str | Path | None) -> Settings:
        return replace(
            self,
            output_dir=_optional_path(path, self.output_dir),
            chart_dir=_optional_path(path, self.output_dir) / "charts",
        )

    def ensure_dirs(self) -> Settings:
        for directory in (self.data_dir, self.raw_dir, self.output_dir, self.chart_dir, self.model_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    # ---- file naming -------------------------------------------------
    def data_csv(self, code: str) -> Path:
        return self.data_dir / f"{code}_kronos.csv"

    def raw_csv(self, code: str) -> Path:
        return self.raw_dir / f"{code}_raw.csv"

    def pred_csv(self, code: str) -> Path:
        return self.output_dir / f"{code}_pred.csv"

    def chart_png(self, code: str, tag: str = "") -> Path:
        suffix = f"_{tag}" if tag else ""
        return self.chart_dir / f"{code}{suffix}.png"


def normalize_code(code: str) -> str:
    """Strip exchange suffixes and whitespace; keep the ``USA`` convention."""
    code = str(code).strip().upper()
    for suffix in (".SH", ".SZ", ".BJ"):
        if code.endswith(suffix):
            return code[: -len(suffix)]
    return code


def is_a_share(code: str) -> bool:
    code = normalize_code(code)
    return code.isdigit() and len(code) == 6


def market_suffix(code: str) -> str:
    """Return the Tushare-style exchange suffix for an A-share code."""
    code = normalize_code(code)
    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return ".SH"
    if code.startswith(("000", "001", "002", "003", "300", "301", "200")):
        return ".SZ"
    if code.startswith(("4", "8")):
        return ".BJ"
    return ""

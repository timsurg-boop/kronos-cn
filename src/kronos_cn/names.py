"""Symbol → display-name lookup.

A trimmed name table ships with the package (``assets/stock_names.json``) so
heatmaps and charts look right offline. ``refresh_names`` can rebuild it from
Akshare when that extra is installed.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

_ASSET = "stock_names.json"
_cache: dict[str, str] | None = None

#: Short Chinese aliases for common overseas tickers.
ALIASES = {
    "SPYUSA": "标普500",
    "QQQUSA": "纳指100",
    "DIAUSA": "道琼斯",
    "IWMUSA": "罗素2000",
    "BTCUSA": "比特币",
    "ETHUSA": "以太坊",
    "SOLUSA": "Solana",
    "DOGEUSA": "狗狗币",
    "XRPUSA": "瑞波",
    "AAPLUSA": "苹果",
    "MSFTUSA": "微软",
    "NVDAUSA": "英伟达",
    "TSLAUSA": "特斯拉",
    "GOOGLUSA": "谷歌",
    "AMZNUSA": "亚马逊",
    "METAUSA": "Meta",
}


def _load_bundled() -> dict[str, str]:
    try:
        with resources.files("kronos_cn.assets").joinpath(_ASSET).open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, ModuleNotFoundError):
        return {}
    # The bundled file is a flat {code: name} map; accept the legacy nested form.
    out: dict[str, str] = {}
    for code, value in data.items():
        if isinstance(value, dict):
            out[str(code)] = str(value.get("zh") or value.get("en") or code)
        else:
            out[str(code)] = str(value)
    return out


def load_names(extra: str | Path | None = None) -> dict[str, str]:
    """Load the bundled table, optionally merged with a user JSON file."""
    global _cache
    if _cache is None:
        _cache = _load_bundled()
    names = dict(_cache)
    if extra:
        path = Path(extra).expanduser()
        if path.exists():
            try:
                names.update(_load_from(path))
            except (json.JSONDecodeError, OSError):
                pass
    return names


def _load_from(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out[str(key)] = str(value.get("zh") or value.get("en") or key)
        else:
            out[str(key)] = str(value)
    return out


def get_name(code: str, extra: str | Path | None = None) -> str:
    code = str(code).strip().upper()
    if code in ALIASES:
        return ALIASES[code]
    names = load_names(extra)
    name = names.get(code)
    if name is None:
        base = code[:-3] if code.endswith("USA") else code
        name = names.get(base, base)
    # Providers prefix ex-dividend / ex-rights flags, e.g. "XD中国石化".
    for prefix in ("XD", "XR", "DR"):
        if name.startswith(prefix) and len(name) > len(prefix):
            name = name[len(prefix):]
    return name.replace(" ", "").replace("\u3000", "")


def refresh_names(out: str | Path | None = None) -> Path:
    """Rebuild the name table from Akshare (requires the ``fetch`` extra)."""
    import akshare as ak

    frame = ak.stock_info_a_code_name()
    mapping = {
        str(row["code"]).zfill(6): str(row["name"])
        for _, row in frame.iterrows()
        if str(row.get("code", "")).strip()
    }
    target = Path(out).expanduser() if out else Path(__file__).parent / "assets" / _ASSET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(mapping, ensure_ascii=False, indent=0), encoding="utf-8")
    return target

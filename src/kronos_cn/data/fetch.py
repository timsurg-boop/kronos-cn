"""Price download with an explicit provider chain.

Order: Akshare (free, no key) → Tushare (needs ``TUSHARE_TOKEN``).
Every provider is imported lazily so the base install stays lightweight.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from kronos_cn.config import Settings, is_a_share, market_suffix, normalize_code
from kronos_cn.data.convert import normalize


class FetchError(RuntimeError):
    pass


@dataclass
class FetchResult:
    frame: pd.DataFrame
    source: str


def _akshare_a_share(code: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    symbol = ("sh" if market_suffix(code) == ".SH" else "sz") + code
    frame = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="qfq")
    return normalize(frame)


def _akshare_a_share_weekly(code: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    frame = ak.stock_zh_a_hist(
        symbol=code, period="weekly", start_date=start, end_date=end, adjust="qfq"
    ).rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
        }
    )
    return normalize(frame)


def _akshare_us(ticker: str, start: str, end: str) -> pd.DataFrame:
    import akshare as ak

    frame = ak.stock_us_daily(symbol=ticker, adjust="qfq")
    if frame.empty:
        raise FetchError(f"no US data for {ticker}")
    frame = frame.rename(columns={"date": "date"})
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[(frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))]
    return normalize(frame)


def _tushare(code: str, start: str, end: str, token: str, freq: str) -> pd.DataFrame:
    import tushare as ts

    ts.set_token(token)
    ts_code = f"{normalize_code(code)}{market_suffix(code)}"
    frame = ts.pro_bar(ts_code=ts_code, adj="qfq", freq=freq, start_date=start, end_date=end)
    if frame is None or frame.empty:
        raise FetchError(f"Tushare returned no rows for {ts_code}")
    return normalize(frame)


def _compact(day: str | date) -> str:
    if isinstance(day, date):
        return day.strftime("%Y%m%d")
    return str(day).replace("-", "")


def fetch(
    code: str,
    start: str | date = "2018-01-01",
    end: str | date | None = None,
    freq: str = "D",
    settings: Settings | None = None,
    pause: float = 1.0,
) -> FetchResult:
    """Download one symbol and return it in canonical format."""
    settings = settings or Settings.load()
    code = normalize_code(code)
    end = end or date.today()
    start_s, end_s = _compact(start), _compact(end)
    errors: list[str] = []

    if is_a_share(code):
        attempts = [
            ("akshare", lambda: (
                _akshare_a_share_weekly(code, start_s, end_s)
                if freq in ("W", "ME")
                else _akshare_a_share(code, start_s, end_s)
            )),
        ]
        if settings.tushare_token:
            attempts.append(
                ("tushare", lambda: _tushare(code, start_s, end_s, settings.tushare_token, freq))
            )
    elif code.endswith("USA"):
        ticker = code[:-3]
        attempts = [("akshare-us", lambda: _akshare_us(ticker, start_s, end_s))]
    else:
        raise FetchError(
            f"unsupported symbol {code!r}: use a 6-digit A-share code or '<TICKER>USA'"
        )

    for source, call in attempts:
        try:
            frame = call()
            if frame.empty:
                raise FetchError("empty frame")
            return FetchResult(frame=frame, source=source)
        except Exception as exc:  # noqa: BLE001 - provider errors vary wildly
            errors.append(f"{source}: {exc}")
        time.sleep(pause)

    raise FetchError("all providers failed for " + code + " — " + " | ".join(errors))


def default_window(years: int = 8) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=365 * years)
    return start.isoformat(), end.isoformat()

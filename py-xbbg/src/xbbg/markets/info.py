"""Market information utilities for tickers and exchanges."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import logging
from typing import Any, cast

import pandas as pd

from xbbg.markets.bloomberg import _to_pandas_wide

logger = logging.getLogger(__name__)

__all__ = [
    "exch_info",
    "exch_info_bloomberg",
    "market_info",
    "market_timing",
    "ccy_pair",
    "convert_session_times_to_utc",
    "CurrencyPair",
]


@dataclass(frozen=True)
class CurrencyPair:
    """FX conversion metadata."""

    ticker: str
    factor: float
    power: float


def exch_info_bloomberg(ticker: str, **kwargs) -> pd.Series:
    """Get exchange info from Bloomberg API."""
    from .bloomberg import fetch_exchange_info
    from .sessions import derive_sessions

    if ref := kwargs.get("ref"):
        return exch_info_bloomberg(ticker=ref, **{k: v for k, v in kwargs.items() if k != "ref"})

    try:
        bbg_info = fetch_exchange_info(ticker=ticker)
        if bbg_info.source == "fallback":
            return pd.Series(dtype=object)

        sessions = derive_sessions(bbg_info)
        result: dict[str, object] = {"tz": bbg_info.timezone}
        if sessions.allday:
            result["allday"] = list(sessions.allday)
        if sessions.day:
            result["day"] = list(sessions.day)
        if sessions.pre:
            result["pre"] = list(sessions.pre)
        if sessions.post:
            result["post"] = list(sessions.post)
        if sessions.am:
            result["am"] = list(sessions.am)
        if sessions.pm:
            result["pm"] = list(sessions.pm)

        name = bbg_info.mic or bbg_info.exch_code or "Bloomberg"
        return pd.Series(result, name=name)
    except Exception as e:
        logger.warning("Failed to get Bloomberg exchange info for %s: %s", ticker, e)
        return pd.Series(dtype=object)


def exch_info(ticker: str, **kwargs) -> pd.Series:
    """Exchange info for given ticker."""
    if ref := kwargs.get("ref"):
        return exch_info(ticker=ref, **{k: v for k, v in kwargs.items() if k != "ref"})

    result = exch_info_bloomberg(ticker=ticker, **kwargs)
    if not result.empty:
        return result

    original = kwargs.get("original", "")
    if original:
        logger.warning("Bloomberg exchange info not found for: %s", original)
    return pd.Series(dtype=object)


def market_info(ticker: str) -> pd.Series:
    """Get market info for a ticker using Bloomberg metadata fields."""
    xbbg_module = importlib.import_module("xbbg")
    bdp_fn = cast("Any", xbbg_module.bdp)  # type: ignore[unresolved-attribute]

    t_info = ticker.split()
    if len(t_info) < 2:
        return pd.Series(dtype=object)

    asset = t_info[-1]
    if asset not in ["Equity", "Comdty", "Curncy", "Index", "Corp"]:
        return pd.Series(dtype=object)

    if asset == "Corp" and len(t_info) >= 2 and t_info[0] == "CDX":
        return pd.Series({"exch": "US", "tz": "America/New_York"})

    fields = ["EXCH_CODE", "ID_MIC_PRIM_EXCH", "IANA_TIME_ZONE"]
    is_generic_future = (
        asset in ["Index", "Comdty", "Curncy"]
        and len(t_info[0]) >= 2
        and t_info[0][-1].isdigit()
        and t_info[0][-2:-1].isalpha()
    )
    if is_generic_future:
        fields.append("FUT_GEN_MONTH")

    try:
        raw = bdp_fn(tickers=ticker, flds=fields)
        result = _to_pandas_wide(raw)
    except Exception as e:
        logger.warning("Failed to get market info from Bloomberg for %s: %s", ticker, e)
        return pd.Series(dtype=object)

    if result.empty:
        return pd.Series(dtype=object)

    row = result.iloc[0]
    cols = {c.lower(): c for c in result.columns}

    def _get(name: str):
        key = cols.get(name.lower())
        if key is None:
            return None
        val = row.get(key)
        if pd.isna(val):
            return None
        return val

    info: dict[str, object] = {}
    exch_code = _get("EXCH_CODE") or _get("ID_MIC_PRIM_EXCH")
    if exch_code:
        info["exch"] = exch_code

    tz = _get("IANA_TIME_ZONE")
    if tz:
        info["tz"] = tz

    fut_month = _get("FUT_GEN_MONTH")
    if fut_month:
        info["freq"] = fut_month
        info["is_fut"] = True
    else:
        info["is_fut"] = False

    return pd.Series(info)


def explode(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Explode helper retained for backward compatibility."""
    if data.empty:
        return pd.DataFrame()

    missing_cols = [col for col in columns if col not in data.columns]
    if missing_cols:
        logger.warning(
            "Missing columns %s in DataFrame for explode. Available columns: %s.",
            missing_cols,
            list(data.columns),
        )
        return pd.DataFrame()

    if len(columns) == 1:
        return data.explode(column=columns[0])
    return explode(data=data.explode(column=columns[-1]), columns=columns[:-1])


def ccy_pair(local: str, base: str = "USD") -> CurrencyPair:
    """Currency pair info using Rust FX helpers."""
    core = importlib.import_module("xbbg._core")
    ext_same_currency = cast("Any", core.ext_same_currency)
    ext_build_fx_pair = cast("Any", core.ext_build_fx_pair)

    if ext_same_currency(base, local):
        factor = 1.0
        if base and base[-1].islower():
            factor /= 100.0
        if local and local[-1].islower():
            factor *= 100.0
        return CurrencyPair(ticker="", factor=factor, power=1.0)

    fx_pair, factor, _from_ccy, _to_ccy = ext_build_fx_pair(local, base)
    return CurrencyPair(ticker=fx_pair, factor=float(factor), power=1.0)


def convert_session_times_to_utc(
    start_time: str,
    end_time: str,
    exchange_tz: str,
    time_fmt: str = "%Y-%m-%dT%H:%M:%S",
) -> tuple[str, str]:
    """Convert timezone-naive session times from exchange timezone to UTC."""
    if exchange_tz == "UTC":
        return start_time, end_time

    start_ts = pd.Timestamp(start_time).tz_localize(exchange_tz).tz_convert("UTC")
    end_ts = pd.Timestamp(end_time).tz_localize(exchange_tz).tz_convert("UTC")
    return start_ts.strftime(time_fmt), end_ts.strftime(time_fmt)


def _resolve_to_timezone(tz: str, exch_tz: str) -> str:
    if tz == "local":
        return exch_tz

    alias = {
        "NY": "America/New_York",
        "LN": "Europe/London",
        "TK": "Asia/Tokyo",
        "HK": "Asia/Hong_Kong",
    }
    if tz.upper() in alias:
        return alias[tz.upper()]

    if " " in tz:
        ref = exch_info(ticker=tz)
        if not ref.empty and "tz" in ref:
            return str(ref["tz"])

    return tz


def market_timing(ticker, dt, timing="EOD", tz="local", **kwargs) -> str:
    """Market close/open time for ticker."""
    exch = pd.Series(exch_info(ticker=ticker, **kwargs))
    required = {"tz", "allday", "day"}
    if not required.issubset(exch.index):
        logger.error("Required exchange information %s not found for ticker: %s", required, ticker)
        return ""

    mkt_time = {"BOD": exch.day[0], "FINISHED": exch.allday[-1]}.get(timing, exch.day[-1])
    cur_dt = str(pd.Timestamp(str(dt)).date())

    if tz == "local":
        return f"{cur_dt} {mkt_time}"

    from_tz = str(exch.tz)
    to_tz = _resolve_to_timezone(str(tz), from_tz)
    ts = pd.Timestamp(f"{cur_dt} {mkt_time}").tz_localize(from_tz).tz_convert(to_tz)
    return str(ts)

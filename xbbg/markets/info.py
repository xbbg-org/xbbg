"""Market information utilities for tickers and exchanges.

Provides functions to resolve exchange information, market timing, and asset configuration.
"""

from __future__ import annotations

import logging

import pandas as pd

from xbbg import const
from xbbg.core.utils import timezone

logger = logging.getLogger(__name__)

__all__ = [
    "exch_info",
    "exch_info_bloomberg",
    "market_info",
    "market_timing",
    "asset_config",
    "ccy_pair",
    "convert_session_times_to_utc",
]


# =============================================================================
# Bloomberg-backed exchange info
# =============================================================================


def exch_info_bloomberg(ticker: str, **kwargs) -> pd.Series:
    """Get exchange info from Bloomberg API.

    This function queries Bloomberg for exchange metadata and derives
    trading session windows dynamically.

    Args:
        ticker: Bloomberg ticker (e.g., 'AAPL US Equity', 'ES1 Index')
        **kwargs:
            ref: Reference ticker (used if primary ticker fails)

    Returns:
        pd.Series with keys: tz, allday, day, pre, post, am, pm (where applicable)
        Returns empty Series if Bloomberg data unavailable.

    Examples:
        >>> exch_info_bloomberg('AAPL US Equity')  # doctest: +SKIP
        tz        America/New_York
        allday      [04:00, 20:30]
        day         [09:30, 16:30]
        pre         [04:00, 09:30]
        post        [16:31, 20:30]
        dtype: object
    """
    from xbbg.markets.bloomberg import fetch_exchange_info
    from xbbg.markets.sessions import derive_sessions

    # Handle ref parameter - use reference ticker if provided
    if ref := kwargs.get("ref"):
        return exch_info_bloomberg(ticker=ref, **{k: v for k, v in kwargs.items() if k != "ref"})

    try:
        # Fetch from Bloomberg
        bbg_info = fetch_exchange_info(ticker)

        # If fallback (no Bloomberg data), return empty
        if bbg_info.source == "fallback":
            logger.debug("Bloomberg returned fallback for %s", ticker)
            return pd.Series(dtype=object)

        # Derive session windows
        sessions = derive_sessions(bbg_info)

        # Build result Series
        result = {"tz": bbg_info.timezone}

        # Add sessions as lists [start, end]
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

        # Use MIC or exch_code as the Series name
        name = bbg_info.mic or bbg_info.exch_code or "Bloomberg"

        return pd.Series(result, name=name)

    except Exception as e:
        logger.warning("Failed to get Bloomberg exchange info for %s: %s", ticker, e)
        return pd.Series(dtype=object)


def exch_info(ticker: str, **kwargs) -> pd.Series:
    """Exchange info for given ticker.

    Queries Bloomberg API for exchange metadata including timezone and
    trading session windows.

    Args:
        ticker: ticker or exchange
        **kwargs:
            ref: reference ticker or exchange
                 used as supplement if exchange info is not defined for `ticker`
            original: original ticker (for logging)

    Returns:
        pd.Series with keys: tz, allday, day, pre, post, am, pm (where applicable)

    Examples:
        >>> exch_info('SPY US Equity')  # doctest: +SKIP
        tz        America/New_York
        allday      [04:00, 20:00]
        day         [09:30, 16:00]
        post        [16:01, 20:00]
        pre         [04:00, 09:30]
        Name: XNGS, dtype: object
    """
    # Handle ref parameter
    if ref := kwargs.get("ref"):
        return exch_info(ticker=ref, **{k: v for k, v in kwargs.items() if k != "ref"})

    # Query Bloomberg for exchange info
    result = exch_info_bloomberg(ticker, **kwargs)
    if not result.empty:
        return result

    # Log if we got no data
    original = kwargs.get("original", "")
    if original:
        logger.warning("Bloomberg exchange info not found for: %s", original)
    return pd.Series(dtype=object)


def market_info(ticker: str) -> pd.Series:
    """Get market info for given ticker using Bloomberg.

    Queries Bloomberg for exchange code, timezone, and futures metadata.

    Args:
        ticker: Bloomberg full ticker

    Returns:
        pd.Series with keys: exch, tz, freq (for futures), is_fut

    Examples:
        >>> market_info('SPY US Equity').exch  # doctest: +SKIP
        'US'
        >>> market_info('7203 JT Equity').exch  # doctest: +SKIP
        'JT'
        >>> market_info('ES1 Index').freq  # doctest: +SKIP
        'HMUZ'
        >>> market_info('CL1 Comdty').freq  # doctest: +SKIP
        'FGHJKMNQUVXZ'
    """
    from xbbg.api.reference import bdp  # noqa: PLC0415

    t_info = ticker.split()

    # Handle invalid tickers
    if len(t_info) < 2:
        return pd.Series(dtype=object)

    asset = t_info[-1]

    # Allow only supported asset types; special-case certain Corp tickers
    if asset not in ["Equity", "Comdty", "Curncy", "Index", "Corp"]:
        return pd.Series(dtype=object)

    # Special case for CDX tickers
    if asset == "Corp" and len(t_info) >= 2 and t_info[0] == "CDX":
        return pd.Series({"exch": "US", "tz": "America/New_York"})

    # Query Bloomberg for market metadata
    fields = ["EXCH_CODE", "ID_MIC_PRIM_EXCH", "IANA_TIME_ZONE"]

    # For futures/generic tickers, also get cycle months
    is_generic_future = (
        asset in ["Index", "Comdty", "Curncy"]
        and len(t_info[0]) >= 2
        and t_info[0][-1].isdigit()
        and t_info[0][-2:-1].isalpha()
    )
    if is_generic_future:
        fields.append("FUT_GEN_MONTH")

    try:
        result = bdp(ticker, fields)
    except Exception as e:
        logger.warning("Failed to get market info from Bloomberg for %s: %s", ticker, e)
        return pd.Series(dtype=object)

    if result.empty:
        return pd.Series(dtype=object)

    row = result.iloc[0]

    # Build the response Series
    info = {}

    # Exchange code
    exch_code = row.get("EXCH_CODE") or row.get("ID_MIC_PRIM_EXCH")
    if exch_code:
        info["exch"] = exch_code

    # Timezone
    tz = row.get("IANA_TIME_ZONE")
    if tz:
        info["tz"] = tz

    # Futures cycle months (acts as freq indicator)
    if "FUT_GEN_MONTH" in row and row.get("FUT_GEN_MONTH"):
        info["freq"] = row["FUT_GEN_MONTH"]
        info["is_fut"] = True
    else:
        info["is_fut"] = False

    return pd.Series(info)


def asset_config(asset: str) -> pd.DataFrame:
    """Get asset configuration.

    .. deprecated::
        This function is deprecated and returns empty DataFrame.
        Use `market_info(ticker)` to get ticker metadata from Bloomberg directly,
        or use Bloomberg fields like FUT_GEN_MONTH for futures cycle information.

    Args:
        asset: asset name

    Returns:
        pd.DataFrame: Empty DataFrame. This function is deprecated.
    """
    import warnings

    warnings.warn(
        "asset_config() is deprecated. Use market_info(ticker) to get ticker metadata "
        "from Bloomberg directly, or use bdp(ticker, 'FUT_GEN_MONTH') for futures cycles.",
        DeprecationWarning,
        stacklevel=2,
    )
    return pd.DataFrame()


def explode(data: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Explode data by columns.

    Args:
        data: pd.DataFrame
        columns: columns to explode

    Returns:
        pd.DataFrame
    """
    if data.empty:
        return pd.DataFrame()

    # Check if all required columns exist before attempting to explode
    # This prevents KeyError when DataFrames are created from malformed config entries
    # (e.g., empty dicts like Corp: [{}] which create DataFrames with no columns)
    missing_cols = [col for col in columns if col not in data.columns]
    if missing_cols:
        logger.warning(
            "Missing columns %s in DataFrame for explode. "
            "Available columns: %s. "
            "Returning empty DataFrame. This may indicate malformed config data.",
            missing_cols,
            list(data.columns),
        )
        return pd.DataFrame()

    if len(columns) == 1:
        return data.explode(column=columns[0])

    return explode(
        data=data.explode(column=columns[-1]),
        columns=columns[:-1],
    )


def ccy_pair(local, base="USD") -> const.CurrencyPair:
    """Currency pair info.

    Uses Bloomberg's INVERSE_QUOTED field to determine the quote direction.
    Handles sub-unit currencies like GBp (pence) by checking for lowercase suffixes.

    Args:
        local: local currency
        base: base currency

    Returns:
        CurrencyPair with ticker, factor, and power for FX conversion.
        The FX rate can be calculated as: (BDP(ticker) / factor) ** power

    Examples:
        >>> ccy_pair(local='HKD', base='USD')  # doctest: +SKIP
        CurrencyPair(ticker='HKD Curncy', factor=1.0, power=1.0)
        >>> ccy_pair(local='GBp')  # doctest: +SKIP
        CurrencyPair(ticker='GBP Curncy', factor=100.0, power=-1.0)
        >>> ccy_pair(local='USD', base='GBp')  # doctest: +SKIP
        CurrencyPair(ticker='GBP Curncy', factor=0.01, power=1.0)
        >>> ccy_pair(local='GBP', base='GBp')  # doctest: +SKIP
        CurrencyPair(ticker='', factor=0.01, power=1.0)
        >>> ccy_pair(local='GBp', base='GBP')  # doctest: +SKIP
        CurrencyPair(ticker='', factor=100.0, power=1.0)
    """
    # Handle same currency (e.g., GBP to GBp or vice versa)
    if base.lower() == local.lower():
        factor = 1.0
        # Handle sub-unit conversions (e.g., GBp = pence, lowercase suffix)
        if base[-1].islower():
            factor /= 100.0
        if local[-1].islower():
            factor *= 100.0
        return const.CurrencyPair(ticker="", factor=factor, power=1.0)

    # Determine factor for sub-unit currencies (lowercase suffix = sub-unit like pence)
    local_factor = 100.0 if local[-1].islower() else 1.0
    base_factor = 100.0 if base[-1].islower() else 1.0

    # Normalize currency codes (uppercase)
    local_norm = local.upper()
    base_norm = base.upper()

    # Construct the Bloomberg ticker - use the local currency
    ticker = f"{local_norm} Curncy"

    # Query Bloomberg for quote direction
    from xbbg.api.reference import bdp  # noqa: PLC0415

    try:
        result = bdp(ticker, ["INVERSE_QUOTED", "BASE_CRNCY"])
    except Exception as e:
        logger.error("Failed to query Bloomberg for currency %s: %s", ticker, e)
        return const.CurrencyPair(ticker="", factor=1.0, power=1.0)

    if result.empty:
        logger.warning("No Bloomberg data for currency ticker: %s", ticker)
        return const.CurrencyPair(ticker="", factor=1.0, power=1.0)

    # Check if the ticker's base currency matches our base
    ticker_base = result.iloc[0].get("BASE_CRNCY", "USD")
    if ticker_base and ticker_base.upper() != base_norm:
        # The ticker's base doesn't match our requested base
        # For now, log a warning but still return what we have
        logger.debug(
            "Currency ticker %s has base %s, but requested base is %s",
            ticker,
            ticker_base,
            base_norm,
        )

    # Determine power from INVERSE_QUOTED field
    # INVERSE_QUOTED='Y' means quote is in LOCAL/BASE (e.g., EUR/USD = 1.18 means 1 EUR = 1.18 USD)
    # INVERSE_QUOTED='N' means quote is in BASE/LOCAL (e.g., USD/JPY = 155 means 1 USD = 155 JPY)
    inverse_quoted = result.iloc[0].get("INVERSE_QUOTED", "N")
    power = -1.0 if inverse_quoted == "Y" else 1.0

    # Calculate final factor accounting for sub-units
    factor = local_factor / base_factor

    return const.CurrencyPair(
        ticker=ticker,
        factor=factor,
        power=power,
    )


def convert_session_times_to_utc(
    start_time: str,
    end_time: str,
    exchange_tz: str,
    time_fmt: str = "%Y-%m-%dT%H:%M:%S",
) -> tuple[str, str]:
    """Convert timezone-naive session times from exchange timezone to UTC.

    Bloomberg API expects UTC times, but session windows are typically
    timezone-naive strings in the exchange's local timezone. This function
    converts them to UTC format strings suitable for Bloomberg requests.

    Args:
        start_time: Start time string (timezone-naive, in exchange timezone).
        end_time: End time string (timezone-naive, in exchange timezone).
        exchange_tz: Exchange timezone (e.g., 'America/New_York').
        time_fmt: Output time format. Defaults to '%Y-%m-%dT%H:%M:%S'.

    Returns:
        Tuple of (start_time_utc, end_time_utc) as formatted strings.

    Examples:
        >>> convert_session_times_to_utc(
        ...     '2025-11-14T09:30:00',
        ...     '2025-11-14T10:00:00',
        ...     'America/New_York'
        ... )
        ('2025-11-14T14:30:00', '2025-11-14T15:00:00')
        >>> convert_session_times_to_utc(
        ...     '2025-11-14T09:30:00',
        ...     '2025-11-14T10:00:00',
        ...     'UTC'
        ... )
        ('2025-11-14T09:30:00', '2025-11-14T10:00:00')
    """
    if exchange_tz == "UTC":
        return start_time, end_time

    start_ts = pd.Timestamp(start_time).tz_localize(exchange_tz).tz_convert("UTC")
    end_ts = pd.Timestamp(end_time).tz_localize(exchange_tz).tz_convert("UTC")
    return start_ts.strftime(time_fmt), end_ts.strftime(time_fmt)


def market_timing(ticker, dt, timing="EOD", tz="local", **kwargs) -> str:
    """Market close time for ticker.

    Args:
        ticker: ticker name
        dt: date
        timing: [EOD (default), BOD]
        tz: conversion to timezone
        **kwargs: Passed through to exchange lookup and timezone helpers.

    Returns:
        str: date & time.

    Examples:
        >>> market_timing('7267 JT Equity', dt='2018-09-10')  # doctest: +SKIP
        '2018-09-10 14:58'
        >>> market_timing('7267 JT Equity', dt='2018-09-10', tz=timezone.TimeZone.NY)  # doctest: +SKIP
        '2018-09-10 01:58:00-04:00'
        >>> market_timing('7267 JT Equity', dt='2018-01-10', tz='NY')  # doctest: +SKIP
        '2018-01-10 00:58:00-05:00'
        >>> market_timing('7267 JT Equity', dt='2018-09-10', tz='SPX Index')  # doctest: +SKIP
        '2018-09-10 01:58:00-04:00'
        >>> market_timing('8035 JT Equity', dt='2018-09-10', timing='BOD')  # doctest: +SKIP
        '2018-09-10 09:01'
        >>> market_timing('Z 1 Index', dt='2018-09-10', timing='FINISHED')  # doctest: +SKIP
        '2018-09-10 21:00'
        >>> market_timing('TESTTICKER Corp', dt='2018-09-10') == ''  # doctest: +SKIP
        True
    """
    exch = pd.Series(exch_info(ticker=ticker, **kwargs))
    required = {"tz", "allday", "day"}
    if not required.issubset(exch.index):
        logger.error("Required exchange information %s not found for ticker: %s", required, ticker)
        return ""

    mkt_time = {"BOD": exch.day[0], "FINISHED": exch.allday[-1]}.get(timing, exch.day[-1])
    cur_dt = pd.Timestamp(str(dt)).strftime("%Y-%m-%d")
    if tz == "local":
        return f"{cur_dt} {mkt_time}"
    return timezone.tz_convert(f"{cur_dt} {mkt_time}", to_tz=tz, from_tz=exch.tz)

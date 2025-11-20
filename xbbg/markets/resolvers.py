"""Resolvers for market-specific ticker transformations and helpers."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import pandas as pd

from xbbg import const

if TYPE_CHECKING:
    from xbbg.core.domain.context import BloombergContext

logger = logging.getLogger(__name__)


def active_futures(ticker: str, dt, **kwargs) -> str:
    """Active futures contract.

    Args:
        ticker: Generic futures ticker, i.e., UX1 Index, ESA Index, Z A Index, CLA Comdty, etc.
            Must be a generic contract (e.g., UX1 Index), not a specific contract (e.g., UXZ5 Index).
        dt: date
        **kwargs: Passed through to downstream resolvers (e.g., logging).

    Returns:
        str: ticker name

    Raises:
        ValueError: If ticker is a specific contract instead of a generic one.
    """
    # Check if ticker is already a specific contract (contains month codes)
    month_codes = set(const.Futures.values())  # {'F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'}
    ticker_base = ticker.rsplit(' ', 1)[0]  # Remove asset type (Index, Comdty, etc.)

    # Generic tickers end with just a number (1, 2, etc.) like UX1, ESA1, ZA1
    # Specific contracts end with month code + year digits like UXZ5, UXZ24, ESAM24
    # Pattern: ends with [month_code][1-2 digits] where month_code is immediately before digits
    month_code_pattern = rf'[{re.escape("".join(month_codes))}]'
    # Match pattern: [anything][month_code][1-2 digits] at the end
    match = re.search(rf'(.+)({month_code_pattern})(\d{{1,2}})$', ticker_base)
    if match:
        prefix, month_char, digits = match.groups()
        # If it ends with [month_code][2 digits] it's definitely specific
        # If it ends with [month_code][1 digit], check length: very short (3 chars) is likely generic
        if len(digits) == 2:
            # Two digit year = definitely specific contract
            raise ValueError(
                f"'{ticker}' appears to be a specific futures contract (ends with month code + 2-digit year), "
                f"not a generic one. Please use a generic ticker (e.g., 'UX1 Index' instead of 'UXZ24 Index'). "
                f"Generic tickers end with a number (1, 2, etc.) before the asset type."
            )
        # Single digit: could be generic (UX1) or specific (UXZ5)
        # Check length: very short (3 chars) with single digit is likely generic
        if len(digits) == 1 and len(ticker_base) > 3:
            # Longer ticker ending in [month_code][digit] is likely specific (e.g., "UXZ5", "ESAM4")
            raise ValueError(
                f"'{ticker}' appears to be a specific futures contract, not a generic one. "
                f"Please use a generic ticker (e.g., 'UX1 Index' instead of 'UXZ5 Index'). "
                f"Generic tickers end with a number (1, 2, etc.) before the asset type."
            )

    # Import directly from API modules to avoid circular dependency
    from xbbg.api.reference import bdp  # noqa: PLC0415

    t_info = ticker.split()
    prefix, asset = ' '.join(t_info[:-1]), t_info[-1]
    info = const.market_info(f'{prefix[:-1]}1 {asset}')

    f1, f2 = f'{prefix[:-1]}1 {asset}', f'{prefix[:-1]}2 {asset}'
    raw_freq = info.get('freq')
    if isinstance(raw_freq, str) and raw_freq.strip():
        freq_code = raw_freq.strip()
    else:
        logger.error(
            "Missing 'freq' configuration in assets.yml for futures root '%s' (asset type: %s). Please set 'freq' explicitly.",
            prefix[:-1], asset
        )
        return ''

    fut_2 = fut_ticker(gen_ticker=f2, dt=dt, freq=freq_code, **kwargs)
    fut_1 = fut_ticker(gen_ticker=f1, dt=dt, freq=freq_code, **kwargs)

    fut_tk = bdp(tickers=[fut_1, fut_2], flds='last_tradeable_dt')

    first_matu = pd.Timestamp(fut_tk['last_tradeable_dt'].iloc[0])
    if pd.Timestamp(dt).month < first_matu.month: return fut_1

    dts = pd.bdate_range(end=dt, periods=10)
    from xbbg.api.historical import bdh  # noqa: PLC0415
    volume = bdh(tickers=list(fut_tk.index), flds='volume', start_date=dts[0], end_date=dts[-1])
    if volume.empty: return fut_1
    return volume.iloc[-1].idxmax()[0]


def fut_ticker(gen_ticker: str, dt, freq: str, **kwargs) -> str:
    """Get proper ticker from generic ticker.

    Args:
        gen_ticker: generic ticker
        dt: date
        freq: futures contract frequency
        **kwargs: Passed through to Bloomberg fetch and logging.

    Returns:
        str: exact futures ticker
    """
    # Logger is module-level
    dt = pd.Timestamp(dt)
    t_info = gen_ticker.split()
    pre_dt = pd.bdate_range(end='today', periods=1)[-1]
    same_month = (pre_dt.month == dt.month) and (pre_dt.year == dt.year)

    asset = t_info[-1]
    if asset in ['Index', 'Curncy', 'Comdty']:
        ticker = ' '.join(t_info[:-1])
        prefix, idx, postfix = ticker[:-1], int(ticker[-1]) - 1, asset

    elif asset == 'Equity':
        ticker = t_info[0]
        prefix, idx, postfix = ticker[:-1], int(ticker[-1]) - 1, ' '.join(t_info[1:])

    else:
        logger.error('Unknown asset type for generic ticker: %s (expected Index, Curncy, Comdty, or Equity)', gen_ticker)
        return ''

    month_ext = 4 if asset == 'Comdty' else 2
    eff_freq = (freq or '').strip().upper() if isinstance(freq, str) else None
    if not eff_freq:
        logger.error("Missing or invalid 'freq' parameter for generic ticker '%s'. Please provide explicit 'freq' in assets.yml.", gen_ticker)
        return ''
    if eff_freq == 'M':
        eff_freq = 'ME'
    elif eff_freq == 'Q':
        eff_freq = 'QE-DEC'
    months = pd.date_range(start=dt, periods=max(idx + month_ext, 3), freq=eff_freq)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Computing futures expiry dates for %d months', len(months))

    def to_fut(month):
        return prefix + const.Futures[month.strftime('%b')] + \
            month.strftime('%y')[-1 if same_month else -2:] + ' ' + postfix

    fut = [to_fut(m) for m in months]
    # Guard list conversion - only log if DEBUG enabled (avoid string conversion overhead)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Attempting to resolve %d futures contracts', len(fut))
    # Import directly from API modules to avoid circular dependency
    from xbbg.api.reference import bdp  # lazy
    # noinspection PyBroadException
    try:
        fut_matu = bdp(tickers=fut, flds='last_tradeable_dt')
    except Exception as e1:
        logger.error('Failed to download futures contracts (attempt 1): %s. Tickers: %s', e1, fut)
        # noinspection PyBroadException
        try:
            fut = fut[:-1]
            logger.debug('Retrying futures contract resolution (attempt 2): %s', fut)
            fut_matu = bdp(tickers=fut, flds='last_tradeable_dt')
        except Exception as e2:
            logger.error('Failed to download futures contracts (attempt 2): %s. Tickers: %s', e2, fut)
            return ''

    if 'last_tradeable_dt' not in fut_matu:
        logger.warning('No valid futures contracts found for: %s', fut)
        return ''

    fut_matu.sort_values(by='last_tradeable_dt', ascending=True, inplace=True)
    sub_fut = fut_matu[pd.DatetimeIndex(fut_matu.last_tradeable_dt) > dt]
    # Guard len() calls - only compute if DEBUG logging is enabled
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Futures maturity chain: %d contracts', len(fut_matu))
        logger.debug('Selecting futures contract at index %d from %d available contracts', idx, len(sub_fut))
    return sub_fut.index.values[idx]


def cdx_ticker(
    gen_ticker: str,
    dt,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Resolve generic CDX 5Y ticker (e.g., 'CDX IG CDSI GEN 5Y Corp') to concrete series.

    Uses Bloomberg fields:
      - rolling_series: returns current on-the-run series number
      - on_the_run_current_bd_indicator: 'Y' if on-the-run
      - cds_first_accrual_start_date: start date of current series trading

    Args:
        gen_ticker: Generic CDX ticker.
        dt: Date to resolve for.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Resolved ticker string.
    """
    # Logger is module-level
    from xbbg.core.domain.context import split_kwargs

    dt = pd.Timestamp(dt)
    # Import directly from API modules to avoid circular dependency
    from xbbg.api.reference import bdp  # lazy

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    # Convert context to kwargs for bdp call
    safe_kwargs = ctx.to_kwargs()

    try:
        info = bdp(
            tickers=gen_ticker,
            flds=['rolling_series', 'on_the_run_current_bd_indicator', 'cds_first_accrual_start_date'],
            **safe_kwargs,
        )
    except Exception as e:
        logger.error('Failed to fetch CDX metadata for generic ticker %s: %s', gen_ticker, e)
        return ''

    if info.empty or 'rolling_series' not in info:
        logger.warning('No rolling series configuration found for CDX ticker: %s', gen_ticker)
        return ''

    series = info.loc[gen_ticker, 'rolling_series']
    try:
        series = int(series)
    except Exception:
        series = series

    tokens = gen_ticker.split()
    if 'GEN' not in tokens:
        logger.warning('Generic ticker %s does not contain expected GEN token for CDX resolution', gen_ticker)
        return ''
    tokens[tokens.index('GEN')] = f'S{series}'
    resolved = ' '.join(tokens)

    # If dt is before first accrual date of current series, use prior series
    faccr_col = 'cds_first_accrual_start_date'
    try:
        start_dt = pd.Timestamp(info.loc[gen_ticker, faccr_col]) if faccr_col in info else None
    except Exception:
        start_dt = None

    if (start_dt is not None) and (dt < start_dt) and isinstance(series, int) and series > 1:
        tokens[tokens.index(f'S{series}')] = f'S{series - 1}'
        resolved = ' '.join(tokens)

    return resolved


def active_cdx(
    gen_ticker: str,
    dt,
    lookback_days: int = 10,
    ctx: BloombergContext | None = None,
    **kwargs,
) -> str:
    """Choose active CDX series for a date, preferring on-the-run unless it's not started yet.

    If ambiguous, prefer the series with recent non-empty PX_LAST over the lookback window.

    Args:
        gen_ticker: Generic CDX ticker.
        dt: Date to resolve for.
        lookback_days: Number of days to look back for activity.
        ctx: Bloomberg context (infrastructure kwargs only). If None, will be
            extracted from kwargs for backward compatibility.
        **kwargs: Legacy kwargs support. If ctx is provided, kwargs are ignored.

    Returns:
        Active ticker string.
    """
    from xbbg.core.domain.context import split_kwargs

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra

    cur = cdx_ticker(gen_ticker=gen_ticker, dt=dt, ctx=ctx)
    if not cur:
        return ''

    # Compute previous series candidate
    parts = cur.split()
    prev = ''
    for i, tok in enumerate(parts):
        if tok.startswith('S') and tok[1:].isdigit():
            s = int(tok[1:])
            if s > 1:
                parts[i] = f'S{s - 1}'
                prev = ' '.join(parts)
            break

    # If no prev candidate, return current
    if not prev:
        return cur

    # Import directly from API modules to avoid circular dependency
    from xbbg.api.historical import bdh  # lazy
    from xbbg.api.reference import bdp  # lazy
    # Convert context to kwargs for bdp/bdh calls
    safe_kwargs = ctx.to_kwargs()
    # If dt is before accrual start, prefer prev
    try:
        cur_meta = bdp(cur, ['cds_first_accrual_start_date'], **safe_kwargs)
        cur_start = pd.Timestamp(cur_meta.iloc[0, 0]) if not cur_meta.empty else None
    except Exception:
        cur_start = None

    if (cur_start is not None) and (pd.Timestamp(dt) < cur_start):
        return prev

    # Otherwise, pick one with recent activity (PX_LAST availability)
    end = pd.Timestamp(dt)
    start = end - pd.Timedelta(days=lookback_days)
    try:
        px = bdh([cur, prev], ['PX_LAST'], start_date=start, end_date=end, **safe_kwargs)
        if px.empty:
            return cur
        last_non_na = px.xs('PX_LAST', axis=1, level=1).ffill().iloc[-1]
        return last_non_na.dropna().index[0] if last_non_na.notna().any() else cur
    except Exception:
        return cur



"""Cache utilities for Bloomberg data (paths, adapters, lookup).

Provides path resolution, cache adapters, and cache lookup utilities
for Bloomberg intraday bar data and reference data (BDP/BDS).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from xbbg import const
from xbbg.core.config import overrides
from xbbg.core.domain import contracts
from xbbg.core.utils import utils
from xbbg.io import files

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================================
# Path Resolution
# ============================================================================


def bar_file(ticker: str, dt, typ='TRADE') -> str:
    """Data file location for Bloomberg historical data.

    Args:
        ticker: ticker name
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]

    Returns:
        str: File location or empty string if BBG_ROOT not set.
    """
    data_path_str = os.environ.get(overrides.BBG_ROOT, '')
    if not data_path_str:
        # Don't log warning here - it will be logged in cache adapter when caching is requested
        return ''
    data_path = Path(data_path_str)
    asset = ticker.split()[-1]
    proper_ticker = ticker.replace('/', '_')
    cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
    return (data_path / asset / proper_ticker / typ / f'{cur_dt}.parq').as_posix()


def ref_file(
        ticker: str, fld: str, has_date=False, cache=False, ext='parq', **kwargs
) -> str:
    """Data file location for Bloomberg reference data.

    Args:
        ticker: ticker name
        fld: field
        has_date: whether add current date to data file
        cache: if has_date is True, whether to load file from latest cached
        ext: file extension
        **kwargs: other overrides passed to ref function

    Returns:
        str: File location or empty string if not cached.
    """
    data_path_str = os.environ.get(overrides.BBG_ROOT, '')
    if (not data_path_str) or (not cache):
        if cache and not data_path_str:
            logger.warning(
                'BBG_ROOT environment variable not set. Caching requested but disabled. '
                'Set BBG_ROOT to enable data caching.'
            )
        return ''
    data_path = Path(data_path_str)

    proper_ticker = ticker.replace('/', '_')
    cache_days = kwargs.pop('cache_days', 10)
    root = data_path / ticker.split()[-1] / proper_ticker / fld

    ref_kw = {k: v for k, v in kwargs.items() if k not in overrides.PRSV_COLS}
    info = utils.to_str(ref_kw)[1:-1].replace('|', '_') if len(ref_kw) > 0 else 'ovrd=None'

    if has_date:
        cache_file = (root / f'asof=[cur_date], {info}.{ext}').as_posix()
        cur_dt = utils.cur_time()
        start_dt = pd.date_range(end=cur_dt, freq=f'{cache_days}D', periods=2)[0]
        for dt in pd.date_range(start=start_dt, end=cur_dt, normalize=True)[1:][::-1]:
            cur_file = cache_file.replace('[cur_date]', dt.strftime("%Y-%m-%d"))
            if files.exists(cur_file):
                return cur_file
        return cache_file.replace('[cur_date]', str(cur_dt))

    return (root / f'{info}.{ext}').as_posix()


def save_intraday(data: pd.DataFrame, ticker: str, dt, typ='TRADE', **kwargs):
    """Check whether data is done for the day and save.

    Args:
        data: data
        ticker: ticker
        dt: date
        typ: [TRADE, BID, ASK, BID_BEST, ASK_BEST, BEST_BID, BEST_ASK]
        **kwargs: Additional options forwarded to timing/logging helpers.
    """
    cur_dt = pd.Timestamp(dt).strftime('%Y-%m-%d')
    info = f'{ticker} / {cur_dt} / {typ}'
    data_file = bar_file(ticker=ticker, dt=dt, typ=typ)
    if not data_file:
        return

    if data.empty:
        logger.warning('No data to save for %s (empty DataFrame)', info)
        return

    exch = const.exch_info(ticker=ticker, **kwargs)
    if exch.empty:
        return

    end_time = pd.Timestamp(
        const.market_timing(ticker=ticker, dt=dt, timing='FINISHED', **kwargs)
    ).tz_localize(exch.tz)
    now = pd.Timestamp('now', tz=exch.tz) - pd.Timedelta('1h')

    if end_time > now:
        logger.debug('Skipping save: market close time %s is less than 1 hour ago (%s), data may be incomplete', end_time, now)
        return

    if logger.isEnabledFor(logging.INFO):
        logger.info('Saving intraday data to cache: %s (%d rows)', data_file, len(data))
    else:
        logger.info('Saving intraday data to cache: %s', data_file)
    files.create_folder(data_file, is_file=True)
    data.to_parquet(data_file)


# ============================================================================
# Cache Adapters
# ============================================================================


class BarCacheAdapter:
    """Cache adapter for intraday bar data (parquet-based)."""

    def load(
        self,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> pd.DataFrame | None:
        """Load cached bar data if available."""
        if not session_window.is_valid():
            return None

        data_file = bar_file(ticker=request.ticker, dt=request.dt, typ=request.event_type)
        if not data_file:
            # BBG_ROOT not set - warning already logged in bar_file
            return None
        if not files.exists(data_file):
            return None

        try:
            from xbbg.utils import pipeline

            res = (
                pd.read_parquet(data_file)
                .pipe(pipeline.add_ticker, ticker=request.ticker)
                .loc[session_window.start_time:session_window.end_time]
            )

            if not res.empty:
                logger.debug('Loading cached Bloomberg intraday data from: %s', data_file)
                return res
        except Exception as e:
            logger.debug('Cache load failed: %s', e)

        return None

    def save(
        self,
        data: pd.DataFrame,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> None:
        """Save bar data to cache."""
        if data.empty:
            logger.warning('No data to save for %s / %s', request.ticker, request.to_date_string())
            return

        # Check if BBG_ROOT is set before attempting to save
        data_path_str = os.environ.get(overrides.BBG_ROOT, '')
        if not data_path_str:
            logger.warning(
                'BBG_ROOT environment variable not set. Cannot save cache for %s / %s. '
                'Set BBG_ROOT to enable data caching.',
                request.ticker,
                request.to_date_string(),
            )
            return

        ctx_kwargs = request.context.to_kwargs() if request.context else {}
        save_intraday(
            data=data[request.ticker] if request.ticker in data.columns else data,
            ticker=request.ticker,
            dt=request.dt,
            typ=request.event_type,
            **ctx_kwargs,
        )


class TickCacheAdapter:
    """Cache adapter for tick data (future implementation)."""

    def load(
        self,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> pd.DataFrame | None:
        """Load cached tick data (not implemented yet)."""
        return None

    def save(
        self,
        data: pd.DataFrame,
        request: contracts.DataRequest,
        session_window: contracts.SessionWindow,
    ) -> None:
        """Save tick data (not implemented yet)."""
        ...


# ============================================================================
# Cache Lookup
# ============================================================================




"""Market information utilities for tickers and exchanges.

Provides functions to resolve exchange information, market timing, and asset configuration.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from xbbg import const
from xbbg.core.utils import timezone
from xbbg.io import files, param

logger = logging.getLogger(__name__)

__all__ = [
    'exch_info',
    'market_info',
    'market_timing',
    'asset_config',
    'ccy_pair',
    'convert_session_times_to_utc',
]


def exch_info(ticker: str, **kwargs) -> pd.Series:
    """Exchange info for given ticker.

    Args:
        ticker: ticker or exchange
        **kwargs:
            ref: reference ticker or exchange
                 used as supplement if exchange info is not defined for `ticker`
            original: original ticker (for logging)
            config: info from exch.yml

    Returns:
        pd.Series

    Examples:
        >>> exch_info('SPY US Equity')  # doctest: +SKIP
        tz        America/New_York
        allday      [04:00, 20:00]
        day         [09:30, 16:00]
        post        [16:01, 20:00]
        pre         [04:00, 09:30]
        Name: EquityUS, dtype: object
        >>> exch_info('SPY US Equity', ref='EquityUS')  # doctest: +SKIP
        tz        America/New_York
        allday      [04:00, 20:00]
        day         [09:30, 16:00]
        post        [16:01, 20:00]
        pre         [04:00, 09:30]
        Name: EquityUS, dtype: object
        >>> exch_info('ES1 Index')  # doctest: +SKIP
        tz        America/New_York
        allday      [18:00, 17:00]
        day         [08:00, 17:00]
        Name: CME, dtype: object
        >>> exch_info('ESM0 Index', ref='ES1 Index')  # doctest: +SKIP
        tz        America/New_York
        allday      [18:00, 17:00]
        day         [08:00, 17:00]
        Name: CME, dtype: object
        >>> exch_info('Z 1 Index')  # doctest: +SKIP
        tz         Europe/London
        allday    [01:00, 21:00]
        day       [01:00, 21:00]
        Name: FuturesFinancialsICE, dtype: object
        >>> exch_info('TESTTICKER Corp')  # doctest: +SKIP
        Series([], dtype: object)
        >>> exch_info('US')  # doctest: +SKIP
        tz        America/New_York
        allday      [04:00, 20:00]
        day         [09:30, 16:00]
        post        [16:01, 20:00]
        pre         [04:00, 09:30]
        Name: EquityUS, dtype: object
        >>> exch_info('UXF1UXG1 Index')  # doctest: +SKIP
        tz        America/New_York
        allday      [18:00, 17:00]
        day         [18:00, 17:00]
        Name: FuturesCBOE, dtype: object
        >>> exch_info('TESTTICKER Index', original='TESTTICKER Index').empty  # doctest: +SKIP
        True
        >>> exch_info('TESTTCK Index')  # doctest: +SKIP
        Series([], dtype: object)
    """
    if ref := kwargs.get('ref'):
        return exch_info(ticker=ref, **{k: v for k, v in kwargs.items() if k != 'ref'})

    exch = kwargs.get('config', param.load_config(cat='exch'))
    original = kwargs.get('original', '')

    # Handle empty exchange config
    if exch.empty:
        if original:
            logger.error('Exchange information not found for ticker: %s', original)
        return pd.Series(dtype=object)

    # Case 1: Use exchange directly
    if ticker in exch.index:
        info = exch.loc[ticker].dropna()
        if info.reindex(['allday', 'tz']).dropna().size < 2:
            logger.error(
                f'required info (allday + tz) cannot be found in {original or ticker} ...'
            )
            return pd.Series(dtype=object)
        if 'day' not in info:
            info['day'] = info['allday']
        return info.dropna().apply(param.to_hours)

    if original:
        logger.error('Exchange information not found for ticker: %s', original)
        return pd.Series(dtype=object)

    # Case 2: Use ticker to find exchange
    if not (exch_name := market_info(ticker=ticker).get('exch', '')):
        return pd.Series(dtype=object)
    return exch_info(ticker=exch_name, original=ticker, config=exch)


def market_info(ticker: str) -> pd.Series:
    """Get info for given ticker.

    Args:
        ticker: Bloomberg full ticker

    Returns:
        pd.Series

    Examples:
        >>> market_info('SHCOMP Index').exch  # doctest: +SKIP
        'EquityChina'
        >>> market_info('SPY US Equity').exch  # doctest: +SKIP
        'EquityUS'
        >>> market_info('ICICIC=1 IS Equity').exch  # doctest: +SKIP
        'EquityFuturesIndia'
        >>> market_info('INT1 Curncy').exch  # doctest: +SKIP
        'CurrencyIndia'
        >>> market_info('CL1 Comdty').exch  # doctest: +SKIP
        'NYME'
        >>> incorrect_tickers = [  # doctest: +SKIP
        ...     'C XX Equity', 'XXX Comdty', 'Bond_ISIN Corp',
        ...     'XYZ Index', 'XYZ Curncy',
        ... ]
        >>> pd.concat([market_info(_) for _ in incorrect_tickers])  # doctest: +SKIP
        Series([], dtype: object)
    """
    t_info = ticker.split()
    exch_only = len(ticker) == 2
    # Allow only supported asset types; special-case certain Corp tickers
    if (not exch_only) and (t_info[-1] not in ['Equity', 'Comdty', 'Curncy', 'Index']):
        # Minimal default for CDX generic CDS tickers (Corp asset)
        # Example: 'CDX IG CDSI GEN 5Y Corp' → use IndexUS session as default hours
        if t_info[-1] == 'Corp' and len(t_info) >= 2 and t_info[0] == 'CDX':
            return pd.Series({'exch': 'IndexUS'})
        return pd.Series(dtype=object)

    a_info = asset_config(asset='Equity' if exch_only else t_info[-1])

    # Handle empty asset config (no config files or cache issues)
    if a_info.empty:
        return pd.Series(dtype=object)

    # =========================================== #
    #           Equity / Equity Futures           #
    # =========================================== #

    if (t_info[-1] == 'Equity') or exch_only:
        is_fut = '==' if '=' in ticker else '!='
        exch_sym = ticker if exch_only else t_info[-2]
        return take_first(
            data=a_info,
            query=f'exch_codes == "{exch_sym}" and is_fut {is_fut} True',
        )

    # ================================================ #
    #           Currency / Commodity / Index           #
    # ================================================ #

    if 'tickers' in a_info.columns and t_info[0] in a_info.tickers.values:
        symbol = t_info[0]
    elif t_info[0][-1].isdigit():
        end_idx = 2 if t_info[-2].isdigit() else 1
        symbol = t_info[0][:-end_idx].strip()
    else:
        symbol = t_info[0].split('+')[0]
    # Special contracts: map any UX* Index form (e.g., UXA, UX1, UXF1UXG1) to UX root
    if (t_info[-1] == 'Index') and symbol.startswith('UX'):
        symbol = 'UX'
    return take_first(data=a_info, query=f'tickers == "{symbol}"')


def take_first(data: pd.DataFrame, query: str) -> pd.Series:
    """Query and take the 1st row of result."""
    if data.empty or (res := data.query(query)).empty:
        return pd.Series(dtype=object)
    return res.reset_index(drop=True).iloc[0]


def asset_config(asset: str) -> pd.DataFrame:
    """Load info for given asset.

    Args:
        asset: asset name

    Returns:
        pd.DataFrame
    """
    cfg_files = param.config_files('assets')
    if not cfg_files:
        return pd.DataFrame()
    cache_cfg = str(Path(const.PKG_PATH) / 'markets' / 'cached' / f'{asset}_cfg.parq')
    if (last_mod := max(map(files.modified_time, cfg_files), default=0)) and \
       files.exists(cache_cfg) and files.modified_time(cache_cfg) > last_mod:
        return pd.read_parquet(cache_cfg)

    if not cfg_files:
        return pd.DataFrame()

    logger.debug('Loading asset config for %s from %s', asset, cfg_files)

    config = (
        pd.concat([
            explode(
                data=pd.DataFrame(list(param.load_yaml(cf).get(asset, []))),
                columns=const.ASSET_INFO[asset],
            )
            for cf in cfg_files
        ], sort=False)
        .drop_duplicates(keep='last')
        .reset_index(drop=True)
    )
    if config.empty:
        return pd.DataFrame()
    files.create_folder(cache_cfg, is_file=True)
    config.to_parquet(cache_cfg)
    return config


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
    # This prevents KeyError when DataFrames are created from malformed YAML entries
    # (e.g., empty dicts like Corp: [{}] which create DataFrames with no columns)
    missing_cols = [col for col in columns if col not in data.columns]
    if missing_cols:
        logger.warning(
            'Missing columns %s in DataFrame for explode. '
            'Available columns: %s. '
            'Returning empty DataFrame. This may indicate malformed config data.',
            missing_cols, list(data.columns)
        )
        return pd.DataFrame()

    if len(columns) == 1:
        return data.explode(column=columns[0])

    return explode(
        data=data.explode(column=columns[-1]),
        columns=columns[:-1],
    )


def ccy_pair(local, base='USD') -> const.CurrencyPair:
    """Currency pair info.

    Args:
        local: local currency
        base: base currency

    Returns:
        CurrencyPair

    Examples:
        >>> ccy_pair(local='HKD', base='USD')
        CurrencyPair(ticker='HKD Curncy', factor=1.0, power=1.0)
        >>> ccy_pair(local='GBp')
        CurrencyPair(ticker='GBP Curncy', factor=100.0, power=-1.0)
        >>> ccy_pair(local='USD', base='GBp')
        CurrencyPair(ticker='GBP Curncy', factor=0.01, power=1.0)
        >>> ccy_pair(local='XYZ', base='USD')  # doctest: +SKIP
        CurrencyPair(ticker='', factor=1.0, power=1.0)
        >>> ccy_pair(local='GBP', base='GBp')
        CurrencyPair(ticker='', factor=0.01, power=1.0)
        >>> ccy_pair(local='GBp', base='GBP')
        CurrencyPair(ticker='', factor=100.0, power=1.0)
    """
    ccy_param = param.load_config(cat='ccy')
    if f'{local}{base}' in ccy_param.index:
        info = ccy_param.loc[f'{local}{base}'].dropna().to_dict()

    elif f'{base}{local}' in ccy_param.index:
        info = ccy_param.loc[f'{base}{local}'].dropna().to_dict()
        info['factor'] = 1. / info.get('factor', 1.)
        info['power'] = -info.get('power', 1.)

    elif base.lower() == local.lower():
        info = {'ticker': ''}
        info['factor'] = 1.
        if base[-1].lower() == base[-1]:
            info['factor'] /= 100.
        if local[-1].lower() == local[-1]:
            info['factor'] *= 100.

    else:
        logger.error('Invalid currency pair configuration: local currency %s, base currency %s', local, base)
        return const.CurrencyPair(ticker='', factor=1., power=1.0)

    info.setdefault('factor', 1.0)
    info.setdefault('power', 1.0)
    return const.CurrencyPair(
        ticker=info.get('ticker', ''),
        factor=float(info['factor']),
        power=float(info['power']),
    )


def convert_session_times_to_utc(
    start_time: str,
    end_time: str,
    exchange_tz: str,
    time_fmt: str = '%Y-%m-%dT%H:%M:%S',
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
    if exchange_tz == 'UTC':
        return start_time, end_time

    start_ts = pd.Timestamp(start_time).tz_localize(exchange_tz).tz_convert('UTC')
    end_ts = pd.Timestamp(end_time).tz_localize(exchange_tz).tz_convert('UTC')
    return start_ts.strftime(time_fmt), end_ts.strftime(time_fmt)


def market_timing(ticker, dt, timing='EOD', tz='local', **kwargs) -> str:
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
    required = {'tz', 'allday', 'day'}
    if not required.issubset(exch.index):
        logger.error('Required exchange information %s not found for ticker: %s', required, ticker)
        return ''

    mkt_time = {'BOD': exch.day[0], 'FINISHED': exch.allday[-1]}.get(timing, exch.day[-1])
    cur_dt = pd.Timestamp(str(dt)).strftime('%Y-%m-%d')
    if tz == 'local':
        return f'{cur_dt} {mkt_time}'
    return timezone.tz_convert(f'{cur_dt} {mkt_time}', to_tz=tz, from_tz=exch.tz)


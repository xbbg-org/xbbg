"""Bloomberg historical data API (BDH).

Provides functions for end-of-day historical data, dividends, earnings, and turnover.
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd

from xbbg import const
from xbbg.api.reference import bds
from xbbg.core import process
from xbbg.core.utils import utils

logger = logging.getLogger(__name__)

__all__ = ['bdh', 'dividend', 'earning', 'turnover', 'abdh']


def bdh(
    tickers: str | list[str],
    flds: str | list[str] | None = None,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp = 'today',
    adjust: str | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg historical data.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields. Defaults to ['Last_Price'].
        start_date: Start date. Defaults to 8 weeks before end_date.
        end_date: End date. Defaults to 'today'.
        adjust: Adjustment type: `all`, `dvd`, `normal`, `abn` (=abnormal), `split`, `-` or None.
            - `-`: No adjustment for dividend or split
            - `dvd` or `normal|abn`: Adjust for all dividends except splits
            - `split`: Adjust for splits and ignore all dividends
            - `all` == `dvd|split`: Adjust for all
            - None: Bloomberg default OR use kwargs
        **kwargs: Additional overrides and infrastructure options.

    Returns:
        pd.DataFrame: Historical data with MultiIndex columns (ticker, field) and dates as index.
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, historical_pipeline_config

    # Normalize tickers to list
    ticker_list = utils.normalize_tickers(tickers)
    primary_ticker = str(ticker_list[0] if ticker_list else tickers)

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request - use first ticker as primary, store all in request_opts
    if flds is None:
        flds = ['Last_Price']

    e_dt = utils.fmt_dt(end_date, fmt='%Y%m%d')
    if start_date is None:
        start_date = pd.Timestamp(e_dt) - pd.Timedelta(weeks=8)
    s_dt = utils.fmt_dt(start_date, fmt='%Y%m%d')

    request = (
        RequestBuilder()
        .ticker(primary_ticker)
        .date(end_date)  # Use end_date as primary date
        .context(split.infra)
        .cache_policy(enabled=split.infra.cache, reload=split.infra.reload)
        .request_opts(
            tickers=ticker_list,
            flds=flds,
            start_date=s_dt,
            end_date=e_dt,
            adjust=adjust,
        )
        .override_kwargs(**split.override_like)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=historical_pipeline_config())
    return pipeline.run(request)


def earning(
    ticker: str,
    by: str = 'Geo',
    typ: str = 'Revenue',
    ccy: str | None = None,
    level: int | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Earning exposures by Geo or Products.

    Args:
        ticker: ticker name
        by: [G(eo), P(roduct)]
        typ: type of earning, start with `PG_` in Bloomberg FLDS - default `Revenue`
            `Revenue` - Revenue of the company
            `Operating_Income` - Operating Income (also named as EBIT) of the company
            `Assets` - Assets of the company
            `Gross_Profit` - Gross profit of the company
            `Capital_Expenditures` - Capital expenditures of the company
        ccy: currency of earnings
        level: hierarchy level of earnings
        **kwargs: Additional overrides such as fiscal year and periods.

    Returns:
        pd.DataFrame.
    """
    kwargs.pop('raw', None)
    ovrd = 'G' if by[0].upper() == 'G' else 'P'
    new_kw = {'Product_Geo_Override': ovrd}

    year = kwargs.pop('year', None)
    periods = kwargs.pop('periods', None)
    if year: kwargs['Eqy_Fund_Year'] = year
    if periods: kwargs['Number_Of_Periods'] = periods

    header = bds(tickers=ticker, flds='PG_Bulk_Header', use_port=False, **new_kw, **kwargs)
    if ccy: kwargs['Eqy_Fund_Crncy'] = ccy
    if level: kwargs['PG_Hierarchy_Level'] = level
    data = bds(tickers=ticker, flds=f'PG_{typ}', use_port=False, **new_kw, **kwargs)

    if data.empty or header.empty: return pd.DataFrame()
    if data.shape[1] != header.shape[1]:
        raise ValueError('Inconsistent shape of data and header')
    data.columns = (
        header.iloc[0]
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('_20', '20')
        .tolist()
    )

    if 'level' not in data: raise KeyError('Cannot find [level] in data')
    for yr in data.columns[data.columns.str.startswith('fy')]:
        process.earning_pct(data=data, yr=yr)

    return data


def dividend(
    tickers: str | list[str],
    typ: str = 'all',
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg dividend / split history.

    Args:
        tickers: list of tickers
        typ: dividend adjustment type
            `all`:       `DVD_Hist_All`
            `dvd`:       `DVD_Hist`
            `split`:     `Eqy_DVD_Hist_Splits`
            `gross`:     `Eqy_DVD_Hist_Gross`
            `adjust`:    `Eqy_DVD_Adjust_Fact`
            `adj_fund`:  `Eqy_DVD_Adj_Fund`
            `with_amt`:  `DVD_Hist_All_with_Amt_Status`
            `dvd_amt`:   `DVD_Hist_with_Amt_Status`
            `gross_amt`: `DVD_Hist_Gross_with_Amt_Stat`
            `projected`: `BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann`
        start_date: start date
        end_date: end date
        **kwargs: overrides

    Returns:
        pd.DataFrame
    """
    kwargs.pop('raw', None)
    tickers = utils.normalize_tickers(tickers)
    tickers = [t for t in tickers if ('Equity' in t) and ('=' not in t)]

    fld = const.DVD_TPYES.get(typ, typ)

    if (fld == 'Eqy_DVD_Adjust_Fact') and ('Corporate_Actions_Filter' not in kwargs):
        kwargs['Corporate_Actions_Filter'] = 'NORMAL_CASH|ABNORMAL_CASH|CAPITAL_CHANGE'

    if start_date:
        kwargs['DVD_Start_Dt'] = utils.fmt_dt(start_date, fmt='%Y%m%d')
    if end_date:
        kwargs['DVD_End_Dt'] = utils.fmt_dt(end_date, fmt='%Y%m%d')

    return bds(tickers=tickers, flds=fld, col_maps=const.DVD_COLS, **kwargs)


def turnover(
    tickers: str | list[str],
    flds: str = 'Turnover',
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    ccy: str = 'USD',
    factor: float = 1e6,
) -> pd.DataFrame:
    """Currency adjusted turnover (in million).

    Args:
        tickers: ticker or list of tickers.
        flds: override ``flds``.
        start_date: start date, default 1 month prior to ``end_date``.
        end_date: end date, default T - 1.
        ccy: currency - 'USD' (default), any currency, or 'local' (no adjustment).
        factor: adjustment factor, default 1e6 - return values in millions.

    Returns:
        pd.DataFrame.
    """
    if end_date is None:
        end_date = pd.bdate_range(end='today', periods=2)[0]
    if start_date is None:
        start_date = pd.bdate_range(end=end_date, periods=2, freq='M')[0]
    tickers = utils.normalize_tickers(tickers)

    data = bdh(tickers=tickers, flds=flds, start_date=start_date, end_date=end_date)
    cols = data.columns.get_level_values(level=0).unique()
    use_volume = pd.DataFrame()
    if isinstance(flds, str) and (flds.lower() == 'turnover'):
        vol_tcks = [t for t in tickers if t not in cols]
        if vol_tcks:
            vol_data = bdh(
                tickers=vol_tcks,
                flds=['eqy_weighted_avg_px', 'volume'],
                start_date=start_date,
                end_date=end_date,
            )
            if not vol_data.empty:
                # Calculate turnover = volume * VWAP
                use_volume = vol_data.xs('eqy_weighted_avg_px', axis=1, level=1) * \
                           vol_data.xs('volume', axis=1, level=1)

    if data.empty and use_volume.empty: return pd.DataFrame()
    from xbbg.api.helpers import adjust_ccy  # noqa: PLC0415
    return pd.concat([adjust_ccy(data=data, ccy=ccy).div(factor), use_volume], axis=1)


async def abdh(
    tickers: str | list[str],
    flds: str | list[str] | None = None,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp = 'today',
    adjust: str | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg historical data.

    Non-blocking async version of `bdh()`. Use this in async contexts to avoid
    blocking the event loop.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields. Defaults to ['Last_Price'].
        start_date: Start date. Defaults to 8 weeks before end_date.
        end_date: End date. Defaults to 'today'.
        adjust: Adjustment type: `all`, `dvd`, `normal`, `abn` (=abnormal), `split`, `-` or None.
            - `-`: No adjustment for dividend or split
            - `dvd` or `normal|abn`: Adjust for all dividends except splits
            - `split`: Adjust for splits and ignore all dividends
            - `all` == `dvd|split`: Adjust for all
            - None: Bloomberg default OR use kwargs
        **kwargs: Additional overrides and infrastructure options.

    Returns:
        pd.DataFrame: Historical data with MultiIndex columns (ticker, field) and dates as index.

    Examples:
        >>> import asyncio
        >>> # Single request
        >>> # df = await blp.abdh('AAPL US Equity', start_date='2024-01-01')
        >>>
        >>> # Concurrent requests for multiple tickers
        >>> # results = await asyncio.gather(
        >>> #     blp.abdh('AAPL US Equity', start_date='2024-01-01'),
        >>> #     blp.abdh('MSFT US Equity', start_date='2024-01-01'),
        >>> # )
    """
    return await asyncio.to_thread(
        bdh,
        tickers=tickers,
        flds=flds,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        **kwargs,
    )


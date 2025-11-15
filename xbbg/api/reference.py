"""Bloomberg reference data API (BDP/BDS).

Provides functions for single point-in-time reference data (BDP) and
bulk/block data (BDS) queries.
"""

from __future__ import annotations

from functools import partial
import logging

import pandas as pd

from xbbg.core import conn, helpers, process
from xbbg.io import files, storage
from xbbg.utils import pipeline

logger = logging.getLogger(__name__)

__all__ = ['bdp', 'bds']


def bdp(
    tickers: str | list[str],
    flds: str | list[str],
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg reference data.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        **kwargs: Bloomberg overrides.

    Returns:
        pd.DataFrame: Reference data with tickers as index and fields as columns.
    """
    tickers = helpers.normalize_tickers(tickers)
    flds = helpers.normalize_flds(flds)

    request = process.create_request(
        service='//blp/refdata',
        request='ReferenceDataRequest',
        **kwargs,
    )
    process.init_request(request=request, tickers=tickers, flds=flds, **kwargs)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Sending Bloomberg reference data request for %d ticker(s), %d field(s)', len(tickers), len(flds))
    handle = conn.send_request(request=request, service='//blp/refdata', **kwargs)

    res = pd.DataFrame(process.rec_events(func=process.process_ref, event_queue=handle["event_queue"], **kwargs))
    if kwargs.get('raw', False): return res
    if helpers.check_empty_result(res, ['ticker', 'field']):
        return pd.DataFrame()

    return (
        res
        .set_index(['ticker', 'field'])
        .unstack(level=1)
        .rename_axis(index=None, columns=[None, None])
        .droplevel(axis=1, level=0)
        .loc[:, res.field.unique()]
        .pipe(pipeline.standard_cols, col_maps=kwargs.get('col_maps'))
    )


def bds(
    tickers: str | list[str],
    flds: str,
    use_port: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg block data.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Field name.
        use_port: Whether to use `PortfolioDataRequest` instead of `ReferenceDataRequest`.
        **kwargs: Other overrides for query.

    Returns:
        pd.DataFrame: Block data with multi-row results per ticker.
    """
    part = partial(_bds_, fld=flds, logger=logger, use_port=use_port, **kwargs)
    tickers = helpers.normalize_tickers(tickers)
    return pd.DataFrame(pd.concat(map(part, tickers), sort=False))


def _bds_(
    ticker: str,
    fld: str,
    logger: logging.Logger,
    use_port: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Get BDS data for a single ticker."""
    if 'has_date' not in kwargs: kwargs['has_date'] = True
    data_file = storage.ref_file(ticker=ticker, fld=fld, ext='pkl', **kwargs)
    if files.exists(data_file):
        logger.debug('Loading cached Bloomberg reference data from: %s', data_file)
        return pd.DataFrame(pd.read_pickle(data_file))

    request = process.create_request(
        service='//blp/refdata',
        request='PortfolioDataRequest' if use_port else 'ReferenceDataRequest',
        **kwargs,
    )
    process.init_request(request=request, tickers=ticker, flds=fld, **kwargs)
    logger.debug('Sending Bloomberg reference data request for ticker: %s, field: %s', ticker, fld)
    handle = conn.send_request(request=request, service='//blp/refdata', **kwargs)

    res = pd.DataFrame(process.rec_events(func=process.process_ref, event_queue=handle["event_queue"], **kwargs))
    if kwargs.get('raw', False): return res
    if helpers.check_empty_result(res, ['ticker', 'field']):
        return pd.DataFrame()

    data = (
        res
        .set_index(['ticker', 'field'])
        .droplevel(axis=0, level=1)
        .rename_axis(index=None)
        .pipe(pipeline.standard_cols, col_maps=kwargs.get('col_maps'))
    )
    if data_file:
        logger.debug('Saving Bloomberg reference data to cache: %s', data_file)
        files.create_folder(data_file, is_file=True)
        data.to_pickle(data_file)

    return data


"""Cache helpers for BDP/BDS queries.

Provides utilities to identify which ticker/field pairs are already cached
on disk and which remain to be queried.
"""

from collections import namedtuple
from itertools import product
import logging

import pandas as pd

from xbbg.core import utils
from xbbg.io import files, storage

logger = logging.getLogger(__name__)

ToQuery = namedtuple('ToQuery', ['tickers', 'flds', 'cached_data'])
EXC_COLS = ['tickers', 'flds', 'raw', 'log', 'col_maps']


def bdp_bds_cache(func, tickers, flds, **kwargs) -> ToQuery:
    """Find cached ``BDP``/``BDS`` queries.

    Args:
        func: Function name, either ``bdp`` or ``bds``.
        tickers: One or more tickers.
        flds: One or more fields.
        **kwargs: Additional options forwarded to storage helpers.

    Returns:
        ToQuery: Tickers and fields still to query, and any cached data.
    """
    cache_data = []
    # Logger is module-level
    kwargs['has_date'] = kwargs.pop('has_date', func == 'bds')
    kwargs['cache'] = kwargs.get('cache', True)

    tickers = utils.flatten(tickers)
    flds = utils.flatten(flds)
    loaded = pd.DataFrame(data=0, index=tickers, columns=flds)

    for ticker, fld in product(tickers, flds):
        data_file = storage.ref_file(
            ticker=ticker, fld=fld, ext='pkl', **{
                k: v for k, v in kwargs.items() if k not in EXC_COLS
            }
        )
        if not files.exists(data_file): continue
        # Guard logging in loop - only log if DEBUG enabled
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('Reading cached data from file: %s', data_file)
        cache_data.append(pd.read_pickle(data_file))
        loaded.loc[ticker, fld] = 1

    to_qry = loaded.where(loaded == 0)\
        .dropna(how='all', axis=1).dropna(how='all', axis=0)

    # Log cache statistics only if DEBUG enabled (aggregate, not per-item)
    if logger.isEnabledFor(logging.DEBUG):
        cached_count = loaded.sum().sum()
        total_count = len(tickers) * len(flds)
        if cached_count > 0:
            logger.debug('Cache hit: %d/%d ticker-field combinations found in cache', cached_count, total_count)
        if not to_qry.empty:
            to_query_count = to_qry.notna().sum().sum()
            logger.debug('Cache miss: %d ticker-field combinations need to be queried', to_query_count)

    return ToQuery(
        tickers=to_qry.index.tolist(), flds=to_qry.columns.tolist(),
        cached_data=cache_data
    )

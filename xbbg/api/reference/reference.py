"""Bloomberg reference data API (BDP/BDS).

Provides functions for single point-in-time reference data (BDP) and
bulk/block data (BDS) queries.
"""

from __future__ import annotations

import logging

import pandas as pd

from xbbg.core import process
from xbbg.core.infra import conn
from xbbg.core.utils import utils
from xbbg.io import cache, files
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
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        pd.DataFrame: Reference data with tickers as index and fields as columns.
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, reference_pipeline_config

    # Normalize tickers to list
    ticker_list = utils.normalize_tickers(tickers)
    primary_ticker = ticker_list[0] if ticker_list else tickers
    fld_list = utils.normalize_flds(flds)

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request
    request = (
        RequestBuilder()
        .ticker(primary_ticker)
        .date('today')  # Reference data doesn't use dates, but DataRequest requires one
        .context(split.infra)
        .cache_policy(enabled=split.infra.cache, reload=split.infra.reload)
        .request_opts(tickers=ticker_list, flds=fld_list)
        .override_kwargs(**split.override_like)
        .build()
    )

    # Run pipeline
    pipeline = BloombergPipeline(config=reference_pipeline_config())
    return pipeline.run(request)


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
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline import BloombergPipeline, RequestBuilder, block_data_pipeline_config

    # Split kwargs
    split = split_kwargs(**kwargs)
    ticker_list = utils.normalize_tickers(tickers)

    # Process each ticker using pipeline
    def _process_ticker(ticker: str) -> pd.DataFrame:
        request = (
            RequestBuilder()
            .ticker(ticker)
            .date('today')
            .context(split.infra)
            .cache_policy(enabled=split.infra.cache, reload=split.infra.reload)
            .request_opts(fld=flds, use_port=use_port)
            .override_kwargs(**split.override_like)
            .build()
        )

        pipeline = BloombergPipeline(config=block_data_pipeline_config())
        return pipeline.run(request)

    results = [_process_ticker(t) for t in ticker_list]
    return pd.DataFrame(pd.concat(results, sort=False))


def _bds_(
    ticker: str,
    fld: str,
    logger: logging.Logger,
    use_port: bool = False,
    ctx=None,
    **kwargs,
) -> pd.DataFrame:
    """Get BDS data for a single ticker.

    Args:
        ticker: Ticker symbol.
        fld: Field name.
        logger: Logger instance.
        use_port: Whether to use PortfolioDataRequest.
        ctx: Bloomberg context (infrastructure kwargs only).
        **kwargs: Legacy kwargs support (includes overrides for request building).

    Returns:
        BDS data DataFrame.
    """
    from xbbg.core.domain.context import split_kwargs

    # Extract context - prefer explicit ctx, otherwise extract from kwargs
    if ctx is None:
        split = split_kwargs(**kwargs)
        ctx = split.infra
        override_kwargs = split.override_like
        all_kwargs = {**ctx.to_kwargs(), **override_kwargs}
    else:
        # ctx provided, but kwargs may still contain overrides
        split = split_kwargs(**kwargs)
        override_kwargs = split.override_like
        all_kwargs = {**ctx.to_kwargs(), **override_kwargs}

    # Set has_date if not already set (BDS typically needs date context)
    if 'has_date' not in all_kwargs:
        all_kwargs['has_date'] = True
    data_file = cache.ref_file(ticker=ticker, fld=fld, ext='pkl', **ctx.to_kwargs())
    if files.exists(data_file):
        logger.debug('Loading cached Bloomberg reference data from: %s', data_file)
        return pd.DataFrame(pd.read_pickle(data_file))

    request = process.create_request(
        service='//blp/refdata',
        request='PortfolioDataRequest' if use_port else 'ReferenceDataRequest',
        **all_kwargs,
    )
    process.init_request(request=request, tickers=ticker, flds=fld, **all_kwargs)
    logger.debug('Sending Bloomberg reference data request for ticker: %s, field: %s', ticker, fld)
    handle = conn.send_request(request=request, service='//blp/refdata', **ctx.to_kwargs())

    res = pd.DataFrame(process.rec_events(func=process.process_ref, event_queue=handle["event_queue"], **ctx.to_kwargs()))
    if ctx.raw: return res
    if utils.check_empty_result(res, ['ticker', 'field']):
        return pd.DataFrame()

    data = (
        res
        .set_index(['ticker', 'field'])
        .droplevel(axis=0, level=1)
        .rename_axis(index=None)
        .pipe(pipeline.standard_cols, col_maps=ctx.col_maps)
    )
    if data_file:
        logger.debug('Saving Bloomberg reference data to cache: %s', data_file)
        files.create_folder(data_file, is_file=True)
        data.to_pickle(data_file)

    return data


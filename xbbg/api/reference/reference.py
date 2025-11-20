"""Bloomberg reference data API (BDP/BDS).

Provides functions for single point-in-time reference data (BDP) and
bulk/block data (BDS) queries.
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd

from xbbg.core.utils import utils

logger = logging.getLogger(__name__)

__all__ = ['bdp', 'bds', 'abdp', 'abds']


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
    # Ensure primary_ticker is always a string (use first ticker or convert single string)
    primary_ticker = ticker_list[0] if ticker_list else (tickers if isinstance(tickers, str) else '')
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


async def abdp(
    tickers: str | list[str],
    flds: str | list[str],
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg reference data.

    Non-blocking async version of `bdp()`. Use this in async contexts to avoid
    blocking the event loop.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        pd.DataFrame: Reference data with tickers as index and fields as columns.

    Examples:
        >>> import asyncio
        >>> # Single request
        >>> # df = await blp.abdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
        >>>
        >>> # Concurrent requests
        >>> # results = await asyncio.gather(
        >>> #     blp.abdp('AAPL US Equity', ['PX_LAST']),
        >>> #     blp.abdp('MSFT US Equity', ['PX_LAST']),
        >>> # )
    """
    return await asyncio.to_thread(bdp, tickers=tickers, flds=flds, **kwargs)


async def abds(
    tickers: str | list[str],
    flds: str,
    use_port: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg block data.

    Non-blocking async version of `bds()`. Use this in async contexts to avoid
    blocking the event loop.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Field name.
        use_port: Whether to use `PortfolioDataRequest` instead of `ReferenceDataRequest`.
        **kwargs: Other overrides for query.

    Returns:
        pd.DataFrame: Block data with multi-row results per ticker.

    Examples:
        >>> import asyncio
        >>> # Single request
        >>> # df = await blp.abds('AAPL US Equity', 'DVD_Hist_All')
        >>>
        >>> # Concurrent requests
        >>> # results = await asyncio.gather(
        >>> #     blp.abds('AAPL US Equity', 'DVD_Hist_All'),
        >>> #     blp.abds('MSFT US Equity', 'DVD_Hist_All'),
        >>> # )
    """
    return await asyncio.to_thread(bds, tickers=tickers, flds=flds, use_port=use_port, **kwargs)


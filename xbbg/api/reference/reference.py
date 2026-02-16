"""Bloomberg reference data API (BDP/BDS).

Provides functions for single point-in-time reference data (BDP) and
bulk/block data (BDS) queries. Async versions are the source of truth;
sync versions are generated via sync_api().
"""

from __future__ import annotations

import logging

import pandas as pd

from xbbg.backend import Backend, Format
from xbbg.core.infra.conn import sync_api
from xbbg.core.utils import utils

logger = logging.getLogger(__name__)

__all__ = ["bdp", "bds", "abdp", "abds"]


async def abdp(
    tickers: str | list[str],
    flds: str | list[str],
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg reference data (source of truth).

    Truly non-blocking -- uses async event polling via arequest().
    Use ``bdp()`` for synchronous usage.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        pd.DataFrame: Reference data with tickers as index and fields as columns.

    Examples:
        >>> import asyncio
        >>> # Single request
        >>> # df = await blp.abdp('AAPL US Equity', ['PX_LAST', 'VOLUME'])
        >>>
        >>> # Concurrent requests (true async -- single thread, cooperative polling)
        >>> # results = await asyncio.gather(
        >>> #     blp.abdp('AAPL US Equity', ['PX_LAST']),
        >>> #     blp.abdp('MSFT US Equity', ['PX_LAST']),
        >>> # )
    """
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import reference_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

    # Normalize tickers to list
    ticker_list = utils.normalize_tickers(tickers)
    # Ensure primary_ticker is always a string (use first ticker or convert single string)
    primary_ticker = ticker_list[0] if ticker_list else (tickers if isinstance(tickers, str) else "")
    fld_list = utils.normalize_flds(flds)

    # Split kwargs
    split = split_kwargs(**kwargs)

    # Build request
    request = (
        RequestBuilder()
        .ticker(primary_ticker)
        .date("today")  # Reference data doesn't use dates, but DataRequest requires one
        .context(split.infra)
        .cache_policy(enabled=split.infra.cache, reload=split.infra.reload)
        .request_opts(tickers=ticker_list, flds=fld_list)
        .override_kwargs(**split.override_like)
        .with_output(backend, format)
        .build()
    )

    # Run pipeline (async)
    pipeline = BloombergPipeline(config=reference_pipeline_config())
    return await pipeline.arun(request)


bdp = sync_api(abdp)


async def abds(
    tickers: str | list[str],
    flds: str,
    use_port: bool = False,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg block data (source of truth).

    Truly non-blocking -- uses async event polling via arequest().
    Use ``bds()`` for synchronous usage.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Field name.
        use_port: Whether to use `PortfolioDataRequest` instead of `ReferenceDataRequest`.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
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
    from xbbg.core.domain.context import split_kwargs
    from xbbg.core.pipeline_core import BloombergPipeline
    from xbbg.core.pipeline_factories import block_data_pipeline_config
    from xbbg.core.request_builder import RequestBuilder

    # Split kwargs
    split = split_kwargs(**kwargs)
    ticker_list = utils.normalize_tickers(tickers)

    # Process each ticker using pipeline (async)
    async def _process_ticker(ticker: str):
        request = (
            RequestBuilder()
            .ticker(ticker)
            .date("today")
            .context(split.infra)
            .cache_policy(enabled=split.infra.cache, reload=split.infra.reload)
            .request_opts(fld=flds, use_port=use_port)
            .override_kwargs(**split.override_like)
            .with_output(backend, format)
            .build()
        )

        pipeline = BloombergPipeline(config=block_data_pipeline_config())
        return await pipeline.arun(request)

    results = []
    for t in ticker_list:
        results.append(await _process_ticker(t))

    # Use backend-agnostic concat
    from xbbg.io.convert import concat_frames

    return concat_frames(results, backend)


bds = sync_api(abds)

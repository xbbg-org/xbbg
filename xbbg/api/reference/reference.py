"""Bloomberg reference data API (BDP/BDS).

Provides functions for single point-in-time reference data (BDP) and
bulk/block data (BDS) queries.
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd

from xbbg.backend import Backend, Format
from xbbg.core.utils import utils

logger = logging.getLogger(__name__)

__all__ = ["bdp", "bds", "abdp", "abds"]


def bdp(
    tickers: str | list[str],
    flds: str | list[str],
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg reference data.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Single field or list of fields to query.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Bloomberg overrides and infrastructure options.

    Returns:
        pd.DataFrame: Reference data with tickers as index and fields as columns.
    """
    from xbbg.core.request import request
    from xbbg.core.pipeline import reference_pipeline_config

    return request(
        config=reference_pipeline_config, tickers=tickers, fields=flds, backend=backend, format=format, **kwargs
    )


def bds(
    tickers: str | list[str],
    flds: str,
    use_port: bool = False,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg block data.

    Args:
        tickers: Single ticker or list of tickers.
        flds: Field name.
        use_port: Whether to use `PortfolioDataRequest` instead of `ReferenceDataRequest`.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Other overrides for query.

    Returns:
        pd.DataFrame: Block data with multi-row results per ticker.
    """
    from xbbg.core.request import request
    from xbbg.core.pipeline import block_data_pipeline_config

    return request(
        config=block_data_pipeline_config,
        tickers=tickers,
        fields=flds,
        fields_key="fld",
        per_ticker=True,
        request_opts={"use_port": use_port},
        backend=backend,
        format=format,
        **kwargs,
    )


async def abdp(
    tickers: str | list[str],
    flds: str | list[str],
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg reference data.

    Non-blocking async version of `bdp()`. Use this in async contexts to avoid
    blocking the event loop.

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
        >>> # Concurrent requests
        >>> # results = await asyncio.gather(
        >>> #     blp.abdp('AAPL US Equity', ['PX_LAST']),
        >>> #     blp.abdp('MSFT US Equity', ['PX_LAST']),
        >>> # )
    """
    from xbbg.core.request import arequest
    from xbbg.core.pipeline import reference_pipeline_config

    return await arequest(
        config=reference_pipeline_config, tickers=tickers, fields=flds, backend=backend, format=format, **kwargs
    )


async def abds(
    tickers: str | list[str],
    flds: str,
    use_port: bool = False,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Async Bloomberg block data.

    Non-blocking async version of `bds()`. Use this in async contexts to avoid
    blocking the event loop.

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
    from xbbg.core.request import arequest
    from xbbg.core.pipeline import block_data_pipeline_config

    return await arequest(
        config=block_data_pipeline_config,
        tickers=tickers,
        fields=flds,
        fields_key="fld",
        per_ticker=True,
        request_opts={"use_port": use_port},
        backend=backend,
        format=format,
        **kwargs,
    )

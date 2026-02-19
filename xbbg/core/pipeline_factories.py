"""Pipeline configuration factories.

Uses a table-driven registry pattern to eliminate code duplication.
All 9 pipeline configurations are defined in _PIPELINE_REGISTRY,
with backward-compatible wrapper functions for existing callers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from xbbg.core import process
from xbbg.core.pipeline_core import PipelineConfig
from xbbg.core.strategies import (
    BeqsRequestBuilder,
    BeqsTransformer,
    BlockDataRequestBuilder,
    BlockDataTransformer,
    BqlRequestBuilder,
    BqlTransformer,
    BqrRequestBuilder,
    BqrTransformer,
    BsrchRequestBuilder,
    BsrchTransformer,
    BtaRequestBuilder,
    BtaTransformer,
    HistoricalRequestBuilder,
    HistoricalTransformer,
    IntradayRequestBuilder,
    IntradayTransformer,
    ReferenceRequestBuilder,
    ReferenceTransformer,
)


def _get_intraday_resolvers() -> Callable[[], Any]:
    """Lazy import for intraday-specific resolver chain."""
    from xbbg.markets.resolver_chain import create_default_resolver_chain

    return create_default_resolver_chain


def _get_intraday_cache_adapter() -> Callable[[], Any]:
    """Lazy import for intraday-specific cache adapter."""
    from xbbg.io.cache import BarCacheAdapter

    return BarCacheAdapter


# Table-driven registry: name -> (service, request_type, process_func, builder, transformer, config_dict)
_PIPELINE_REGISTRY: dict[str, tuple[str, str, Any, Any, Any, dict[str, Any]]] = {
    "reference": (
        "//blp/refdata",
        "ReferenceDataRequest",
        process.process_ref,
        ReferenceRequestBuilder(),
        ReferenceTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "historical": (
        "//blp/refdata",
        "HistoricalDataRequest",
        process.process_hist,
        HistoricalRequestBuilder(),
        HistoricalTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "intraday": (
        "//blp/refdata",
        "IntradayBarRequest",
        process.process_bar,
        IntradayRequestBuilder(),
        IntradayTransformer(),
        {
            "needs_session": True,
            "default_resolvers": _get_intraday_resolvers(),
            "default_cache_adapter": _get_intraday_cache_adapter(),
        },
    ),
    "block_data": (
        "//blp/refdata",
        "ReferenceDataRequest",
        process.process_ref,
        BlockDataRequestBuilder(),
        BlockDataTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "beqs": (
        "//blp/refdata",
        "BeqsRequest",
        process.process_ref,
        BeqsRequestBuilder(),
        BeqsTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "bsrch": (
        "//blp/exrsvc",
        "ExcelGetGridRequest",
        process.process_bsrch,
        BsrchRequestBuilder(),
        BsrchTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "bql": (
        "//blp/bqlsvc",
        "sendQuery",
        process.process_bql,
        BqlRequestBuilder(),
        BqlTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "bta": (
        "//blp/tasvc",
        "studyRequest",
        process.process_tasvc,
        BtaRequestBuilder(),
        BtaTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
    "bqr": (
        "//blp/refdata",
        "IntradayTickRequest",
        process.process_bqr,
        BqrRequestBuilder(),
        BqrTransformer(),
        {"needs_session": False, "default_resolvers": list},
    ),
}


def get_pipeline_config(name: str) -> PipelineConfig:
    """Generate pipeline config from registry.

    Args:
        name: Pipeline name (e.g., 'reference', 'historical', 'intraday').

    Returns:
        PipelineConfig instance.

    Raises:
        KeyError: If pipeline name not found in registry.
    """
    if name not in _PIPELINE_REGISTRY:
        available = ", ".join(sorted(_PIPELINE_REGISTRY.keys()))
        raise KeyError(f"Unknown pipeline: {name!r}. Available: {available}")

    service, request_type, process_func, builder, transformer, config_dict = _PIPELINE_REGISTRY[name]

    return PipelineConfig(
        service=service,
        request_type=request_type,
        process_func=process_func,
        request_builder=builder,
        transformer=transformer,
        **config_dict,
    )


# Backward-compatible wrapper functions
def reference_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg reference data (BDP)."""
    return get_pipeline_config("reference")


def historical_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg historical data (BDH)."""
    return get_pipeline_config("historical")


def intraday_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg intraday bar data (BDIB)."""
    return get_pipeline_config("intraday")


def block_data_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg block data (BDS)."""
    return get_pipeline_config("block_data")


def beqs_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Equity Screening (BEQS)."""
    return get_pipeline_config("beqs")


def bsrch_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg SRCH (Search) queries."""
    return get_pipeline_config("bsrch")


def bql_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Query Language (BQL)."""
    return get_pipeline_config("bql")


def bta_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Technical Analysis (TASVC)."""
    return get_pipeline_config("bta")


def bqr_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Quote Request (BQR).

    BQR emulates the Excel =BQR() function for retrieving dealer quote data
    using IntradayTickRequest with BID/ASK events and broker codes.
    """
    return get_pipeline_config("bqr")

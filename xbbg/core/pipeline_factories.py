"""Pipeline configuration factories."""

from __future__ import annotations

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


def reference_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg reference data (BDP)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="ReferenceDataRequest",
        process_func=process.process_ref,
        request_builder=ReferenceRequestBuilder(),
        transformer=ReferenceTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def historical_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg historical data (BDH)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="HistoricalDataRequest",
        process_func=process.process_hist,
        request_builder=HistoricalRequestBuilder(),
        transformer=HistoricalTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def intraday_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg intraday bar data (BDIB)."""
    from xbbg.io.cache import BarCacheAdapter
    from xbbg.markets.resolver_chain import create_default_resolver_chain

    return PipelineConfig(
        service="//blp/refdata",
        request_type="IntradayBarRequest",
        process_func=process.process_bar,
        request_builder=IntradayRequestBuilder(),
        transformer=IntradayTransformer(),
        needs_session=True,
        default_resolvers=create_default_resolver_chain,
        default_cache_adapter=BarCacheAdapter,
    )


def block_data_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg block data (BDS)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="ReferenceDataRequest",
        process_func=process.process_ref,
        request_builder=BlockDataRequestBuilder(),
        transformer=BlockDataTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def beqs_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Equity Screening (BEQS)."""
    return PipelineConfig(
        service="//blp/refdata",
        request_type="BeqsRequest",
        process_func=process.process_ref,
        request_builder=BeqsRequestBuilder(),
        transformer=BeqsTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def bsrch_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg SRCH (Search) queries."""
    return PipelineConfig(
        service="//blp/exrsvc",
        request_type="ExcelGetGridRequest",
        process_func=process.process_bsrch,
        request_builder=BsrchRequestBuilder(),
        transformer=BsrchTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def bql_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Query Language (BQL)."""
    return PipelineConfig(
        service="//blp/bqlsvc",
        request_type="sendQuery",
        process_func=process.process_bql,
        request_builder=BqlRequestBuilder(),
        transformer=BqlTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def bta_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Technical Analysis (TASVC)."""
    return PipelineConfig(
        service="//blp/tasvc",
        request_type="studyRequest",
        process_func=process.process_tasvc,
        request_builder=BtaRequestBuilder(),
        transformer=BtaTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )


def bqr_pipeline_config() -> PipelineConfig:
    """Create pipeline config for Bloomberg Quote Request (BQR).

    BQR emulates the Excel =BQR() function for retrieving dealer quote data
    using IntradayTickRequest with BID/ASK events and broker codes.
    """
    return PipelineConfig(
        service="//blp/refdata",
        request_type="IntradayTickRequest",
        process_func=process.process_bqr,
        request_builder=BqrRequestBuilder(),
        transformer=BqrTransformer(),
        needs_session=False,
        default_resolvers=lambda: [],
    )

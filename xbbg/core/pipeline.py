"""Backward-compatible re-exports.

All classes and functions have moved to focused modules:
- Pipeline core: xbbg.core.pipeline_core
- Request builder: xbbg.core.request_builder
- Strategies: xbbg.core.strategies.*
- Factory functions: xbbg.core.pipeline_factories
"""

from __future__ import annotations

from xbbg.core.pipeline_core import (
    BloombergPipeline,
    PipelineConfig,
    RequestBuilderStrategy,
    ResponseTransformerStrategy,
)
from xbbg.core.pipeline_factories import (
    beqs_pipeline_config,
    block_data_pipeline_config,
    bql_pipeline_config,
    bqr_pipeline_config,
    bsrch_pipeline_config,
    bta_pipeline_config,
    historical_pipeline_config,
    intraday_pipeline_config,
    reference_pipeline_config,
)
from xbbg.core.request_builder import RequestBuilder
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

__all__ = [
    "BeqsRequestBuilder",
    "BeqsTransformer",
    "BlockDataRequestBuilder",
    "BlockDataTransformer",
    "BloombergPipeline",
    "BqlRequestBuilder",
    "BqlTransformer",
    "BqrRequestBuilder",
    "BqrTransformer",
    "BsrchRequestBuilder",
    "BsrchTransformer",
    "BtaRequestBuilder",
    "BtaTransformer",
    "HistoricalRequestBuilder",
    "HistoricalTransformer",
    "IntradayRequestBuilder",
    "IntradayTransformer",
    "PipelineConfig",
    "ReferenceRequestBuilder",
    "ReferenceTransformer",
    "RequestBuilder",
    "RequestBuilderStrategy",
    "ResponseTransformerStrategy",
    "block_data_pipeline_config",
    "bql_pipeline_config",
    "bqr_pipeline_config",
    "bsrch_pipeline_config",
    "bta_pipeline_config",
    "beqs_pipeline_config",
    "historical_pipeline_config",
    "intraday_pipeline_config",
    "reference_pipeline_config",
]

"""Core Bloomberg API processing and connection utilities.

This package contains internal core functionality organized into subpackages:
- utils: Supporting utilities (utils, timezone)
- config: Bloomberg API configuration (overrides, intervals)
- domain: Domain model & contracts (contracts, context)
- infra: Infrastructure layer (conn, blpapi_logging)
- process: Request creation and message processing
- pipeline: Unified data pipeline
"""

# Import subpackages to make them accessible as attributes (needed for mocking in tests)
from xbbg.core import config, domain, infra, pipeline, process, utils as core_utils

# Re-export commonly used modules for backward compatibility
from xbbg.core.config import intervals, overrides
from xbbg.core.domain import context, contracts
from xbbg.core.infra import blpapi_logging, conn
from xbbg.core.utils import timezone, utils

# Make utils subpackage accessible as xbbg.core.utils
utils = core_utils  # noqa: F811 - intentional reassignment for backward compat

__all__ = [
    "process",
    "pipeline",
    "intervals",
    "overrides",
    "context",
    "contracts",
    "blpapi_logging",
    "conn",
    "timezone",
    "utils",
]

"""Core Bloomberg API processing and connection utilities.

This package contains internal core functionality organized into subpackages:
- utils: Supporting utilities (utils, timezone, trials)
- config: Bloomberg API configuration (overrides, intervals)
- domain: Domain model & contracts (contracts, context)
- infra: Infrastructure layer (conn, blpapi_logging)
- process: Request creation and message processing
- pipeline: Unified data pipeline
"""

# Re-export commonly used modules for backward compatibility
from xbbg.core import pipeline, process
from xbbg.core.config import intervals, overrides
from xbbg.core.domain import context, contracts
from xbbg.core.infra import blpapi_logging, conn
from xbbg.core.utils import timezone, trials, utils

__all__ = [
    'process',
    'pipeline',
    'intervals',
    'overrides',
    'context',
    'contracts',
    'blpapi_logging',
    'conn',
    'timezone',
    'trials',
    'utils',
]


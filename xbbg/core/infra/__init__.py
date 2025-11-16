"""Infrastructure layer for Bloomberg API connections and logging.

This package contains low-level infrastructure:
- conn: Bloomberg session connection management
- blpapi_logging: Optional Bloomberg API logging configuration
"""

# Import modules for easy access
from xbbg.core.infra import blpapi_logging as blpapi_logging_module, conn as conn_module

__all__ = ['conn_module', 'blpapi_logging_module']


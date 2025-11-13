"""An intuitive Bloomberg API."""

from importlib.metadata import PackageNotFoundError, version
import logging

try:
    __version__ = version("xbbg")
except PackageNotFoundError:
    __version__ = "0+unknown"

# Root logger for xbbg package - add NullHandler following best practices
# Applications should configure their own handlers and levels
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Export blpapi logging utilities if available
try:
    from xbbg.core import blpapi_logging
    __all__ = ['__version__', 'blpapi_logging']
except ImportError:
    __all__ = ['__version__']

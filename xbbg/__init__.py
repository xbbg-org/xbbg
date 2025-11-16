"""An intuitive Bloomberg API.

Main entry point for xbbg. For API functions, use `from xbbg import blp` or
`from xbbg.api import bdp, bdh, ...`. For pipeline utilities, use
`from xbbg.utils import pipeline` or `from xbbg import pipeline` (backward compat).
"""

from importlib.metadata import PackageNotFoundError, version
import logging

try:
    __version__ = version("xbbg")
except PackageNotFoundError:
    __version__ = "0+unknown"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.WARNING)

# Backward compatibility: re-export pipeline from utils
from xbbg.utils import pipeline  # noqa: E402, F401

try:
    from xbbg.core.infra import blpapi_logging  # noqa: F401

    __all__ = ['__version__', 'blpapi_logging', 'pipeline']
except ImportError:
    __all__ = ['__version__', 'pipeline']

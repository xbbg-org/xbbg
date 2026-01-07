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

# Backend and format configuration (matching Rust v1 API)
from xbbg.backend import Backend, EngineConfig, Format, configure  # noqa: E402, F401
from xbbg.options import get_backend, get_format, set_backend, set_format  # noqa: E402, F401

# Exception classes (v1.0 compatible)
from xbbg.exceptions import (  # noqa: E402, F401
    BlpError,
    BlpFieldError,
    BlpInternalError,
    BlpRequestError,
    BlpSecurityError,
    BlpSessionError,
    BlpTimeoutError,
    BlpValidationError,
)

# Backward compatibility: re-export pipeline from utils
from xbbg.utils import pipeline  # noqa: E402, F401

try:
    from xbbg.core.infra import blpapi_logging  # noqa: F401

    __all__ = [
        "__version__",
        "Backend",
        "EngineConfig",
        "Format",
        "configure",
        "get_backend",
        "set_backend",
        "get_format",
        "set_format",
        "BlpError",
        "BlpFieldError",
        "BlpInternalError",
        "BlpRequestError",
        "BlpSecurityError",
        "BlpSessionError",
        "BlpTimeoutError",
        "BlpValidationError",
        "blpapi_logging",
        "pipeline",
    ]
except ImportError:
    __all__ = [
        "__version__",
        "Backend",
        "EngineConfig",
        "Format",
        "configure",
        "get_backend",
        "set_backend",
        "get_format",
        "set_format",
        "BlpError",
        "BlpFieldError",
        "BlpInternalError",
        "BlpRequestError",
        "BlpSecurityError",
        "BlpSessionError",
        "BlpTimeoutError",
        "BlpValidationError",
        "pipeline",
    ]

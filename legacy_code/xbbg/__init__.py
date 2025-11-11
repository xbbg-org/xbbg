"""An intuitive Bloomberg API."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("xbbg")
except PackageNotFoundError:
    __version__ = "0+unknown"

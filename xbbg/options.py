"""Global configuration options for xbbg.

This module provides module-level state and functions for configuring the
default backend and output format for xbbg API calls. The API matches the
Rust v1 branch pattern (set_backend, get_backend, etc.) for compatibility.

For v0.x, defaults are set for backward compatibility:
    - backend: Backend.PANDAS
    - format: Format.WIDE

In v1.0, these defaults will change to:
    - backend: Backend.NARWHALS
    - format: Format.LONG

Example usage:
    >>> import xbbg  # doctest: +SKIP
    >>> from xbbg.backend import Backend, Format  # doctest: +SKIP
    >>>
    >>> # Get current defaults
    >>> xbbg.options.get_backend()  # doctest: +SKIP
    <Backend.PANDAS: 'pandas'>
    >>>
    >>> # Set global defaults
    >>> xbbg.options.set_backend(Backend.POLARS)  # doctest: +SKIP
    >>> xbbg.options.set_format(Format.LONG)  # doctest: +SKIP
    >>>
    >>> # Also works with strings
    >>> xbbg.options.set_backend('polars')  # doctest: +SKIP
    >>> xbbg.options.set_format('long')  # doctest: +SKIP
"""

from __future__ import annotations

from xbbg.backend import Backend, Format

# Module-level state (matching Rust v1 pattern)
# v0.x defaults for backward compatibility
_default_backend: Backend = Backend.PANDAS
_default_format: Format = Format.WIDE


def get_backend() -> Backend:
    """Get the current default backend.

    Returns:
        Backend: The current default backend enum value.

    Example:
        >>> from xbbg import options  # doctest: +SKIP
        >>> options.get_backend()  # doctest: +SKIP
        <Backend.PANDAS: 'pandas'>
    """
    return _default_backend


def set_backend(backend: Backend | str) -> None:
    """Set the global default backend.

    This sets the default backend used by all xbbg API calls (bdp, bdh, bds,
    bdib, etc.) when no explicit backend parameter is provided.

    Args:
        backend: Backend enum or string ('pandas', 'polars', 'narwhals',
            'polars_lazy', 'pyarrow', 'duckdb').

    Raises:
        ValueError: If the backend string is not a valid Backend value.

    Example:
        >>> from xbbg import options  # doctest: +SKIP
        >>> from xbbg.backend import Backend  # doctest: +SKIP
        >>>
        >>> # Using enum
        >>> options.set_backend(Backend.POLARS)  # doctest: +SKIP
        >>>
        >>> # Using string
        >>> options.set_backend('polars')  # doctest: +SKIP
    """
    global _default_backend
    if isinstance(backend, str):
        backend = Backend(backend)
    _default_backend = backend


def get_format() -> Format:
    """Get the current default output format.

    Returns:
        Format: The current default format enum value.

    Example:
        >>> from xbbg import options  # doctest: +SKIP
        >>> options.get_format()  # doctest: +SKIP
        <Format.WIDE: 'wide'>
    """
    return _default_format


def set_format(fmt: Format | str) -> None:
    """Set the global default output format.

    This sets the default output format used by all xbbg API calls when no
    explicit format parameter is provided.

    Args:
        fmt: Format enum or string ('long', 'semi_long', 'wide').

    Raises:
        ValueError: If the format string is not a valid Format value.

    Example:
        >>> from xbbg import options  # doctest: +SKIP
        >>> from xbbg.backend import Format  # doctest: +SKIP
        >>>
        >>> # Using enum
        >>> options.set_format(Format.LONG)  # doctest: +SKIP
        >>>
        >>> # Using string
        >>> options.set_format('long')  # doctest: +SKIP
    """
    global _default_format
    if isinstance(fmt, str):
        fmt = Format(fmt)
    _default_format = fmt

"""Deprecation warning infrastructure for xbbg.

This module provides FutureWarning infrastructure for the v1.0 migration.
All warnings are issued once per session to avoid spamming users.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
import warnings

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    T = TypeVar("T")

_BASE_ALL = [
    "XbbgFutureWarning",
    "warn_once",
    "warn_defaults_changing",
    "warn_function_removed",
    "warn_function_renamed",
    "warn_function_moved",
    "warn_signature_changed",
    "warn_parameter_renamed",
    "deprecated_alias",
    "get_warn_func",
]


class XbbgFutureWarning(FutureWarning):
    """Warning for upcoming changes in xbbg v1.0."""


# Track which warnings have been issued this session
_warned: set[str] = set()


def warn_once(key: str, message: str, stacklevel: int = 3) -> None:
    """Issue a FutureWarning once per session.

    Args:
        key: Unique key to identify this warning (only warn once per key).
        message: The warning message to display.
        stacklevel: Stack level for the warning (default 3 for wrapper functions).
    """
    if key in _warned:
        return
    _warned.add(key)
    warnings.warn(message, XbbgFutureWarning, stacklevel=stacklevel)


def warn_defaults_changing() -> None:
    """Warn that default values are changing in version 1.0."""
    warn_once(
        "defaults_changing",
        "xbbg defaults are changing in version 1.0: "
        "backend='narwhals' and format='long' will become the new defaults. "
        "Set backend/format explicitly to silence this warning. "
        "See https://github.com/alpha-xone/xbbg/issues/166 for details.",
        stacklevel=4,
    )


def warn_function_removed(name: str, replacement: str | None = None) -> None:
    """Warn that a function is removed in v1.0.

    Args:
        name: Name of the removed function.
        replacement: Name of the replacement function/approach, if any.
    """
    if replacement:
        msg = f"{name}() is removed in v1.0. {replacement}"
    else:
        msg = f"{name}() is removed in v1.0 with no direct replacement."
    warn_once(f"removed_{name}", msg)


def warn_function_renamed(old_name: str, new_name: str) -> None:
    """Warn that a function has been renamed in v1.0.

    Args:
        old_name: The old function name.
        new_name: The new function name.
    """
    warn_once(f"renamed_{old_name}", f"{old_name}() is renamed to {new_name}() in v1.0.")


def warn_function_moved(name: str, new_location: str) -> None:
    """Warn that a function has moved to a new module in v1.0.

    Args:
        name: Name of the function.
        new_location: New import path (e.g., 'xbbg.ext.dividend').
    """
    warn_once(
        f"moved_{name}",
        f"{name}() has moved to {new_location}() in v1.0. Update imports: from xbbg import ext; ext.{name}(...)",
    )


def warn_signature_changed(name: str, details: str) -> None:
    """Warn that a function's signature has changed in v1.0.

    Args:
        name: Name of the function.
        details: Description of the signature changes.
    """
    warn_once(f"signature_{name}", f"{name}() signature changed in v1.0. {details}")


def warn_parameter_renamed(func_name: str, old_param: str, new_param: str) -> None:
    """Warn that a parameter has been renamed in v1.0.

    Args:
        func_name: Name of the function.
        old_param: Old parameter name.
        new_param: New parameter name.
    """
    warn_once(
        f"param_{func_name}_{old_param}",
        f"{func_name}() parameter '{old_param}' is renamed to '{new_param}' in v1.0.",
    )


def deprecated_alias(
    old_name: str,
    new_func: Callable[..., T],
    warning_func: Callable[[], None],
) -> Callable[..., T]:
    """Create a deprecated alias that warns and delegates to the new function.

    Args:
        old_name: The old function name (for error messages).
        new_func: The new function to delegate to.
        warning_func: A callable that issues the appropriate warning.

    Returns:
        A wrapper function that warns and delegates.
    """

    def wrapper(*args, **kwargs):
        warning_func()
        return new_func(*args, **kwargs)

    wrapper.__name__ = old_name
    wrapper.__doc__ = f"DEPRECATED: {old_name}() - see warning for migration info."
    return wrapper


# =============================================================================
# Pre-defined warning messages for specific functions
# =============================================================================

_DEPRECATION_REGISTRY = {
    # Removed in v1.0
    "connect": (
        "removed",
        "Engine auto-initializes in v1.0. Use xbbg.configure() for custom host/port.",
    ),
    "disconnect": (
        "removed",
        "Engine manages connections automatically in v1.0. Remove this call.",
    ),
    "getBlpapiVersion": (
        "removed",
        "Use xbbg.get_sdk_info() instead, which returns all SDK sources and versions.",
    ),
    "lookupSecurity": (
        "removed",
        "Use xbbg.blkp() instead. Note: yellowkey format changed to 'YK_FILTER_*'.",
    ),
    # Renamed in v1.0
    "fieldInfo": ("renamed", "bfld"),
    "fieldSearch": (
        "custom",
        "fieldSearch() is merged into bfld() in v1.0. Use bfld(search_spec='keyword') for field search.",
    ),
    "bta_studies": ("renamed", "ta_studies"),
    "getPortfolio": ("renamed", "bport"),
    # Signature changed
    "live": (
        "signature",
        "Replaced by asubscribe()/stream() which return Subscription object, not async generator. Yields DataFrames instead of dicts.",
    ),
    "subscribe": (
        "signature",
        "No longer a context manager in v1.0. Returns Subscription object with dynamic add/remove support. Use stream() for simple iteration.",
    ),
    # Param renamed
    "beqs_typ_param": ("param", ("beqs", "typ", "screen_type")),
    # Moved to ext
    "dividend": ("moved", "xbbg.ext.dividend"),
    "earning": ("moved", "xbbg.ext.earning"),
    "turnover": ("moved", "xbbg.ext.turnover"),
    "adjust_ccy": ("moved", "xbbg.ext.adjust_ccy"),
    "fut_ticker": ("moved", "xbbg.ext.fut_ticker"),
    "active_futures": ("moved", "xbbg.ext.active_futures"),
    "cdx_ticker": ("moved", "xbbg.ext.cdx_ticker"),
    "active_cdx": ("moved", "xbbg.ext.active_cdx"),
    "etf_holdings": ("moved", "xbbg.ext.etf_holdings"),
    "preferreds": ("moved", "xbbg.ext.preferreds"),
    "corporate_bonds": ("moved", "xbbg.ext.corporate_bonds"),
    "yas": ("moved", "xbbg.ext.yas"),
    "refresh_studies": ("removed", None),
}


def get_warn_func(name: str) -> Callable[[], None]:
    """Return a zero-argument warning function for a deprecated name."""
    try:
        kind, detail = _DEPRECATION_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown deprecation warning key: {name}") from exc

    def _warn() -> None:
        if kind == "removed":
            warn_function_removed(name, cast("str | None", detail))
            return
        if kind == "renamed":
            warn_function_renamed(name, cast("str", detail))
            return
        if kind == "moved":
            warn_function_moved(name, cast("str", detail))
            return
        if kind == "signature":
            warn_signature_changed(name, cast("str", detail))
            return
        if kind == "param":
            warn_parameter_renamed(*cast("tuple[str, str, str]", detail))
            return
        if kind == "custom":
            warn_once(f"renamed_{name}", cast("str", detail))
            return
        raise ValueError(f"Unknown deprecation warning kind: {kind}")

    _warn.__name__ = f"warn_{name}"
    _warn.__doc__ = f"Warn about {name}() deprecation."
    return _warn


_GENERATED_WARN_NAMES = [f"warn_{name}" for name in _DEPRECATION_REGISTRY]

for _deprecated_name in _DEPRECATION_REGISTRY:
    _warn_name = f"warn_{_deprecated_name}"
    globals()[_warn_name] = get_warn_func(_deprecated_name)

__all__ = [*_BASE_ALL, *_GENERATED_WARN_NAMES]

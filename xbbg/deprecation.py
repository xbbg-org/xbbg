"""Deprecation warning infrastructure for xbbg.

This module provides FutureWarning infrastructure for the v1.0 migration.
All warnings are issued once per session to avoid spamming users.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    T = TypeVar("T")

__all__ = [
    "XbbgFutureWarning",
    "warn_once",
    "warn_defaults_changing",
    "warn_function_removed",
    "warn_function_renamed",
    "warn_function_moved",
    "warn_signature_changed",
    "warn_parameter_renamed",
    "deprecated_alias",
]


class XbbgFutureWarning(FutureWarning):
    """Warning for upcoming changes in xbbg v1.0."""

    pass


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


def warn_connect() -> None:
    """Warn about connect() removal."""
    warn_function_removed(
        "connect",
        "Engine auto-initializes in v1.0. Use xbbg.configure() for custom host/port.",
    )


def warn_disconnect() -> None:
    """Warn about disconnect() removal."""
    warn_function_removed(
        "disconnect",
        "Engine manages connections automatically in v1.0. Remove this call.",
    )


def warn_getBlpapiVersion() -> None:
    """Warn about getBlpapiVersion() removal."""
    warn_function_removed(
        "getBlpapiVersion",
        "Use xbbg.get_sdk_info() instead, which returns all SDK sources and versions.",
    )


def warn_lookupSecurity() -> None:
    """Warn about lookupSecurity() removal."""
    warn_function_removed(
        "lookupSecurity",
        "Use xbbg.blkp() instead. Note: yellowkey format changed to 'YK_FILTER_*'.",
    )


def warn_fieldInfo() -> None:
    """Warn about fieldInfo() rename."""
    warn_function_renamed("fieldInfo", "bfld")


def warn_fieldSearch() -> None:
    """Warn about fieldSearch() merge into bfld()."""
    warn_once(
        "renamed_fieldSearch",
        "fieldSearch() is merged into bfld() in v1.0. Use bfld(search_spec='keyword') for field search.",
    )


def warn_bta_studies() -> None:
    """Warn about bta_studies() rename."""
    warn_function_renamed("bta_studies", "ta_studies")


def warn_refresh_studies() -> None:
    """Warn about refresh_studies() removal."""
    warn_function_removed("refresh_studies")


def warn_getPortfolio() -> None:
    """Warn about getPortfolio() rename."""
    warn_function_renamed("getPortfolio", "bport")


def warn_live() -> None:
    """Warn about live() replacement."""
    warn_signature_changed(
        "live",
        "Replaced by asubscribe()/stream() which return Subscription object, "
        "not async generator. Yields DataFrames instead of dicts.",
    )


def warn_subscribe() -> None:
    """Warn about subscribe() signature change."""
    warn_signature_changed(
        "subscribe",
        "No longer a context manager in v1.0. Returns Subscription object with "
        "dynamic add/remove support. Use stream() for simple iteration.",
    )


def warn_beqs_typ_param() -> None:
    """Warn about beqs() 'typ' parameter rename."""
    warn_parameter_renamed("beqs", "typ", "screen_type")


# =============================================================================
# Moved to ext module warnings
# =============================================================================


def warn_dividend() -> None:
    """Warn about dividend() move to ext module."""
    warn_function_moved("dividend", "xbbg.ext.dividend")


def warn_earning() -> None:
    """Warn about earning() move to ext module."""
    warn_function_moved("earning", "xbbg.ext.earning")


def warn_turnover() -> None:
    """Warn about turnover() move to ext module."""
    warn_function_moved("turnover", "xbbg.ext.turnover")


def warn_adjust_ccy() -> None:
    """Warn about adjust_ccy() move to ext module."""
    warn_function_moved("adjust_ccy", "xbbg.ext.adjust_ccy")


def warn_fut_ticker() -> None:
    """Warn about fut_ticker() move to ext module."""
    warn_function_moved("fut_ticker", "xbbg.ext.fut_ticker")


def warn_active_futures() -> None:
    """Warn about active_futures() move to ext module."""
    warn_function_moved("active_futures", "xbbg.ext.active_futures")


def warn_cdx_ticker() -> None:
    """Warn about cdx_ticker() move to ext module."""
    warn_function_moved("cdx_ticker", "xbbg.ext.cdx_ticker")


def warn_active_cdx() -> None:
    """Warn about active_cdx() move to ext module."""
    warn_function_moved("active_cdx", "xbbg.ext.active_cdx")


def warn_etf_holdings() -> None:
    """Warn about etf_holdings() move to ext module."""
    warn_function_moved("etf_holdings", "xbbg.ext.etf_holdings")


def warn_preferreds() -> None:
    """Warn about preferreds() move to ext module."""
    warn_function_moved("preferreds", "xbbg.ext.preferreds")


def warn_corporate_bonds() -> None:
    """Warn about corporate_bonds() move to ext module."""
    warn_function_moved("corporate_bonds", "xbbg.ext.corporate_bonds")


def warn_yas() -> None:
    """Warn about yas() move to ext module."""
    warn_function_moved("yas", "xbbg.ext.yas")

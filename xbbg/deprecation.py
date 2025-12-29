"""Deprecation warning infrastructure for xbbg."""

import warnings

__all__ = ['XbbgFutureWarning', 'warn_defaults_changing']


class XbbgFutureWarning(FutureWarning):
    """Warning for upcoming changes in xbbg behavior."""
    pass


# Module-level flag to ensure we only warn once per session
_warned_defaults: bool = False


def warn_defaults_changing() -> None:
    """Warn that default values are changing in version 1.0.

    This function only warns once per session to avoid spamming the user.
    """
    global _warned_defaults

    if _warned_defaults:
        return

    _warned_defaults = True

    warnings.warn(
        "xbbg defaults are changing in version 1.0: "
        "backend='narwhals' and format='long' will become the new defaults. "
        "See https://github.com/alpha-xone/xbbg/issues/166 for details.",
        XbbgFutureWarning,
        stacklevel=4,
    )

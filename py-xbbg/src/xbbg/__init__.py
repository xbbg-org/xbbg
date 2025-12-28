"""xbbg - Intuitive Bloomberg data API.

This package provides a high-level API for Bloomberg data access,
powered by a high-performance Rust backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Lazy import of the Rust module to avoid import errors when it's not built
if TYPE_CHECKING:
    from . import _core

__all__ = [
    "_core",
    "bdp",
    "bds",
    "bdh",
    "bdib",
    "bdtick",
    "set_backend",
    "get_backend",
]


def __getattr__(name: str):
    """Lazy attribute access for deferred imports."""
    if name == "_core":
        from . import _core as mod

        return mod
    if name in ("bdp", "bds", "bdh", "bdib", "bdtick", "set_backend", "get_backend"):
        from . import blp

        return getattr(blp, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose public attributes for tab completion."""
    return __all__

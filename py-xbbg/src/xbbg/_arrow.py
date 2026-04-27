"""Native xbbg Arrow object exports.

This module is intentionally a thin import-organizing facade over ``xbbg._core``.
All storage and table operations are implemented in Rust.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xbbg._core import ArrowField, ArrowRecordBatch, ArrowSchema, ArrowTable

__all__ = ["ArrowField", "ArrowRecordBatch", "ArrowSchema", "ArrowTable"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from xbbg import _import_core

        return getattr(_import_core(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

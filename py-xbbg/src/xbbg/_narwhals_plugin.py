"""Narwhals plugin entry point for xbbg native Arrow objects."""

from __future__ import annotations

from typing import Any

from ._narwhals_impl import XbbgNamespace, _is_arrow_record_batch, _is_arrow_table

NATIVE_PACKAGE = "xbbg"


def is_native(native_object: object, /) -> bool:
    """Return whether ``native_object`` is an xbbg Arrow object."""
    return _is_arrow_table(native_object) or _is_arrow_record_batch(native_object)


def __narwhals_namespace__(version: Any) -> XbbgNamespace:
    """Return the Narwhals namespace backing xbbg native Arrow frames."""
    return XbbgNamespace(version=version)

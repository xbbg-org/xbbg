"""Identifier resolution extension functions backed by native xbbg recipes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from xbbg.ext._utils import _call_native_recipe, _syncify

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


def _normalize_ids(values: str | Sequence[str]) -> list[str]:
    return [values] if isinstance(values, str) else [str(value) for value in values]


async def aresolve_isins(
    isins: str | Sequence[str],
    *,
    backend=None,
    **_kwargs,
) -> IntoDataFrame:
    """Async equity ISIN resolution through Bloomberg `/ISIN/<id>` lookups."""
    return await _call_native_recipe(
        "recipe_resolve_isins",
        _normalize_ids(isins),
        backend=backend,
    )


async def aissuer_isins(
    bond_isins: str | Sequence[str],
    *,
    backend=None,
    **_kwargs,
) -> IntoDataFrame:
    """Async bond ISIN to issuer equity ISIN resolution."""
    return await _call_native_recipe(
        "recipe_issuer_isins",
        _normalize_ids(bond_isins),
        backend=backend,
    )


resolve_isins = _syncify(aresolve_isins)
issuer_isins = _syncify(aissuer_isins)

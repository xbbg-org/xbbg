"""Bloomberg Yield & Spread Analysis (YAS) API.

Provides convenience functions for fixed income yield and spread calculations.
"""

from __future__ import annotations

from enum import IntEnum
import logging

import pandas as pd

from xbbg.backend import Backend, Format

logger = logging.getLogger(__name__)

__all__ = ["yas", "YieldType"]


class YieldType(IntEnum):
    """Bloomberg YAS yield calculation type (YAS_YLD_FLAG override).

    Used to specify whether to calculate Yield to Maturity or Yield to Call.

    Examples:
        >>> from xbbg.api.fixed_income import YieldType
        >>> YieldType.YTM
        <YieldType.YTM: 1>
        >>> YieldType.YTC
        <YieldType.YTC: 2>
        >>> int(YieldType.YTM)
        1
    """

    YTM = 1  # Yield to Maturity
    YTC = 2  # Yield to Call


def yas(
    tickers: str | list[str],
    flds: str | list[str] = "YAS_BOND_YLD",
    *,
    settle_dt: str | pd.Timestamp | None = None,
    yield_type: YieldType | int | None = None,
    spread: float | None = None,
    yield_: float | None = None,
    price: float | None = None,
    benchmark: str | None = None,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Bloomberg Yield & Spread Analysis (YAS) data.

    Convenience wrapper for YAS fields with commonly-used overrides as named parameters.
    Replicates Bloomberg YAS<GO> screen functionality via API.

    Args:
        tickers: Bond ticker(s) (e.g., 'US912810TD00 Govt', '/isin/US912810TD00')
        flds: YAS field(s) to retrieve. Defaults to 'YAS_BOND_YLD'.
            Common fields: YAS_BOND_YLD, YAS_BOND_PX, YAS_MOD_DUR,
            YAS_OAS_SPREAD, YAS_ASW_SPREAD, YAS_Z_SPREAD, YAS_YLD_SPREAD
        settle_dt: Settlement date for yield calculation (YYYYMMDD or datetime).
            Maps to SETTLE_DT override.
        yield_type: Yield calculation type - YieldType.YTM (1) or YieldType.YTC (2).
            Maps to YAS_YLD_FLAG override.
        spread: Spread to benchmark in basis points.
            Maps to YAS_YLD_SPREAD override.
        yield_: Input yield to calculate price from.
            Maps to YAS_BOND_YLD override.
        price: Input price to calculate yield from.
            Maps to YAS_BOND_PX override.
        benchmark: Benchmark bond ticker for spread calculations.
            Maps to YAS_BNCHMRK_BOND override.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS).
            Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG).
            Defaults to global setting.
        **kwargs: Additional Bloomberg overrides passed directly to bdp().

    Returns:
        pd.DataFrame: YAS data with tickers as index and fields as columns.

    Examples:
        Basic usage (requires Bloomberg session; skipped in doctest):

        >>> from xbbg import blp  # doctest: +SKIP
        >>> from xbbg.api.fixed_income import YieldType  # doctest: +SKIP
        >>>
        >>> # Get yield to maturity for a bond
        >>> blp.yas('US912810TD00 Govt')  # doctest: +SKIP
        >>>
        >>> # Get yield with custom settlement date
        >>> blp.yas('US912810TD00 Govt', settle_dt='20240115')  # doctest: +SKIP
        >>>
        >>> # Get yield to call instead of yield to maturity
        >>> blp.yas('XYZ Corp', yield_type=YieldType.YTC)  # doctest: +SKIP
        >>>
        >>> # Calculate yield from a given price
        >>> blp.yas('US912810TD00 Govt', price=98.5)  # doctest: +SKIP
        >>>
        >>> # Calculate price from a given yield
        >>> blp.yas('US912810TD00 Govt', flds='YAS_BOND_PX', yield_=4.5)  # doctest: +SKIP
        >>>
        >>> # Get spread to a specific benchmark
        >>> blp.yas('XYZ Corp', flds='YAS_YLD_SPREAD', benchmark='US912810TD00 Govt')  # doctest: +SKIP
        >>>
        >>> # Get multiple YAS analytics
        >>> blp.yas('US912810TD00 Govt', ['YAS_BOND_YLD', 'YAS_MOD_DUR', 'YAS_Z_SPREAD'])  # doctest: +SKIP
    """
    from xbbg.api.reference import bdp

    # Build overrides dict from named parameters
    overrides: dict[str, object] = {}

    if settle_dt is not None:
        # Convert to YYYYMMDD format if needed
        formatted_dt: str | None = None

        if isinstance(settle_dt, str):
            # Try to parse and reformat to ensure consistent format
            try:
                dt = pd.Timestamp(settle_dt)
                if dt is not pd.NaT:
                    formatted_dt = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"
            except (ValueError, TypeError):
                # If parsing fails, pass through as-is
                formatted_dt = settle_dt
        elif isinstance(settle_dt, pd.Timestamp) and settle_dt is not pd.NaT:
            formatted_dt = f"{settle_dt.year:04d}{settle_dt.month:02d}{settle_dt.day:02d}"
        else:
            formatted_dt = str(settle_dt) if settle_dt is not None else None

        if formatted_dt is not None:
            overrides["SETTLE_DT"] = formatted_dt

    if yield_type is not None:
        # Accept both YieldType enum and raw int
        overrides["YAS_YLD_FLAG"] = int(yield_type)

    if spread is not None:
        overrides["YAS_YLD_SPREAD"] = spread

    if yield_ is not None:
        overrides["YAS_BOND_YLD"] = yield_

    if price is not None:
        overrides["YAS_BOND_PX"] = price

    if benchmark is not None:
        overrides["YAS_BNCHMRK_BOND"] = benchmark

    # Merge with any additional kwargs overrides (kwargs take precedence)
    overrides.update(kwargs)

    # Call bdp with the YAS fields and overrides
    return bdp(tickers=tickers, flds=flds, backend=backend, format=format, **overrides)

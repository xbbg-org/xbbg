"""Shared helper functions for Bloomberg API modules.

This module provides utility functions that can be used across multiple API modules.
"""

from __future__ import annotations

import pandas as pd

from xbbg.backend import Format
from xbbg.io.convert import is_empty

__all__ = ["adjust_ccy"]


def adjust_ccy(data: pd.DataFrame, ccy: str = "USD") -> pd.DataFrame:
    """Adjust series to a target currency.

    This is a general utility function that can be used with any time-series DataFrame
    from historical (bdh), intraday (bdib), or other APIs that return DataFrames with
    date/datetime index and ticker columns.

    Args:
        data: DataFrame with date/datetime index and MultiIndex columns (ticker, field).
            Can be from bdh, bdib, or any other time-series API.
        ccy: currency to adjust to (default: 'USD'). Use 'local' for no adjustment.

    Returns:
        pd.DataFrame: Currency-adjusted data in the same format as input.

    Examples:
        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Works with historical data
        >>> hist_data = blp.bdh('AAPL US Equity', start_date='2024-01-01')  # doctest: +SKIP
        >>> adjusted = blp.adjust_ccy(hist_data, ccy='EUR')  # doctest: +SKIP
        >>>
        >>> # Could also work with intraday data
        >>> intraday_data = blp.bdib('AAPL US Equity', dt='2024-01-01')  # doctest: +SKIP
        >>> adjusted_intraday = blp.adjust_ccy(intraday_data, ccy='EUR')  # doctest: +SKIP
    """
    from xbbg.api.historical import bdh  # noqa: PLC0415
    from xbbg.api.reference import bdp  # noqa: PLC0415

    if is_empty(data):
        return pd.DataFrame()
    if ccy.lower() == "local":
        return data
    tickers = list(data.columns.get_level_values(level=0).unique())
    start_date = data.index[0]
    end_date = data.index[-1]

    # Use WIDE format for internal calls since this function expects MultiIndex columns
    uccy = bdp(tickers=tickers, flds="crncy", format=Format.WIDE)
    if not is_empty(uccy):
        adj = (
            uccy.crncy.map(
                lambda v: {
                    "ccy": None if v.upper() == ccy else f"{ccy}{v.upper()} Curncy",
                    "factor": 100.0 if v[-1].islower() else 1.0,
                }
            )
            .apply(pd.Series)
            .dropna(subset=["ccy"])
        )
    else:
        adj = pd.DataFrame()

    if not is_empty(adj):
        # Use WIDE format to get MultiIndex columns for .xs() access
        fx = bdh(tickers=adj.ccy.unique(), start_date=start_date, end_date=end_date, format=Format.WIDE).xs(
            "Last_Price", axis=1, level=1
        )
    else:
        fx = pd.DataFrame()

    return pd.concat(
        [
            pd.Series(
                (
                    data[t]
                    .dropna()
                    .prod(axis=1)
                    .div(
                        (fx[adj.loc[t, "ccy"]] * adj.loc[t, "factor"]) if t in adj.index else 1.0,
                    )
                ),
                name=t,
            )
            for t in tickers
        ],
        axis=1,
    )

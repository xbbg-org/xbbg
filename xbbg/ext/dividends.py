"""Dividend history utilities.

This module provides dividend and split history functionality.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from xbbg import const
from xbbg.api.reference import bds
from xbbg.backend import Backend, Format
from xbbg.core.utils import utils

__all__ = ["dividend"]


def dividend(
    tickers: str | list[str],
    typ: str = "all",
    start_date: str | datetime | None = None,
    end_date: str | datetime | None = None,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> Any:
    """Bloomberg dividend / split history.

    Args:
        tickers: list of tickers
        typ: dividend adjustment type
            `all`:       `DVD_Hist_All`
            `dvd`:       `DVD_Hist`
            `split`:     `Eqy_DVD_Hist_Splits`
            `gross`:     `Eqy_DVD_Hist_Gross`
            `adjust`:    `Eqy_DVD_Adjust_Fact`
            `adj_fund`:  `Eqy_DVD_Adj_Fund`
            `with_amt`:  `DVD_Hist_All_with_Amt_Status`
            `dvd_amt`:   `DVD_Hist_with_Amt_Status`
            `gross_amt`: `DVD_Hist_Gross_with_Amt_Stat`
            `projected`: `BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann`
        start_date: start date
        end_date: end date
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: overrides

    Returns:
        DataFrame
    """
    kwargs.pop("raw", None)
    tickers = utils.normalize_tickers(tickers)
    tickers = [t for t in tickers if ("Equity" in t) and ("=" not in t)]

    fld = const.DVD_TPYES.get(typ, typ)

    if (fld == "Eqy_DVD_Adjust_Fact") and ("Corporate_Actions_Filter" not in kwargs):
        kwargs["Corporate_Actions_Filter"] = "NORMAL_CASH|ABNORMAL_CASH|CAPITAL_CHANGE"

    if start_date:
        kwargs["DVD_Start_Dt"] = utils.fmt_dt(start_date, fmt="%Y%m%d")
    if end_date:
        kwargs["DVD_End_Dt"] = utils.fmt_dt(end_date, fmt="%Y%m%d")

    return bds(tickers=tickers, flds=fld, col_maps=const.DVD_COLS, backend=backend, format=format, **kwargs)

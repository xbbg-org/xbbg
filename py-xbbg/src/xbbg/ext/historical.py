"""Historical data extension functions.

Convenience wrappers around bds/bdh for common historical data queries.
Returns DataFrame in the configured backend format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import narwhals.stable.v1 as nw

from xbbg.ext.const import DVD_COLS, DVD_TYPES

if TYPE_CHECKING:
    from datetime import date

    from narwhals.typing import IntoDataFrame


def _normalize_tickers(tickers: str | list[str]) -> list[str]:
    """Normalize tickers to a list."""
    if isinstance(tickers, str):
        return [tickers]
    return list(tickers)


def _fmt_date(dt: str | date | None, fmt: str = "%Y%m%d") -> str | None:
    """Format date to string."""
    if dt is None:
        return None
    if isinstance(dt, str):
        # Try to parse and reformat
        import re

        # Already in YYYYMMDD format
        if re.match(r"^\d{8}$", dt):
            return dt
        # Try common formats
        from datetime import datetime

        for parse_fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
            try:
                parsed = datetime.strptime(dt, parse_fmt)
                return parsed.strftime(fmt)
            except ValueError:
                continue
        return dt  # Return as-is if can't parse
    # datetime or date object
    return dt.strftime(fmt)


def dividend(
    tickers: str | list[str],
    typ: str = "all",
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Get dividend and split history for securities.

    Convenience wrapper around bds() for dividend data.

    Args:
        tickers: Single ticker or list of tickers (must be Equity).
        typ: Dividend type:
            - "all": All dividends and splits (DVD_Hist_All)
            - "dvd": Regular dividends only (DVD_Hist)
            - "split": Splits only (Eqy_DVD_Hist_Splits)
            - "gross": Gross dividends (Eqy_DVD_Hist_Gross)
            - "adjust": Adjustment factors (Eqy_DVD_Adjust_Fact)
            - "adj_fund": Fund adjustment factors (Eqy_DVD_Adj_Fund)
            - "with_amt": All with amount status (DVD_Hist_All_with_Amt_Status)
            - "dvd_amt": Dividends with amount status (DVD_Hist_with_Amt_Status)
            - "gross_amt": Gross with amount status (DVD_Hist_Gross_with_Amt_Stat)
            - "projected": Projected dividends (BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann)
        start_date: Start date for dividend history (optional).
        end_date: End date for dividend history (optional).
        **kwargs: Additional arguments passed to bds().

    Returns:
        DataFrame with dividend history (type depends on configured backend).

    Example::

        from xbbg import ext

        # Get all dividend history
        df = ext.dividend("AAPL US Equity")

        # Get dividends for specific date range
        df = ext.dividend("MSFT US Equity", start_date="2020-01-01", end_date="2024-01-01")

        # Get only splits
        df = ext.dividend("TSLA US Equity", typ="split")
    """
    from xbbg import bds

    tickers_list = _normalize_tickers(tickers)
    # Filter to equity tickers only
    tickers_list = [t for t in tickers_list if "Equity" in t and "=" not in t]

    if not tickers_list:
        # Return empty DataFrame using configured backend
        from xbbg.blp import Backend, get_backend

        backend = get_backend()
        if backend == Backend.PANDAS:
            import pandas as pd

            return pd.DataFrame()
        elif backend == Backend.PYARROW:
            import pyarrow as pa

            return pa.table({})
        elif backend == Backend.DUCKDB:
            import duckdb

            return duckdb.query("SELECT 1 WHERE FALSE")
        else:
            # Default to polars for POLARS, POLARS_LAZY, NARWHALS, NARWHALS_LAZY, or None
            import polars as pl

            return pl.DataFrame()

    # Get the Bloomberg field name
    fld = DVD_TYPES.get(typ, typ)

    # Special handling for adjustment factors
    if fld == "Eqy_DVD_Adjust_Fact" and "Corporate_Actions_Filter" not in kwargs:
        kwargs["Corporate_Actions_Filter"] = "NORMAL_CASH|ABNORMAL_CASH|CAPITAL_CHANGE"

    # Add date overrides
    if start_date:
        kwargs["DVD_Start_Dt"] = _fmt_date(start_date)
    if end_date:
        kwargs["DVD_End_Dt"] = _fmt_date(end_date)

    # Call bds - returns DataFrame in configured backend format
    df = bds(tickers=tickers_list, flds=fld, **kwargs)

    # Convert to narwhals for manipulation
    nw_df = nw.from_native(df)

    if len(nw_df) == 0:
        return df

    # Rename columns using DVD_COLS mapping
    rename_map = {old: new for old, new in DVD_COLS.items() if old in nw_df.columns}
    if rename_map:
        nw_df = nw_df.rename(rename_map)
        return nw_df.to_native()

    return df


def earning(
    ticker: str,
    by: str = "Geo",
    typ: str = "Revenue",
    *,
    ccy: str | None = None,
    level: int | None = None,
    year: int | None = None,
    periods: int | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Get earnings breakdown for a security.

    Convenience wrapper around bds() for earnings data by geography or product.

    Args:
        ticker: Single ticker (e.g., "AMD US Equity").
        by: Breakdown type - "Geo" (geographic) or "Product".
        typ: Type of earning metric:
            - "Revenue": Revenue breakdown
            - "Operating_Income": Operating income (EBIT)
            - "Assets": Assets breakdown
            - "Gross_Profit": Gross profit
            - "Capital_Expenditures": CapEx
        ccy: Currency for earnings (optional).
        level: Hierarchy level (optional).
        year: Fiscal year (e.g., 2023).
        periods: Number of periods to retrieve.
        **kwargs: Additional arguments passed to bds().

    Returns:
        DataFrame with earnings breakdown (type depends on configured backend).

    Example::

        from xbbg import ext

        # Get geographic revenue breakdown
        df = ext.earning("AMD US Equity", by="Geo")

        # Get product revenue breakdown for specific year
        df = ext.earning("AAPL US Equity", by="Product", year=2023)

        # Get operating income by geography
        df = ext.earning("MSFT US Equity", by="Geo", typ="Operating_Income")
    """
    from xbbg import bds

    # Determine override value
    ovrd = "G" if by[0].upper() == "G" else "P"
    base_kwargs: dict = {"Product_Geo_Override": ovrd}

    # Add optional overrides
    if year:
        base_kwargs["Eqy_Fund_Year"] = year
    if periods:
        base_kwargs["Number_Of_Periods"] = periods

    # Get header first
    header = bds(tickers=ticker, flds="PG_Bulk_Header", **base_kwargs, **kwargs)
    header_nw = nw.from_native(header)

    # Add currency and level if specified
    if ccy:
        base_kwargs["Eqy_Fund_Crncy"] = ccy
    if level:
        base_kwargs["PG_Hierarchy_Level"] = level

    # Get the actual data
    data = bds(tickers=ticker, flds=f"PG_{typ}", **base_kwargs, **kwargs)
    data_nw = nw.from_native(data)

    if len(data_nw) == 0 or len(header_nw) == 0:
        return data

    if data_nw.shape[1] != header_nw.shape[1]:
        msg = f"Inconsistent shape: data has {data_nw.shape[1]} columns, header has {header_nw.shape[1]}"
        raise ValueError(msg)

    # Use header row as column names
    new_cols = header_nw.row(0) if len(header_nw) > 0 else [f"col_{i}" for i in range(data_nw.shape[1])]
    # Clean column names
    clean_cols = [str(c).lower().replace(" ", "_").replace("_20", "20") for c in new_cols]
    data_nw = data_nw.rename(dict(zip(data_nw.columns, clean_cols, strict=False)))

    return data_nw.to_native()


def turnover(
    tickers: str | list[str],
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    ccy: str = "USD",
    factor: float = 1e6,
    **kwargs,
) -> IntoDataFrame:
    """Get trading volume and turnover for securities.

    Convenience wrapper around bdh() for turnover data with optional
    currency conversion.

    Args:
        tickers: Single ticker or list of tickers.
        start_date: Start date for turnover data (default: 1 month ago).
        end_date: End date for turnover data (default: yesterday).
        ccy: Currency for conversion (default: "USD"). Use "local" for no conversion.
        factor: Division factor (default: 1e6 for millions).
        **kwargs: Additional arguments passed to bdh().

    Returns:
        DataFrame with turnover data (type depends on configured backend).

    Example::

        from xbbg import ext

        # Get turnover in millions USD
        df = ext.turnover(["AAPL US Equity", "MSFT US Equity"], start_date="2024-01-01")

        # Get turnover in local currency
        df = ext.turnover("7203 JP Equity", ccy="local")

        # Get turnover in EUR, in billions
        df = ext.turnover("SAP GR Equity", ccy="EUR", factor=1e9)
    """
    from datetime import datetime, timedelta

    from xbbg import bdh
    from xbbg.ext.currency import adjust_ccy

    # Default dates
    if end_date is None:
        end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if start_date is None:
        if isinstance(end_date, str):
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                end_dt = datetime.now()
        else:
            end_dt = end_date
        start_date = (end_dt - timedelta(days=30)).strftime("%Y-%m-%d")

    tickers_list = _normalize_tickers(tickers)

    # Get turnover data - returns DataFrame in configured backend format
    data = bdh(
        tickers=tickers_list,
        flds="Turnover",
        start_date=start_date,
        end_date=end_date,
        **kwargs,
    )

    # Convert to narwhals for manipulation
    nw_df = nw.from_native(data)

    if len(nw_df) == 0:
        return data

    # Apply currency conversion
    if ccy.lower() != "local":
        data = adjust_ccy(data, ccy=ccy)
        nw_df = nw.from_native(data)

    # Apply factor
    if factor != 1.0:
        # Divide numeric columns by factor
        numeric_cols = [c for c in nw_df.columns if nw_df[c].dtype.is_numeric()]
        if numeric_cols:
            nw_df = nw_df.with_columns([nw.col(c) / factor for c in numeric_cols])
            return nw_df.to_native()

    return data

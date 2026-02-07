"""Historical data extension functions.

Convenience wrappers around bds/bdh for common historical data queries.
Returns DataFrame in the configured backend format.
Uses high-performance Rust utilities from xbbg._core.

Sync functions (wrap async with asyncio.run):
    - dividend(): Get dividend and split history
    - earning(): Get earnings breakdown
    - turnover(): Get trading volume and turnover
    - etf_holdings(): Get ETF holdings via BQL

Async functions (primary implementation):
    - adividend(): Async dividend history
    - aearning(): Async earnings breakdown
    - aturnover(): Async turnover data
    - aetf_holdings(): Async ETF holdings
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import narwhals.stable.v1 as nw

# Import Rust ext utilities for max performance
from xbbg._core import (
    ext_filter_equity_tickers,
    ext_get_dvd_type,
    ext_rename_dividend_columns,
)
from xbbg.ext._utils import _fmt_date

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import date

    from narwhals.typing import IntoDataFrame


def _get_empty_dataframe() -> IntoDataFrame:
    """Return empty DataFrame using configured backend."""
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


# =============================================================================
# Async implementations (primary)
# =============================================================================


async def adividend(
    tickers: str | list[str],
    typ: str = "all",
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Async get dividend and split history for securities.

    Convenience wrapper around abds() for dividend data.
    Uses Rust for ticker filtering and column renaming.

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
        **kwargs: Additional arguments passed to abds().

    Returns:
        DataFrame with dividend history (type depends on configured backend).

    Example::

        import asyncio
        from xbbg.ext.historical import adividend


        async def main():
            # Get all dividend history
            df = await adividend("AAPL US Equity")

            # Get dividends for specific date range
            df = await adividend("MSFT US Equity", start_date="2020-01-01", end_date="2024-01-01")

            # Get only splits
            df = await adividend("TSLA US Equity", typ="split")


        asyncio.run(main())
    """
    from xbbg import abds

    # Pop 'raw' kwarg if present (not used by bds)
    kwargs.pop("raw", None)

    # Normalize and filter tickers using Rust
    if isinstance(tickers, str):
        tickers_list = [tickers]
    else:
        tickers_list = list(tickers)

    # Filter to equity tickers using Rust (high performance)
    tickers_list = ext_filter_equity_tickers(tickers_list)

    if not tickers_list:
        return _get_empty_dataframe()

    # Get the Bloomberg field name using Rust
    fld = ext_get_dvd_type(typ)
    if fld is None:
        fld = typ  # Use as-is if not in mapping

    # Special handling for adjustment factors
    if fld == "Eqy_DVD_Adjust_Fact" and "Corporate_Actions_Filter" not in kwargs:
        kwargs["Corporate_Actions_Filter"] = "NORMAL_CASH|ABNORMAL_CASH|CAPITAL_CHANGE"

    # Add date overrides
    if start_date:
        kwargs["DVD_Start_Dt"] = _fmt_date(start_date)
    if end_date:
        kwargs["DVD_End_Dt"] = _fmt_date(end_date)

    # Call abds - returns DataFrame in configured backend format
    df = await abds(tickers=tickers_list, flds=fld, **kwargs)

    # Convert to narwhals for manipulation
    nw_df = nw.from_native(df)

    if len(nw_df) == 0:
        return df

    # Get column rename mapping from Rust (high performance)
    rename_pairs = ext_rename_dividend_columns(list(nw_df.columns))
    if rename_pairs:
        rename_map = {old: new for old, new in rename_pairs}
        nw_df = nw_df.rename(rename_map)
        return nw_df.to_native()

    return df


def _build_earning_header_rename(
    header_nw: nw.DataFrame,
    data_nw: nw.DataFrame,
) -> dict[str, str]:
    """Build column rename mapping from earnings header values.

    Maps data column names (e.g., "Period X Value") to human-readable names
    derived from the header row (e.g., "fy2023").

    Args:
        header_nw: Header DataFrame from PG_Bulk_Header BDS call.
        data_nw: Data DataFrame from PG_{typ} BDS call.

    Returns:
        Dict mapping original column names to cleaned header-based names.
    """
    header_row = dict(next(header_nw.iter_rows(named=True)))
    rename_map: dict[str, str] = {}

    for data_col in data_nw.columns:
        if data_col == "ticker":
            continue

        # Determine the corresponding header column name
        if data_col.endswith(" Value"):
            # "Period X Value" -> "Period X Header"
            header_col = data_col.replace(" Value", " Header")
        else:
            # "Metric Name" -> "Metric Name Header"
            header_col = f"{data_col} Header"

        # Get the header value and clean it
        if header_col in header_row:
            new_name = str(header_row[header_col]).lower().replace(" ", "_").replace("_20", "20")
            rename_map[data_col] = new_name

    return rename_map


def _compute_earning_percentages(
    data_nw: nw.DataFrame,
    fy_cols: list[str],
) -> nw.DataFrame:
    """Compute percentage columns for each fiscal year in earnings data.

    For level 1 rows, computes percentage of total level 1 sum.
    For level 2 rows, computes percentage of parent level 1 group sum.

    Args:
        data_nw: Earnings DataFrame (already renamed) containing a "level" column.
        fy_cols: List of fiscal year column names (e.g., ["fy2022", "fy2023"]).

    Returns:
        DataFrame with ``{fy}_pct`` columns inserted after each fiscal year column.
    """
    for yr in fy_cols:
        pct_col = f"{yr}_pct"

        # Get level column as list for iteration, converting to int
        raw_levels = data_nw["level"].to_list()
        levels: list[int | None] = []
        for lvl in raw_levels:
            if lvl is None:
                levels.append(None)
            else:
                try:
                    levels.append(int(lvl))
                except (ValueError, TypeError):
                    levels.append(None)

        # Get fiscal year values, converting to float
        raw_values = data_nw[yr].to_list()
        values: list[float | None] = []
        for val in raw_values:
            if val is None:
                values.append(None)
            else:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    values.append(None)

        pct_values: list[float | None] = [None] * len(levels)

        # Calculate level 1 percentage (% of total level 1)
        level_1_indices = [i for i, lvl in enumerate(levels) if lvl == 1]
        if level_1_indices:
            level_1_sum = sum(v for i, v in enumerate(values) if i in level_1_indices and v is not None)
            if level_1_sum and level_1_sum != 0:
                for i in level_1_indices:
                    val = values[i]
                    if val is not None:
                        pct_values[i] = 100.0 * val / level_1_sum

        # Calculate level 2 percentage (% of parent level 1 group)
        # Iterate backwards to group level 2 rows by their level 1 parent
        level_2_group: list[int] = []
        for i in range(len(levels) - 1, -1, -1):
            row_level = levels[i]
            if row_level is None or row_level > 2:
                continue
            if row_level == 2:
                level_2_group.append(i)
            elif row_level == 1:
                # Calculate percentage for this level 2 group
                if level_2_group:
                    group_sum = sum(v for j, v in enumerate(values) if j in level_2_group and v is not None)
                    if group_sum and group_sum != 0:
                        for j in level_2_group:
                            val = values[j]
                            if val is not None:
                                pct_values[j] = 100.0 * val / group_sum
                level_2_group = []

        # Add percentage column using narwhals (backend-agnostic)
        native_namespace = nw.get_native_namespace(data_nw)
        pct_series = nw.new_series(pct_col, pct_values, native_namespace=native_namespace)

        # Insert after the year column
        yr_idx = data_nw.columns.index(yr)
        cols_before = data_nw.columns[: yr_idx + 1]
        cols_after = data_nw.columns[yr_idx + 1 :]

        data_nw = data_nw.with_columns(pct_series)

        # Reorder columns to place pct after year
        new_order = [*list(cols_before), pct_col, *list(cols_after)]
        data_nw = data_nw.select(new_order)

    return data_nw


async def aearning(
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
    """Async get earnings breakdown for a security.

    Convenience wrapper around abds() for earnings data by geography or product.

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
        **kwargs: Additional arguments passed to abds().

    Returns:
        DataFrame with earnings breakdown (type depends on configured backend).

    Example::

        import asyncio
        from xbbg.ext.historical import aearning


        async def main():
            # Get geographic revenue breakdown
            df = await aearning("AMD US Equity", by="Geo")

            # Get product revenue breakdown for specific year
            df = await aearning("AAPL US Equity", by="Product", year=2023)

            # Get operating income by geography
            df = await aearning("MSFT US Equity", by="Geo", typ="Operating_Income")


        asyncio.run(main())
    """
    from xbbg import abds

    # Pop 'raw' kwarg if present (not used by bds)
    kwargs.pop("raw", None)

    # Determine override value
    ovrd = "G" if by[0].upper() == "G" else "P"
    base_kwargs: dict = {"Product_Geo_Override": ovrd}

    # Add optional overrides
    if year:
        base_kwargs["Eqy_Fund_Year"] = year
    if periods:
        base_kwargs["Number_Of_Periods"] = periods

    # Get header first
    header = await abds(tickers=ticker, flds="PG_Bulk_Header", **base_kwargs, **kwargs)
    header_nw = nw.from_native(header)

    # Add currency and level if specified
    if ccy:
        base_kwargs["Eqy_Fund_Crncy"] = ccy
    if level:
        base_kwargs["PG_Hierarchy_Level"] = level

    # Get the actual data
    data = await abds(tickers=ticker, flds=f"PG_{typ}", **base_kwargs, **kwargs)
    data_nw = nw.from_native(data)

    if len(data_nw) == 0 or len(header_nw) == 0:
        return data

    # Build column rename mapping from header
    rename_map = _build_earning_header_rename(header_nw, data_nw)

    # Apply renaming
    if rename_map:
        data_nw = data_nw.rename(rename_map)

    # Calculate percentage columns for each fiscal year
    if "level" not in data_nw.columns:
        return data_nw.to_native()

    # Find fiscal year columns (start with 'fy')
    fy_cols = [c for c in data_nw.columns if c.startswith("fy") and not c.endswith("_pct")]

    data_nw = _compute_earning_percentages(data_nw, fy_cols)

    return data_nw.to_native()


async def _calc_turnover_from_volume(
    missing_tickers: list[str],
    start_date: str | date,
    end_date: str | date,
    nw_df: nw.DataFrame,
    **kwargs,
) -> tuple[nw.DataFrame, IntoDataFrame]:
    """Fetch volume × VWAP for tickers missing direct Turnover data.

    For each ticker in *missing_tickers*, retrieves ``eqy_weighted_avg_px``
    and ``volume`` via ``abdh``, computes turnover as their product, and
    joins the result into the main DataFrame.

    Args:
        missing_tickers: Tickers that had no Turnover column in the initial fetch.
        start_date: Start date for the historical query.
        end_date: End date for the historical query.
        nw_df: Current narwhals DataFrame (may be empty).
        **kwargs: Additional arguments forwarded to ``abdh``.

    Returns:
        Tuple of (updated narwhals DataFrame, updated native DataFrame).
    """
    from xbbg import abdh

    vol_data = await abdh(
        tickers=missing_tickers,
        flds=["eqy_weighted_avg_px", "volume"],
        start_date=start_date,
        end_date=end_date,
        **kwargs,
    )
    vol_nw = nw.from_native(vol_data)

    if len(vol_nw) > 0:
        # Calculate turnover = volume * VWAP for each ticker
        for t in missing_tickers:
            vwap_col = None
            vol_col = None
            for col in vol_nw.columns:
                if t in col and "eqy_weighted_avg_px" in col.lower():
                    vwap_col = col
                elif t in col and "volume" in col.lower():
                    vol_col = col

            if vwap_col and vol_col:
                # Calculate turnover
                turnover_col = f"{t}|Turnover"
                vol_nw = vol_nw.with_columns((nw.col(vwap_col) * nw.col(vol_col)).alias(turnover_col))

                # Add to main dataframe
                if "date" in nw_df.columns and "date" in vol_nw.columns:
                    # Join on date
                    turnover_series = vol_nw.select(["date", turnover_col])
                    nw_df = nw_df.join(turnover_series, on="date", how="outer")
                elif len(nw_df) == 0:
                    # Main df is empty, use vol_nw
                    nw_df = vol_nw.select(["date"] + [c for c in vol_nw.columns if "|Turnover" in c])

    return nw_df, nw_df.to_native()


async def aturnover(
    tickers: str | list[str],
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    ccy: str = "USD",
    factor: float = 1e6,
    **kwargs,
) -> IntoDataFrame:
    """Async get trading volume and turnover for securities.

    Convenience wrapper around abdh() for turnover data with optional
    currency conversion. For equities where the Turnover field is not available,
    calculates turnover as volume * VWAP (eqy_weighted_avg_px).

    Args:
        tickers: Single ticker or list of tickers.
        start_date: Start date for turnover data (default: 1 month ago).
        end_date: End date for turnover data (default: yesterday).
        ccy: Currency for conversion (default: "USD"). Use "local" for no conversion.
        factor: Division factor (default: 1e6 for millions).
        **kwargs: Additional arguments passed to abdh().

    Returns:
        DataFrame with turnover data (type depends on configured backend).

    Example::

        import asyncio
        from xbbg.ext.historical import aturnover


        async def main():
            # Get turnover in millions USD
            df = await aturnover(["AAPL US Equity", "MSFT US Equity"], start_date="2024-01-01")

            # Get turnover in local currency
            df = await aturnover("7203 JP Equity", ccy="local")

            # Get turnover in EUR, in billions
            df = await aturnover("SAP GR Equity", ccy="EUR", factor=1e9)


        asyncio.run(main())
    """
    from datetime import datetime, timedelta

    from xbbg import abdh
    from xbbg.ext.currency import aadjust_ccy

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

    # Normalize tickers
    if isinstance(tickers, str):
        tickers_list = [tickers]
    else:
        tickers_list = list(tickers)

    # Get turnover data - returns DataFrame in configured backend format
    data = await abdh(
        tickers=tickers_list,
        flds="Turnover",
        start_date=start_date,
        end_date=end_date,
        **kwargs,
    )

    # Convert to narwhals for manipulation
    nw_df = nw.from_native(data)

    # Check which tickers have turnover data
    # Column names typically include ticker (e.g., "AAPL US Equity|Turnover")
    tickers_with_data = set()
    for col in nw_df.columns:
        for t in tickers_list:
            if t in col:
                tickers_with_data.add(t)
                break

    # For tickers without turnover, calculate from volume * VWAP
    missing_tickers = [t for t in tickers_list if t not in tickers_with_data]

    if missing_tickers:
        try:
            nw_df, data = await _calc_turnover_from_volume(missing_tickers, start_date, end_date, nw_df, **kwargs)
        except (ValueError, TypeError, KeyError):
            # If fallback fails, continue with original data
            logger.debug("Turnover volume fallback failed")

    if len(nw_df) == 0:
        return data

    # Apply currency conversion
    if ccy.lower() != "local":
        data = await aadjust_ccy(data, ccy=ccy)
        nw_df: nw.DataFrame = nw.from_native(data)  # type: ignore[assignment]

    # Apply factor
    if factor != 1.0:
        # Divide numeric columns by factor
        numeric_cols = [c for c in nw_df.columns if nw_df[c].dtype.is_numeric()]
        if numeric_cols:
            nw_df = nw_df.with_columns([nw.col(c) / factor for c in numeric_cols])
            return nw_df.to_native()

    return data


async def aetf_holdings(
    etf_ticker: str,
    *,
    fields: list[str] | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Async get ETF holdings using Bloomberg Query Language (BQL).

    Retrieves holdings information for an ETF including ISIN, weights, and position IDs.

    Args:
        etf_ticker: ETF ticker (e.g., 'SPY US Equity' or 'SPY'). If no suffix is provided,
            ' US Equity' will be appended automatically.
        fields: Optional list of additional fields to retrieve. Default fields are
            id_isin, weights, and id().position. If provided, these will be added to
            the default fields.
        **kwargs: Additional options passed to the underlying BQL query.

    Returns:
        DataFrame with ETF holdings data (type depends on configured backend).
        Columns include: holding (ticker), id_isin, weights, position, and any
        additional requested fields.

    Example::

        import asyncio
        from xbbg.ext.historical import aetf_holdings


        async def main():
            # Get holdings for an ETF
            df = await aetf_holdings("SPY US Equity")

            # Get holdings with additional fields
            df = await aetf_holdings("SPY US Equity", fields=["name", "px_last"])

            # Ticker without suffix (will append ' US Equity')
            df = await aetf_holdings("SPY")

            # Get holdings for a non-US ETF
            df = await aetf_holdings("VWRL LN Equity")


        asyncio.run(main())
    """
    from xbbg import abql
    from xbbg._core import ext_rename_etf_columns

    # Normalize ticker format - ensure it has proper suffix
    if " " not in etf_ticker:
        etf_ticker = f"{etf_ticker} US Equity"

    # Default fields
    default_fields = ["id_isin", "weights", "id().position"]

    # Combine default fields with any additional fields
    if fields:
        all_fields = default_fields + [f for f in fields if f not in default_fields]
    else:
        all_fields = default_fields

    # Build BQL query - format: get(fields) for(holdings('TICKER'))
    fields_str = ", ".join(all_fields)
    bql_query = f"get({fields_str}) for(holdings('{etf_ticker}'))"

    # Execute BQL query - returns DataFrame in configured backend format
    df = await abql(bql_query, **kwargs)

    # Convert to narwhals for manipulation
    nw_df = nw.from_native(df)

    if len(nw_df) == 0:
        return df

    # Get column rename mapping from Rust
    rename_pairs = ext_rename_etf_columns(list(nw_df.columns))

    # Also handle special BQL columns
    rename_map = {old: new for old, new in rename_pairs}
    if "id().position" in nw_df.columns:
        rename_map["id().position"] = "position"
    if "ID" in nw_df.columns:
        rename_map["ID"] = "holding"

    if rename_map:
        nw_df = nw_df.rename(rename_map)
        return nw_df.to_native()

    return df


# =============================================================================
# Sync wrappers
# =============================================================================


def dividend(
    tickers: str | list[str],
    typ: str = "all",
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Get dividend and split history for securities.

    Sync wrapper for adividend(). See adividend() for full documentation.

    Example::

        from xbbg import ext

        # Get all dividend history
        df = ext.dividend("AAPL US Equity")

        # Get only splits
        df = ext.dividend("TSLA US Equity", typ="split")
    """
    return asyncio.run(adividend(tickers=tickers, typ=typ, start_date=start_date, end_date=end_date, **kwargs))


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

    Sync wrapper for aearning(). See aearning() for full documentation.

    Example::

        from xbbg import ext

        # Get geographic revenue breakdown
        df = ext.earning("AMD US Equity", by="Geo")

        # Get product revenue breakdown for specific year
        df = ext.earning("AAPL US Equity", by="Product", year=2023)
    """
    return asyncio.run(
        aearning(ticker=ticker, by=by, typ=typ, ccy=ccy, level=level, year=year, periods=periods, **kwargs)
    )


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

    Sync wrapper for aturnover(). See aturnover() for full documentation.

    Example::

        from xbbg import ext

        # Get turnover in millions USD
        df = ext.turnover(["AAPL US Equity", "MSFT US Equity"], start_date="2024-01-01")

        # Get turnover in local currency
        df = ext.turnover("7203 JP Equity", ccy="local")
    """
    return asyncio.run(
        aturnover(tickers=tickers, start_date=start_date, end_date=end_date, ccy=ccy, factor=factor, **kwargs)
    )


def etf_holdings(
    etf_ticker: str,
    *,
    fields: list[str] | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Get ETF holdings using Bloomberg Query Language (BQL).

    Sync wrapper for aetf_holdings(). See aetf_holdings() for full documentation.

    Example::

        from xbbg import ext

        # Get holdings for an ETF
        df = ext.etf_holdings("SPY US Equity")

        # Get holdings with additional fields
        df = ext.etf_holdings("SPY US Equity", fields=["name", "px_last"])
    """
    return asyncio.run(aetf_holdings(etf_ticker=etf_ticker, fields=fields, **kwargs))

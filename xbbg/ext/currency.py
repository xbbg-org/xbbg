"""Currency adjustment utilities.

This module provides currency conversion functionality for Bloomberg data.
"""

from __future__ import annotations

from typing import Any

import narwhals as nw
import pyarrow as pa

from xbbg.backend import Backend, Format
from xbbg.io.convert import _convert_backend, is_empty
from xbbg.options import get_backend

__all__ = ["adjust_ccy"]


def adjust_ccy(
    data: Any,
    ccy: str = "USD",
    *,
    backend: Backend | None = None,
) -> Any:
    """Adjust series to a target currency.

    This is a general utility function that can be used with any time-series DataFrame
    from historical (bdh), intraday (bdib), or other APIs that return DataFrames with
    date/datetime index and ticker columns.

    Args:
        data: DataFrame with ticker and date columns, plus value columns.
            Can be from bdh, bdib, or any other time-series API in any backend format.
            Expects SEMI_LONG format: ticker, date, field1, field2, ...
        ccy: currency to adjust to (default: 'USD'). Use 'local' for no adjustment.
        backend: Output backend. Defaults to input format or global setting.

    Returns:
        Currency-adjusted data in the requested backend format.

    Examples:
        >>> from xbbg import blp  # doctest: +SKIP
        >>> # Works with historical data in SEMI_LONG format
        >>> hist_data = blp.bdh("AAPL US Equity", "px_last", "2024-01-01", format=Format.SEMI_LONG)  # doctest: +SKIP
        >>> adjusted = blp.adjust_ccy(hist_data, ccy="EUR")  # doctest: +SKIP
    """
    from xbbg.api.historical import bdh
    from xbbg.api.reference import bdp

    if is_empty(data):
        actual_backend = backend if backend is not None else get_backend()
        return _convert_backend(nw.from_native(pa.table({})), actual_backend)

    if ccy.lower() == "local":
        # No adjustment needed - return as-is in requested backend
        actual_backend = backend if backend is not None else get_backend()
        nw_frame = nw.from_native(data, eager_only=True)
        return _convert_backend(nw_frame, actual_backend)

    # Convert input to narwhals
    nw_frame = nw.from_native(data, eager_only=True)
    columns = nw_frame.columns

    # Detect ticker and date columns
    ticker_col = "ticker" if "ticker" in columns else columns[0]
    date_col = "date" if "date" in columns else columns[1]
    value_cols = [c for c in columns if c not in (ticker_col, date_col)]

    # Get unique tickers
    tickers = nw_frame.get_column(ticker_col).unique().to_list()

    # Get date range
    dates = nw_frame.get_column(date_col)
    start_date = dates.min()
    end_date = dates.max()

    # Get currency for each ticker
    uccy = bdp(tickers=tickers, flds="crncy", backend=Backend.NARWHALS, format=Format.SEMI_LONG)

    if is_empty(uccy):
        # No currency info - return original data
        actual_backend = backend if backend is not None else get_backend()
        return _convert_backend(nw_frame, actual_backend)

    # Build FX pair mapping: ticker -> {ccy_pair, factor}
    # factor is 100 for currencies like GBp (pence)
    # Use vectorized operations instead of row iteration
    uccy_nw = nw.from_native(uccy, eager_only=True)

    # Extract ticker and currency columns
    ticker_col_name = ticker_col if ticker_col in uccy_nw.columns else "ticker"
    ccy_col_name = "value" if "value" in uccy_nw.columns else "crncy"

    # Build mapping with vectorized operations
    uccy_data = uccy_nw.select([ticker_col_name, ccy_col_name]).to_native()
    fx_mapping = {}
    fx_tickers_needed = set()

    for row in uccy_data.to_pylist():
        ticker = row.get(ticker_col_name)
        currency = row.get(ccy_col_name)
        if currency and ticker:
            currency = str(currency).upper()
            if currency != ccy.upper():
                # Need FX conversion
                factor = 100.0 if currency[-1].islower() else 1.0
                currency = currency.upper()
                fx_pair = f"{ccy.upper()}{currency} Curncy"
                fx_mapping[ticker] = {"ccy_pair": fx_pair, "factor": factor}
                fx_tickers_needed.add(fx_pair)

    if not fx_tickers_needed:
        # All tickers already in target currency
        actual_backend = backend if backend is not None else get_backend()
        return _convert_backend(nw_frame, actual_backend)

    # Get FX rates
    fx_data = bdh(
        tickers=list(fx_tickers_needed),
        flds="PX_LAST",
        start_date=start_date,
        end_date=end_date,
        backend=Backend.NARWHALS,
        format=Format.SEMI_LONG,
    )

    if is_empty(fx_data):
        # No FX data available - return original
        actual_backend = backend if backend is not None else get_backend()
        return _convert_backend(nw_frame, actual_backend)

    # Build FX lookup: (date, fx_pair) -> rate
    # Use vectorized operations instead of row iteration
    fx_data_nw = nw.from_native(fx_data, eager_only=True)

    # Normalize column names
    fx_ticker_col = "ticker" if "ticker" in fx_data_nw.columns else fx_data_nw.columns[0]
    fx_date_col = "date" if "date" in fx_data_nw.columns else fx_data_nw.columns[1]
    fx_rate_col = None
    for col in ["PX_LAST", "px_last", "value"]:
        if col in fx_data_nw.columns:
            fx_rate_col = col
            break

    if fx_rate_col is None:
        fx_rate_col = fx_data_nw.columns[-1]

    # Build lookup dict from vectorized data
    fx_lookup = {}
    fx_data_list = fx_data_nw.select([fx_ticker_col, fx_date_col, fx_rate_col]).to_native().to_pylist()
    for row in fx_data_list:
        fx_ticker = row.get(fx_ticker_col)
        date_val = row.get(fx_date_col)
        rate = row.get(fx_rate_col)
        if fx_ticker and date_val and rate:
            fx_lookup[(str(date_val), fx_ticker)] = float(rate)

    # Apply currency adjustment using vectorized operations
    # Build a mapping dataframe for FX info
    fx_info_data = []
    for ticker, info in fx_mapping.items():
        fx_info_data.append(
            {
                ticker_col: ticker,
                "fx_pair": info["ccy_pair"],
                "factor": info["factor"],
            }
        )

    if fx_info_data:
        fx_info_table = pa.Table.from_pylist(fx_info_data)
        fx_info_nw = nw.from_native(fx_info_table, eager_only=True)

        # Join data with FX info
        result = nw_frame.join(fx_info_nw, on=ticker_col, how="left")

        # Build FX rates dataframe from lookup
        fx_rates_data = []
        for (date_str, fx_pair), rate in fx_lookup.items():
            fx_rates_data.append(
                {
                    date_col: date_str,
                    "fx_pair": fx_pair,
                    "fx_rate": rate,
                }
            )

        if fx_rates_data:
            fx_rates_table = pa.Table.from_pylist(fx_rates_data)
            fx_rates_nw = nw.from_native(fx_rates_table, eager_only=True)

            # Join with FX rates
            result = result.join(fx_rates_nw, on=[date_col, "fx_pair"], how="left")

            # Fill missing FX rates with 1.0 and missing factors with 1.0
            result = result.with_columns(
                [
                    nw.col("fx_rate").fill_null(1.0).alias("fx_rate"),
                    nw.col("factor").fill_null(1.0).alias("factor"),
                ]
            )

            # Apply adjustment: divide value columns by (fx_rate * factor)
            # Only adjust where fx_pair is not null (ticker had FX mapping)
            adjustment_exprs = []
            for col in value_cols:
                if col in result.columns:
                    # Use coalesce to handle nulls: if fx_pair is null, keep original value
                    adjustment_exprs.append(
                        (nw.col(col) / (nw.col("fx_rate") * nw.col("factor"))).fill_null(nw.col(col)).alias(col)
                    )

            if adjustment_exprs:
                result = result.with_columns(adjustment_exprs)

            # Drop temporary columns
            cols_to_keep = [ticker_col, date_col] + value_cols
            result = result.select([c for c in cols_to_keep if c in result.columns])
        else:
            # No FX rates available, return original
            result = nw_frame
    else:
        # No FX mapping needed, return original
        result = nw_frame

    result_nw = result

    actual_backend = backend if backend is not None else get_backend()
    return _convert_backend(result_nw, actual_backend)

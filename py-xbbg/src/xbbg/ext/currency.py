"""Currency conversion extension functions.

Functions for converting Bloomberg data between currencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import narwhals.stable.v1 as nw

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


def adjust_ccy(
    data: IntoDataFrame,
    ccy: str = "USD",
    **kwargs,
) -> nw.DataFrame:
    """Adjust DataFrame values to a target currency.

    Converts price/value columns in a time-series DataFrame to the specified
    currency using Bloomberg FX rates.

    Args:
        data: DataFrame with date index and ticker columns (from bdh, bdib, etc.).
            Expected to have a 'date' column and value columns.
            Accepts any DataFrame type supported by narwhals.
        ccy: Target currency code (default: "USD"). Use "local" for no adjustment.
        **kwargs: Additional arguments passed to bdp/bdh for FX lookup.

    Returns:
        DataFrame with currency-adjusted values (same type as input).

    Example::

        from xbbg import bdh, ext

        # Get historical data in local currency
        df = bdh("VOD LN Equity", "PX_LAST", "2024-01-01", "2024-01-10")

        # Convert to USD
        df_usd = ext.adjust_ccy(df, ccy="USD")

        # Convert to EUR
        df_eur = ext.adjust_ccy(df, ccy="EUR")
    """
    from xbbg import bdh, bdp

    # Convert to narwhals DataFrame
    nw_df = nw.from_native(data)

    if len(nw_df) == 0:
        return nw_df.to_native()

    if ccy.lower() == "local":
        return nw_df.to_native()

    # Get list of tickers from column names
    # Columns are typically: date, ticker1|field, ticker2|field, ...
    # Or in long format: date, ticker, field, value
    value_cols = [c for c in nw_df.columns if c not in ("date", "ticker", "field")]

    if not value_cols:
        return nw_df.to_native()

    # Try to extract tickers from column names
    tickers = []
    for col in value_cols:
        if "|" in col:
            ticker = col.split("|")[0]
            if ticker not in tickers:
                tickers.append(ticker)
        elif col not in ("value", "value_str", "value_f64", "value_i64"):
            # Column name might be the ticker itself
            tickers.append(col)

    if not tickers:
        # Can't determine tickers, return as-is
        return nw_df.to_native()

    # Get currency for each ticker
    try:
        ccy_data = bdp(tickers=tickers, flds="crncy", **kwargs)
        ccy_nw = nw.from_native(ccy_data)
    except Exception:
        return nw_df.to_native()

    if len(ccy_nw) == 0 or "crncy" not in ccy_nw.columns:
        return nw_df.to_native()

    # Build FX pair mapping
    # ticker -> {ccy_pair: "USDGBP Curncy", factor: 1.0 or 100.0}
    fx_info: dict[str, dict] = {}
    fx_pairs_needed: set[str] = set()

    for row in ccy_nw.iter_rows(named=True):
        ticker = row.get("ticker", "")
        local_ccy = row.get("crncy", "")

        if not local_ccy or local_ccy.upper() == ccy.upper():
            # Same currency, no conversion needed
            continue

        # Determine FX pair
        # Factor handles GBp (pence) vs GBP
        factor = 100.0 if local_ccy[-1].islower() else 1.0
        local_ccy_upper = local_ccy.upper()

        # FX pair format: TARGETLOCAL Curncy (e.g., USDGBP Curncy for GBP -> USD)
        fx_pair = f"{ccy.upper()}{local_ccy_upper} Curncy"

        fx_info[ticker] = {"ccy_pair": fx_pair, "factor": factor}
        fx_pairs_needed.add(fx_pair)

    if not fx_pairs_needed:
        # All tickers already in target currency
        return nw_df.to_native()

    # Get FX rates for the date range
    if "date" in nw_df.columns:
        dates = nw_df["date"].to_list()
        start_date = min(dates) if dates else None
        end_date = max(dates) if dates else None
    else:
        start_date = None
        end_date = None

    if start_date and end_date:
        try:
            fx_data = bdh(
                tickers=list(fx_pairs_needed),
                flds="PX_LAST",
                start_date=start_date,
                end_date=end_date,
                **kwargs,
            )
            fx_nw = nw.from_native(fx_data)
        except Exception:
            return nw_df.to_native()
    else:
        # No date range, can't get FX history
        return nw_df.to_native()

    if len(fx_nw) == 0:
        return nw_df.to_native()

    # Apply conversion
    result = nw_df

    for ticker, info in fx_info.items():
        fx_pair = info["ccy_pair"]
        factor = info["factor"]

        # Find the FX column
        fx_col = None
        for col in fx_nw.columns:
            if fx_pair in col:
                fx_col = col
                break

        if fx_col is None:
            continue

        # Find the ticker column(s) to adjust
        for col in value_cols:
            if ticker in col and "date" in result.columns and "date" in fx_nw.columns:
                # Join FX data and apply conversion
                result = result.join(
                    fx_nw.select(["date", fx_col]).rename({fx_col: f"_fx_{ticker}"}),
                    on="date",
                    how="left",
                )
                # Apply conversion: value / (fx_rate * factor)
                result = result.with_columns((nw.col(col) / (nw.col(f"_fx_{ticker}") * factor)).alias(col))
                # Drop temporary FX column
                result = result.drop(f"_fx_{ticker}")

    return result.to_native()

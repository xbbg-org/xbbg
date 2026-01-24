"""Fixed income extension functions.

Convenience wrappers for fixed income and bond analysis queries.
Returns DataFrame in the configured backend format.
Uses high-performance Rust utilities from xbbg._core.

Sync functions (wrap async with asyncio.run):
    - yas(): Yield & Spread Analysis
    - preferreds(): Find preferred stocks for a company
    - corporate_bonds(): Find corporate bonds for a company
    - bqr(): Bloomberg Quote Request (dealer quotes)

Async functions (primary implementation):
    - ayas(): Async yield & spread analysis
    - apreferreds(): Async find preferred stocks
    - acorporate_bonds(): Async find corporate bonds
    - abqr(): Async Bloomberg Quote Request
"""

from __future__ import annotations

import asyncio
from datetime import date
from enum import IntEnum
from typing import TYPE_CHECKING

# Import Rust ext utilities for max performance
from xbbg._core import (
    ext_fmt_date,
    ext_normalize_tickers,
    ext_parse_date,
)

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


class YieldType(IntEnum):
    """Bloomberg YAS yield type flags for YAS_YLD_FLAG override.

    These values control which yield calculation method Bloomberg uses
    in Yield & Spread Analysis (YAS) calculations.

    Values validated against Bloomberg Terminal YAS<GO> function.

    Standard Bloomberg YAS_YLD_FLAG values:
        1 = Yield to Maturity (YTM) - Default, assumes bond held to maturity
        2 = Yield to Call (YTC) - Assumes bond called at first call date
        3 = Yield to Refunding (YTR) - Assumes bond refunded at first refunding date
        4 = Yield to Next Put (YTP) - Yield to next put date
        5 = Yield to Worst (YTW) - Worst of next put, call, or maturity
        6 = Yield to Worst Refunding (YTWR) - Worst of maturity, refunding, or next put
        7 = Euro Yield to Worst (EYTW) - Euro worst of maturity, next call, or put
        8 = Euro Yield to Worst Refunding (EYTWR) - Euro worst of YTWR
        9 = Yield to Average Life (YTAL) - Yield to average life at maturity

    Note: Not all yield types apply to all bonds. For example:
        - YTC only applies to callable bonds
        - YTP only applies to putable bonds
        - YTR only applies to refundable bonds
        - Euro variants (7, 8) use Euro conventions for yield calculation
    """

    YTM = 1  # Yield to Maturity
    YTC = 2  # Yield to Call
    YTR = 3  # Yield to Refunding
    YTP = 4  # Yield to Next Put
    YTW = 5  # Yield to Worst (next put, call, or maturity)
    YTWR = 6  # Yield to Worst Refunding (maturity, refunding, or next put)
    EYTW = 7  # Euro Yield to Worst (maturity, next call, or put)
    EYTWR = 8  # Euro Yield to Worst Refunding
    YTAL = 9  # Yield to Average Life at Maturity

    @classmethod
    def from_name(cls, name: str) -> "YieldType":
        """Get YieldType from name string (case-insensitive).

        Args:
            name: Yield type name (e.g., "YTM", "ytm", "Yield to Maturity")

        Returns:
            YieldType enum value

        Raises:
            ValueError: If name is not recognized

        Example::

            >>> YieldType.from_name("YTM")
            <YieldType.YTM: 1>
            >>> YieldType.from_name("yield to worst")
            <YieldType.YTW: 3>
        """
        name_upper = name.upper().strip()

        # Direct enum name match
        try:
            return cls[name_upper]
        except KeyError:
            pass

        # Full name mapping
        name_map = {
            "YIELD TO MATURITY": cls.YTM,
            "YIELD TO CALL": cls.YTC,
            "YIELD TO REFUNDING": cls.YTR,
            "YIELD TO PUT": cls.YTP,
            "YIELD TO NEXT PUT": cls.YTP,
            "YIELD TO WORST": cls.YTW,
            "YIELD TO WORST REFUNDING": cls.YTWR,
            "EURO YIELD TO WORST": cls.EYTW,
            "EURO YIELD TO WORST REFUNDING": cls.EYTWR,
            "YIELD TO AVERAGE LIFE": cls.YTAL,
        }

        if name_upper in name_map:
            return name_map[name_upper]

        raise ValueError(f"Unknown yield type: {name!r}. Valid names: {list(cls.__members__.keys())}")

    @property
    def description(self) -> str:
        """Human-readable description of the yield type."""
        descriptions = {
            self.YTM: "Yield to Maturity - assumes bond held to maturity",
            self.YTC: "Yield to Call - assumes bond called at first call date",
            self.YTR: "Yield to Refunding - assumes bond refunded at first refunding date",
            self.YTP: "Yield to Next Put - yield to next put date",
            self.YTW: "Yield to Worst - worst of next put, call, or maturity",
            self.YTWR: "Yield to Worst Refunding - worst of maturity, refunding, or next put",
            self.EYTW: "Euro Yield to Worst - Euro worst of maturity, next call, or put",
            self.EYTWR: "Euro Yield to Worst Refunding - Euro worst of YTWR",
            self.YTAL: "Yield to Average Life - yield to average life at maturity",
        }
        return descriptions.get(self, f"Yield type {self.value}")


def _normalize_tickers(tickers: str | list[str]) -> list[str]:
    """Normalize tickers to a list using Rust."""
    # ext_normalize_tickers expects a list, so wrap single string
    if isinstance(tickers, str):
        return ext_normalize_tickers([tickers])
    return ext_normalize_tickers(tickers)


def _fmt_date(dt: str | date | None, fmt: str = "%Y%m%d") -> str | None:
    """Format date to string using Rust."""
    if dt is None:
        return None
    if isinstance(dt, str):
        # Parse and reformat using Rust
        try:
            year, month, day = ext_parse_date(dt)
            return ext_fmt_date(year, month, day, fmt)
        except ValueError:
            return dt  # Return as-is if can't parse
    # datetime or date object
    if hasattr(dt, "year"):
        return ext_fmt_date(dt.year, dt.month, dt.day, fmt)
    return None


# =============================================================================
# Async implementations (primary)
# =============================================================================


async def ayas(
    tickers: str | list[str],
    flds: str | list[str] = "YAS_BOND_YLD",
    *,
    settle_dt: str | date | None = None,
    yield_type: YieldType | int | None = None,
    spread: float | None = None,
    yield_: float | None = None,
    price: float | None = None,
    benchmark: str | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Async yield and spread analysis for fixed income securities.

    Convenience wrapper around abdp() for Bloomberg's YAS (Yield & Spread Analysis).
    Maps named parameters to Bloomberg YAS override fields.

    Args:
        tickers: Single ticker or list of bond tickers.
        flds: Field(s) to retrieve. Common YAS fields:
            - YAS_BOND_YLD: Calculated yield
            - YAS_YLD_SPREAD: Spread to benchmark
            - YAS_BOND_PX: Calculated price
            - YAS_ASSET_SWP_SPD: Asset swap spread
            - YAS_MOD_DUR: Modified duration
            - YAS_ISPREAD: I-spread
            - YAS_ZSPREAD: Z-spread
            - YAS_OAS: Option-adjusted spread
        settle_dt: Settlement date for the calculation. Default: spot settlement.
        yield_type: Type of yield calculation. Use YieldType enum or int:
            - YieldType.YTM (1): Yield to Maturity
            - YieldType.YTC (2): Yield to Call
            - YieldType.YTR (3): Yield to Refunding
            - YieldType.YTP (4): Yield to Next Put
            - YieldType.YTW (5): Yield to Worst (next put, call, or maturity)
            - YieldType.YTWR (6): Yield to Worst Refunding
            - YieldType.EYTW (7): Euro Yield to Worst
            - YieldType.EYTWR (8): Euro Yield to Worst Refunding
            - YieldType.YTAL (9): Yield to Average Life
        spread: Input spread value (for reverse calculation from spread to price/yield).
        yield_: Input yield value (for reverse calculation from yield to price).
        price: Input price value (for reverse calculation from price to yield/spread).
        benchmark: Benchmark security for spread calculation (e.g., "T 4.5 05/15/38 Govt").
        **kwargs: Additional arguments passed to abdp().

    Returns:
        DataFrame with yield analysis data (type depends on configured backend).

    Example::

        import asyncio
        from xbbg.ext.fixed_income import ayas, YieldType


        async def main():
            # Get yield to maturity for a bond
            df = await ayas("US912810TM69 Govt", "YAS_BOND_YLD")

            # Get multiple YAS fields
            df = await ayas(
                "US912810TM69 Govt",
                ["YAS_BOND_YLD", "YAS_MOD_DUR", "YAS_ZSPREAD"],
            )

            # Calculate price from yield
            df = await ayas(
                "US912810TM69 Govt",
                "YAS_BOND_PX",
                yield_=4.5,
                yield_type=YieldType.YTM,
            )


        asyncio.run(main())
    """
    from xbbg import abdp

    tickers_list = _normalize_tickers(tickers)

    # Normalize fields
    if isinstance(flds, str):
        fields_list = [flds]
    else:
        fields_list = list(flds)

    # Build overrides from named parameters
    overrides: dict[str, str] = {}

    if settle_dt is not None:
        formatted = _fmt_date(settle_dt)
        if formatted:
            overrides["YAS_SETTLE_DT"] = formatted

    if yield_type is not None:
        overrides["YAS_YLD_FLAG"] = str(int(yield_type))

    if spread is not None:
        overrides["YAS_YLD_SPREAD"] = str(spread)

    if yield_ is not None:
        overrides["YAS_BOND_YLD"] = str(yield_)

    if price is not None:
        overrides["YAS_BOND_PX"] = str(price)

    if benchmark is not None:
        overrides["YAS_BNCHMRK_BOND"] = benchmark

    # Merge with any additional overrides from kwargs
    if "overrides" in kwargs:
        existing = kwargs.pop("overrides")
        if isinstance(existing, dict):
            overrides.update(existing)
        elif isinstance(existing, list):
            for k, v in existing:
                overrides[k] = str(v)

    # Call abdp with the overrides
    return await abdp(tickers=tickers_list, flds=fields_list, overrides=overrides, **kwargs)


async def apreferreds(
    equity_ticker: str,
    *,
    fields: list[str] | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Async find preferred stocks for a company using BQL.

    Uses Bloomberg's debt filter to find preferred stock issues
    associated with a given equity ticker.

    Args:
        equity_ticker: Company equity ticker (e.g., "BAC US Equity" or "BAC").
            If no suffix is provided, " US Equity" will be appended.
        fields: Optional list of additional fields to retrieve.
            Default fields are: id, name.
        **kwargs: Additional options passed to the underlying BQL query.

    Returns:
        DataFrame with preferred stock information (type depends on configured backend).
        Columns include the security ID, name, and any additional requested fields.

    Example::

        import asyncio
        from xbbg.ext.fixed_income import apreferreds


        async def main():
            # Get preferred stocks for Bank of America
            df = await apreferreds("BAC US Equity")

            # Get preferreds with additional fields
            df = await apreferreds("BAC", fields=["px_last", "dvd_yld"])


        asyncio.run(main())
    """
    from xbbg import abql

    # Normalize ticker format
    if " " not in equity_ticker:
        equity_ticker = f"{equity_ticker} US Equity"

    # Build field list
    default_fields = ["id", "name"]
    if fields:
        all_fields = default_fields + [f for f in fields if f.lower() not in [df.lower() for df in default_fields]]
    else:
        all_fields = default_fields

    fields_str = ", ".join(all_fields)

    # Build BQL query using debt filter with Preferreds asset class
    bql_query = (
        f"get({fields_str}) "
        f"for(filter(debt(['{equity_ticker}'], CONSOLIDATEDUPLICATES='N'), "
        f"SRCH_ASSET_CLASS=='Preferreds'))"
    )

    return await abql(bql_query, **kwargs)


async def acorporate_bonds(
    ticker: str,
    *,
    ccy: str | None = "USD",
    fields: list[str] | None = None,
    active_only: bool = True,
    **kwargs,
) -> IntoDataFrame:
    """Async find corporate bonds for a company using BQL.

    Uses Bloomberg's bondsuniv filter to find active corporate bond issues
    for a given company ticker.

    Args:
        ticker: Company ticker without suffix (e.g., "AAPL", "MSFT").
            This is the Bloomberg ticker prefix used to match bonds.
        ccy: Currency filter (default: "USD"). Set to None for all currencies.
        fields: Optional list of additional fields to retrieve.
            Default field is: id.
        active_only: If True (default), only return active bonds.
        **kwargs: Additional options passed to the underlying BQL query.

    Returns:
        DataFrame with corporate bond information (type depends on configured backend).
        Columns include the security ID and any additional requested fields.

    Example::

        import asyncio
        from xbbg.ext.fixed_income import acorporate_bonds


        async def main():
            # Get active USD corporate bonds for Apple
            df = await acorporate_bonds("AAPL")

            # Get all currency bonds with additional fields
            df = await acorporate_bonds("MSFT", ccy=None, fields=["name", "cpn", "maturity"])


        asyncio.run(main())
    """
    from xbbg import abql

    # Build field list
    default_fields = ["id"]
    if fields:
        all_fields = default_fields + [f for f in fields if f.lower() not in [df.lower() for df in default_fields]]
    else:
        all_fields = default_fields

    fields_str = ", ".join(all_fields)

    # Build filter conditions
    conditions = ["SRCH_ASSET_CLASS=='Corporates'", f"TICKER=='{ticker}'"]

    if ccy is not None:
        conditions.append(f"CRNCY=='{ccy}'")

    filter_str = " AND ".join(conditions)

    # Build BQL query using bondsuniv filter
    universe = "active" if active_only else "all"
    bql_query = f"get({fields_str}) for(filter(bondsuniv('{universe}', CONSOLIDATEDUPLICATES='N'), {filter_str}))"

    return await abql(bql_query, **kwargs)


async def abqr(
    ticker: str,
    *,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    event_types: list[str] | None = None,
    include_broker_codes: bool = True,
    **kwargs,
) -> IntoDataFrame:
    """Async Bloomberg Quote Request (dealer quotes).

    Retrieves intraday tick data with broker/dealer codes for a security.
    This is useful for analyzing dealer activity and market making.

    Note: Broker code data availability depends on your Bloomberg entitlements
    and the security type. Not all securities have broker attribution.

    Args:
        ticker: Security ticker (e.g., "US912810TM69 Govt").
        start_datetime: Start datetime (ISO format or "YYYY-MM-DD HH:MM").
            Default: 1 hour ago.
        end_datetime: End datetime (ISO format or "YYYY-MM-DD HH:MM").
            Default: now.
        event_types: List of event types to retrieve (default: ["BID", "ASK"]).
            Options: "TRADE", "BID", "ASK", "BID_BEST", "ASK_BEST", etc.
        include_broker_codes: Whether to include broker/dealer codes (default: True).
        **kwargs: Additional options passed to abdtick.

    Returns:
        DataFrame with quote data including broker codes (if available).
        Columns typically include: time, type, value, size, and broker codes.

    Example::

        import asyncio
        from xbbg.ext.fixed_income import abqr


        async def main():
            # Get dealer quotes for a government bond
            df = await abqr("US912810TM69 Govt")

            # Get quotes for specific time range
            df = await abqr(
                "US912810TM69 Govt",
                start_datetime="2024-01-15 09:00",
                end_datetime="2024-01-15 10:00",
            )


        asyncio.run(main())
    """
    from datetime import datetime, timedelta

    from xbbg import abdtick

    # Default time range: last hour
    if end_datetime is None:
        end_dt = datetime.now()
        end_datetime = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        # Normalize datetime format
        end_datetime = end_datetime.replace(" ", "T")
        if "T" in end_datetime and len(end_datetime) == 16:  # YYYY-MM-DDTHH:MM
            end_datetime += ":00"

    if start_datetime is None:
        # Default to 1 hour before end
        if isinstance(end_datetime, str):
            try:
                end_dt = datetime.fromisoformat(end_datetime)
            except ValueError:
                end_dt = datetime.now()
        else:
            end_dt = end_datetime
        start_dt = end_dt - timedelta(hours=1)
        start_datetime = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        # Normalize datetime format
        start_datetime = start_datetime.replace(" ", "T")
        if "T" in start_datetime and len(start_datetime) == 16:  # YYYY-MM-DDTHH:MM
            start_datetime += ":00"

    # Default event types
    if event_types is None:
        event_types = ["BID", "ASK"]

    # Add broker code request to kwargs if desired
    if include_broker_codes:
        kwargs["includeBrokerCodes"] = True

    # Use abdtick to get the data
    return await abdtick(
        ticker=ticker,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        **kwargs,
    )


# =============================================================================
# Sync wrappers
# =============================================================================


def yas(
    tickers: str | list[str],
    flds: str | list[str] = "YAS_BOND_YLD",
    *,
    settle_dt: str | date | None = None,
    yield_type: YieldType | int | None = None,
    spread: float | None = None,
    yield_: float | None = None,
    price: float | None = None,
    benchmark: str | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Get yield and spread analysis for fixed income securities.

    Sync wrapper for ayas(). See ayas() for full documentation.

    Example::

        from xbbg import ext
        from xbbg.ext.fixed_income import YieldType

        # Get yield to maturity for a bond
        df = ext.yas("US912810TM69 Govt", "YAS_BOND_YLD")

        # Calculate price from yield
        df = ext.yas(
            "US912810TM69 Govt",
            "YAS_BOND_PX",
            yield_=4.5,
            yield_type=YieldType.YTM,
        )
    """
    return asyncio.run(
        ayas(
            tickers=tickers,
            flds=flds,
            settle_dt=settle_dt,
            yield_type=yield_type,
            spread=spread,
            yield_=yield_,
            price=price,
            benchmark=benchmark,
            **kwargs,
        )
    )


def preferreds(
    equity_ticker: str,
    *,
    fields: list[str] | None = None,
    **kwargs,
) -> IntoDataFrame:
    """Find preferred stocks for a company using BQL.

    Sync wrapper for apreferreds(). See apreferreds() for full documentation.

    Example::

        from xbbg import ext

        # Get preferred stocks for Bank of America
        df = ext.preferreds("BAC US Equity")
    """
    return asyncio.run(apreferreds(equity_ticker=equity_ticker, fields=fields, **kwargs))


def corporate_bonds(
    ticker: str,
    *,
    ccy: str | None = "USD",
    fields: list[str] | None = None,
    active_only: bool = True,
    **kwargs,
) -> IntoDataFrame:
    """Find corporate bonds for a company using BQL.

    Sync wrapper for acorporate_bonds(). See acorporate_bonds() for full documentation.

    Example::

        from xbbg import ext

        # Get active USD corporate bonds for Apple
        df = ext.corporate_bonds("AAPL")
    """
    return asyncio.run(acorporate_bonds(ticker=ticker, ccy=ccy, fields=fields, active_only=active_only, **kwargs))


def bqr(
    ticker: str,
    *,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    event_types: list[str] | None = None,
    include_broker_codes: bool = True,
    **kwargs,
) -> IntoDataFrame:
    """Get dealer quotes with broker attribution (Bloomberg Quote Request).

    Sync wrapper for abqr(). See abqr() for full documentation.

    Example::

        from xbbg import ext

        # Get dealer quotes for a government bond
        df = ext.bqr("US912810TM69 Govt")
    """
    return asyncio.run(
        abqr(
            ticker=ticker,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            event_types=event_types,
            include_broker_codes=include_broker_codes,
            **kwargs,
        )
    )

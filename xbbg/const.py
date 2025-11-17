"""Constants and configuration mappings for xbbg.

This module contains all constant definitions used throughout the package.
Market-related utility functions have been moved to xbbg.markets.info.
"""

from dataclasses import dataclass

from xbbg.io import files

# Package path
PKG_PATH = files.abspath(__file__, 0)

# Futures month codes
Futures = {
    'Jan': 'F', 'Feb': 'G', 'Mar': 'H', 'Apr': 'J', 'May': 'K', 'Jun': 'M',
    'Jul': 'N', 'Aug': 'Q', 'Sep': 'U', 'Oct': 'V', 'Nov': 'X', 'Dec': 'Z',
}


@dataclass(frozen=True)
class CurrencyPair:
    """Currency pair configuration."""
    ticker: str
    factor: float
    power: float

# Valid market sessions
ValidSessions = ['allday', 'day', 'am', 'pm', 'night', 'pre', 'post']

# Asset configuration mapping
ASSET_INFO = {
    'Index': ['tickers'],
    'Comdty': ['tickers', 'key_month'],
    'Curncy': ['tickers'],
    'Equity': ['exch_codes'],
}

# Dividend type mappings
DVD_TPYES = {
    'all': 'DVD_Hist_All',
    'dvd': 'DVD_Hist',
    'split': 'Eqy_DVD_Hist_Splits',
    'gross': 'Eqy_DVD_Hist_Gross',
    'adjust': 'Eqy_DVD_Adjust_Fact',
    'adj_fund': 'Eqy_DVD_Adj_Fund',
    'with_amt': 'DVD_Hist_All_with_Amt_Status',
    'dvd_amt': 'DVD_Hist_with_Amt_Status',
    'gross_amt': 'DVD_Hist_Gross_with_Amt_Stat',
    'projected': 'BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann',
}

# Dividend column name mappings
DVD_COLS = {
    'Declared Date': 'dec_date',
    'Ex-Date': 'ex_date',
    'Record Date': 'rec_date',
    'Payable Date': 'pay_date',
    'Dividend Amount': 'dvd_amt',
    'Dividend Frequency': 'dvd_freq',
    'Dividend Type': 'dvd_type',
    'Amount Status': 'amt_status',
    'Adjustment Date': 'adj_date',
    'Adjustment Factor': 'adj_factor',
    'Adjustment Factor Operator Type': 'adj_op',
    'Adjustment Factor Flag': 'adj_flag',
    'Amount Per Share': 'amt_ps',
    'Projected/Confirmed': 'category',
}

# Real-time data fields of interest
LIVE_INFO = {
    # Common fields
    'MKTDATA_EVENT_TYPE', 'MKTDATA_EVENT_SUBTYPE', 'IS_DELAYED_STREAM',
    # Last Price
    'LAST_PRICE', 'RT_PX_CHG_PCT_1D', 'REALTIME_PERCENT_BID_ASK_SPREAD',
    'EVT_TRADE_DATE_RT', 'TRADE_UPDATE_STAMP_RT',
    'EQY_TURNOVER_REALTIME', 'VOLUME',
    # Bid
    'BID', 'BID_UPDATE_STAMP_RT',
    # Ask
    'ASK', 'ASK_UPDATE_STAMP_RT',
    # Common in bid / ask
    'SPREAD_BA', 'MID',
}

# Real-time change percentage fields
LIVE_CHG = {
    'RT_PX_CHG_PCT_1D', 'CHG_PCT_1M_RT', 'CHG_PCT_3M_RT',
    'CHG_PCT_MTD_RT', 'CHG_PCT_QTD_RT', 'CHG_PCT_YTD_RT',
    'REALTIME_2_DAY_CHANGE_PERCENT', 'REALTIME_5_DAY_CHANGE_PERCENT',
    'REALTIME_15_SEC_PRICE_PCT_CHG', 'REALTIME_ONE_MIN_PRICE_PCT_CHG',
    # Equities only
    'REALTIME_FIVE_MIN_PRICE_PCT_CHG', 'REALTIME_15_MIN_PRICE_PCT_CHG',
    'REALTIME_ONE_HOUR_PRICE_PCT_CHG',
}

# Real-time volume fields
LIVE_VOL = {
    'REALTIME_VOLUME_5_DAY_INTERVAL',
    # Real-time current volume as % change from N-day avg volume
    'DELTA_AVAT_1_DAY_INTERVAL', 'DELTA_AVAT_5_DAY_INTERVAL',
    'DELTA_AVAT_10_DAY_INTERVAL', 'DELTA_AVAT_20_DAY_INTERVAL',
    'DELTA_AVAT_30_DAY_INTERVAL', 'DELTA_AVAT_100_DAY_INTERVAL',
    'DELTA_AVAT_180_DAY_INTERVAL',
    # Real-time turnover as % change from N-day average turnover
    'DELTA_ATAT_1_DAY_INTERVAL', 'DELTA_ATAT_5_DAY_INTERVAL',
    'DELTA_ATAT_10_DAY_INTERVAL', 'DELTA_ATAT_20_DAY_INTERVAL',
    'DELTA_ATAT_30_DAY_INTERVAL', 'DELTA_ATAT_100_DAY_INTERVAL',
    'DELTA_ATAT_180_DAY_INTERVAL',
}

# Real-time ratio fields
LIVE_RATIO = {
    'PRICE_EARNINGS_RATIO_RT', 'PRICE_TO_BOOK_RATIO_RT',
    'PRICE_TO_SALES_RATIO_RT', 'PRICE_CASH_FLOW_RT', 'PRICE_EBITDA_RT',
}

# Re-export market info functions for backward compatibility
# Use providers internally for better testability
from xbbg.markets.info import (  # noqa: E402
    asset_config,
    ccy_pair,
    exch_info,
    market_info,
    market_timing,
)

__all__ = [
    'ASSET_INFO',
    'CurrencyPair',
    'DVD_COLS',
    'DVD_TPYES',
    'Futures',
    'LIVE_CHG',
    'LIVE_INFO',
    'LIVE_RATIO',
    'LIVE_VOL',
    'PKG_PATH',
    'ValidSessions',
    # Re-exported functions for backward compatibility
    'asset_config',
    'ccy_pair',
    'exch_info',
    'market_info',
    'market_timing',
]

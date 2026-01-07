"""Constants for xbbg extensions.

This module contains mappings and configurations used by extension functions.
"""

from __future__ import annotations

# Futures month codes (Bloomberg standard)
FUTURES_MONTHS: dict[str, str] = {
    "Jan": "F",
    "Feb": "G",
    "Mar": "H",
    "Apr": "J",
    "May": "K",
    "Jun": "M",
    "Jul": "N",
    "Aug": "Q",
    "Sep": "U",
    "Oct": "V",
    "Nov": "X",
    "Dec": "Z",
}

# Reverse mapping: code -> month name
MONTH_CODES: dict[str, str] = {v: k for k, v in FUTURES_MONTHS.items()}

# Dividend type mappings for dividend()
DVD_TYPES: dict[str, str] = {
    "all": "DVD_Hist_All",
    "dvd": "DVD_Hist",
    "split": "Eqy_DVD_Hist_Splits",
    "gross": "Eqy_DVD_Hist_Gross",
    "adjust": "Eqy_DVD_Adjust_Fact",
    "adj_fund": "Eqy_DVD_Adj_Fund",
    "with_amt": "DVD_Hist_All_with_Amt_Status",
    "dvd_amt": "DVD_Hist_with_Amt_Status",
    "gross_amt": "DVD_Hist_Gross_with_Amt_Stat",
    "projected": "BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann",
}

# Dividend column name mappings (Bloomberg -> clean names)
DVD_COLS: dict[str, str] = {
    "Declared Date": "dec_date",
    "Ex-Date": "ex_date",
    "Record Date": "rec_date",
    "Payable Date": "pay_date",
    "Dividend Amount": "dvd_amt",
    "Dividend Frequency": "dvd_freq",
    "Dividend Type": "dvd_type",
    "Amount Status": "amt_status",
    "Adjustment Date": "adj_date",
    "Adjustment Factor": "adj_factor",
    "Adjustment Factor Operator Type": "adj_op",
    "Adjustment Factor Flag": "adj_flag",
    "Amount Per Share": "amt_ps",
    "Projected/Confirmed": "category",
}

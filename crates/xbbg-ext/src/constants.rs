//! Compile-time constant maps for Bloomberg data.
//!
//! Uses `phf` for zero-cost lookups at runtime.

use phf::phf_map;

/// Futures month codes (Bloomberg standard).
///
/// Maps month name abbreviation to single-letter code.
/// Example: "Mar" -> "H"
pub static FUTURES_MONTHS: phf::Map<&'static str, &'static str> = phf_map! {
    "Jan" => "F",
    "Feb" => "G",
    "Mar" => "H",
    "Apr" => "J",
    "May" => "K",
    "Jun" => "M",
    "Jul" => "N",
    "Aug" => "Q",
    "Sep" => "U",
    "Oct" => "V",
    "Nov" => "X",
    "Dec" => "Z",
};

/// Reverse mapping: month code to month name.
///
/// Example: "H" -> "Mar"
pub static MONTH_CODES: phf::Map<&'static str, &'static str> = phf_map! {
    "F" => "Jan",
    "G" => "Feb",
    "H" => "Mar",
    "J" => "Apr",
    "K" => "May",
    "M" => "Jun",
    "N" => "Jul",
    "Q" => "Aug",
    "U" => "Sep",
    "V" => "Oct",
    "X" => "Nov",
    "Z" => "Dec",
};

/// Month code to month number (1-12).
pub static MONTH_CODE_TO_NUM: phf::Map<&'static str, u32> = phf_map! {
    "F" => 1,
    "G" => 2,
    "H" => 3,
    "J" => 4,
    "K" => 5,
    "M" => 6,
    "N" => 7,
    "Q" => 8,
    "U" => 9,
    "V" => 10,
    "X" => 11,
    "Z" => 12,
};

/// Month number to month code.
pub static MONTH_NUM_TO_CODE: phf::Map<u32, &'static str> = phf_map! {
    1u32 => "F",
    2u32 => "G",
    3u32 => "H",
    4u32 => "J",
    5u32 => "K",
    6u32 => "M",
    7u32 => "N",
    8u32 => "Q",
    9u32 => "U",
    10u32 => "V",
    11u32 => "X",
    12u32 => "Z",
};

/// Dividend type mappings for `dividend()`.
///
/// Maps user-friendly type name to Bloomberg field name.
pub static DVD_TYPES: phf::Map<&'static str, &'static str> = phf_map! {
    "all" => "DVD_Hist_All",
    "dvd" => "DVD_Hist",
    "split" => "Eqy_DVD_Hist_Splits",
    "gross" => "Eqy_DVD_Hist_Gross",
    "adjust" => "Eqy_DVD_Adjust_Fact",
    "adj_fund" => "Eqy_DVD_Adj_Fund",
    "with_amt" => "DVD_Hist_All_with_Amt_Status",
    "dvd_amt" => "DVD_Hist_with_Amt_Status",
    "gross_amt" => "DVD_Hist_Gross_with_Amt_Stat",
    "projected" => "BDVD_Pr_Ex_Dts_DVD_Amts_w_Ann",
};

/// Dividend column name mappings (Bloomberg -> clean names).
pub static DVD_COLS: phf::Map<&'static str, &'static str> = phf_map! {
    "Declared Date" => "dec_date",
    "Ex-Date" => "ex_date",
    "Record Date" => "rec_date",
    "Payable Date" => "pay_date",
    "Dividend Amount" => "dvd_amt",
    "Dividend Frequency" => "dvd_freq",
    "Dividend Type" => "dvd_type",
    "Amount Status" => "amt_status",
    "Adjustment Date" => "adj_date",
    "Adjustment Factor" => "adj_factor",
    "Adjustment Factor Operator Type" => "adj_op",
    "Adjustment Factor Flag" => "adj_flag",
    "Amount Per Share" => "amt_ps",
    "Projected/Confirmed" => "category",
};

/// ETF holdings column name mappings (Bloomberg -> clean names).
pub static ETF_COLS: phf::Map<&'static str, &'static str> = phf_map! {
    "Holding Name" => "name",
    "Holding Ticker" => "ticker",
    "Holding ISIN" => "isin",
    "Holding Sedol" => "sedol",
    "Holding CUSIP" => "cusip",
    "Shares Held" => "shares",
    "Market Value" => "mkt_val",
    "Weight" => "weight",
    "% Weight" => "weight",
    "Sector" => "sector",
    "Country" => "country",
    "Asset Class" => "asset_class",
    "Currency" => "ccy",
    "Coupon" => "coupon",
    "Maturity" => "maturity",
};

/// Set of valid futures month codes for validation.
pub const VALID_MONTH_CODES: &[char] =
    &['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'];

/// Quarterly futures months (Mar, Jun, Sep, Dec).
pub const QUARTERLY_MONTHS: &[u32] = &[3, 6, 9, 12];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_futures_months_lookup() {
        assert_eq!(FUTURES_MONTHS.get("Mar"), Some(&"H"));
        assert_eq!(FUTURES_MONTHS.get("Dec"), Some(&"Z"));
        assert_eq!(FUTURES_MONTHS.get("Invalid"), None);
    }

    #[test]
    fn test_month_codes_reverse() {
        assert_eq!(MONTH_CODES.get("H"), Some(&"Mar"));
        assert_eq!(MONTH_CODES.get("Z"), Some(&"Dec"));
    }

    #[test]
    fn test_dvd_types() {
        assert_eq!(DVD_TYPES.get("all"), Some(&"DVD_Hist_All"));
        assert_eq!(DVD_TYPES.get("split"), Some(&"Eqy_DVD_Hist_Splits"));
    }
}

//! Date parsing and formatting utilities.
//!
//! Provides fast date parsing with support for multiple common formats.

use chrono::NaiveDate;

use crate::error::{ExtError, Result};

/// Supported date formats for parsing.
const DATE_FORMATS: &[&str] = &[
    "%Y-%m-%d", // 2024-01-15
    "%Y%m%d",   // 20240115
    "%Y/%m/%d", // 2024/01/15
    "%d-%m-%Y", // 15-01-2024
    "%d/%m/%Y", // 15/01/2024
];

/// Parse a date string into a `NaiveDate`.
///
/// Supports multiple formats:
/// - `YYYY-MM-DD` (ISO 8601)
/// - `YYYYMMDD` (Bloomberg compact)
/// - `YYYY/MM/DD`
/// - `DD-MM-YYYY`
/// - `DD/MM/YYYY`
///
/// # Examples
///
/// ```
/// use xbbg_ext::utils::date::parse_date;
///
/// let d1 = parse_date("2024-01-15").unwrap();
/// let d2 = parse_date("20240115").unwrap();
/// let d3 = parse_date("2024/01/15").unwrap();
///
/// assert_eq!(d1, d2);
/// assert_eq!(d2, d3);
/// ```
///
/// # Errors
///
/// Returns `ExtError::DateParse` if the string doesn't match any supported format.
pub fn parse_date(s: &str) -> Result<NaiveDate> {
    let s = s.trim();

    // Fast path: check length to narrow down formats
    match s.len() {
        8 => {
            // YYYYMMDD format
            if let Ok(d) = NaiveDate::parse_from_str(s, "%Y%m%d") {
                return Ok(d);
            }
        }
        10 => {
            // Most common: YYYY-MM-DD or YYYY/MM/DD
            if s.as_bytes()[4] == b'-' {
                if let Ok(d) = NaiveDate::parse_from_str(s, "%Y-%m-%d") {
                    return Ok(d);
                }
            } else if s.as_bytes()[4] == b'/' {
                if let Ok(d) = NaiveDate::parse_from_str(s, "%Y/%m/%d") {
                    return Ok(d);
                }
            } else if s.as_bytes()[2] == b'-' {
                if let Ok(d) = NaiveDate::parse_from_str(s, "%d-%m-%Y") {
                    return Ok(d);
                }
            } else if s.as_bytes()[2] == b'/' {
                if let Ok(d) = NaiveDate::parse_from_str(s, "%d/%m/%Y") {
                    return Ok(d);
                }
            }
        }
        _ => {}
    }

    // Fallback: try all formats
    for fmt in DATE_FORMATS {
        if let Ok(d) = NaiveDate::parse_from_str(s, fmt) {
            return Ok(d);
        }
    }

    Err(ExtError::DateParse(s.to_string()))
}

/// Format a date to a string.
///
/// # Arguments
///
/// * `date` - The date to format
/// * `fmt` - Optional format string (default: `%Y%m%d` for Bloomberg)
///
/// # Examples
///
/// ```
/// use chrono::NaiveDate;
/// use xbbg_ext::utils::date::fmt_date;
///
/// let d = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
///
/// assert_eq!(fmt_date(d, None), "20240115");
/// assert_eq!(fmt_date(d, Some("%Y-%m-%d")), "2024-01-15");
/// ```
pub fn fmt_date(date: NaiveDate, fmt: Option<&str>) -> String {
    date.format(fmt.unwrap_or("%Y%m%d")).to_string()
}

/// Try to parse a date, returning None if parsing fails.
///
/// Useful when date parsing is optional or for filter operations.
pub fn try_parse_date(s: &str) -> Option<NaiveDate> {
    parse_date(s).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_iso() {
        let d = parse_date("2024-01-15").unwrap();
        assert_eq!(d.year(), 2024);
        assert_eq!(d.month(), 1);
        assert_eq!(d.day(), 15);
    }

    #[test]
    fn test_parse_compact() {
        let d = parse_date("20240115").unwrap();
        assert_eq!(d.year(), 2024);
        assert_eq!(d.month(), 1);
        assert_eq!(d.day(), 15);
    }

    #[test]
    fn test_parse_slash() {
        let d = parse_date("2024/01/15").unwrap();
        assert_eq!(d.year(), 2024);
        assert_eq!(d.month(), 1);
        assert_eq!(d.day(), 15);
    }

    #[test]
    fn test_parse_euro_dash() {
        let d = parse_date("15-01-2024").unwrap();
        assert_eq!(d.year(), 2024);
        assert_eq!(d.month(), 1);
        assert_eq!(d.day(), 15);
    }

    #[test]
    fn test_parse_euro_slash() {
        let d = parse_date("15/01/2024").unwrap();
        assert_eq!(d.year(), 2024);
        assert_eq!(d.month(), 1);
        assert_eq!(d.day(), 15);
    }

    #[test]
    fn test_parse_invalid() {
        assert!(parse_date("not-a-date").is_err());
        assert!(parse_date("").is_err());
        assert!(parse_date("2024").is_err());
    }

    #[test]
    fn test_parse_with_whitespace() {
        let d = parse_date("  2024-01-15  ").unwrap();
        assert_eq!(d.year(), 2024);
    }

    #[test]
    fn test_fmt_date_default() {
        let d = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
        assert_eq!(fmt_date(d, None), "20240115");
    }

    #[test]
    fn test_fmt_date_custom() {
        let d = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
        assert_eq!(fmt_date(d, Some("%Y-%m-%d")), "2024-01-15");
    }

    #[test]
    fn test_all_formats_same_result() {
        let dates = [
            "2024-01-15",
            "20240115",
            "2024/01/15",
            "15-01-2024",
            "15/01/2024",
        ];

        let expected = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
        for s in dates {
            assert_eq!(parse_date(s).unwrap(), expected, "Failed for: {}", s);
        }
    }
}

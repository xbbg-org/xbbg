//! Futures ticker resolution utilities.
//!
//! Provides logic for generating futures contract candidates and resolving
//! generic tickers to specific contracts.

use chrono::{Datelike, NaiveDate};

use crate::constants::{MONTH_NUM_TO_CODE, QUARTERLY_MONTHS};
use crate::error::{ExtError, Result};
use crate::utils::ticker::{is_specific_contract, parse_ticker_parts, TickerParts};

/// Roll frequency for futures contracts.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RollFrequency {
    /// Monthly contracts (all months)
    Monthly,
    /// Quarterly contracts (Mar, Jun, Sep, Dec)
    Quarterly,
}

impl RollFrequency {
    /// Parse from string (e.g., "M", "Q", "QE").
    pub fn from_str(s: &str) -> Self {
        match s.trim().to_uppercase().as_str() {
            "Q" | "QE" => RollFrequency::Quarterly,
            _ => RollFrequency::Monthly,
        }
    }
}

/// A futures contract candidate with its expected month.
#[derive(Debug, Clone)]
pub struct FuturesCandidate {
    /// The ticker string (e.g., "ESH24 Index")
    pub ticker: String,
    /// The contract month
    pub month: NaiveDate,
}

/// Generate futures contract candidates for a given generic ticker and date.
///
/// This generates the list of potential contract tickers that need to be
/// queried from Bloomberg to resolve the correct contract.
///
/// # Arguments
///
/// * `gen_ticker` - Generic futures ticker (e.g., "ES1 Index")
/// * `dt` - Reference date
/// * `freq` - Roll frequency (Monthly or Quarterly)
/// * `count` - Number of candidates to generate
///
/// # Returns
///
/// A vector of `FuturesCandidate` with ticker strings and their contract months.
///
/// # Examples
///
/// ```
/// use chrono::NaiveDate;
/// use xbbg_ext::resolvers::futures::{generate_futures_candidates, RollFrequency};
///
/// let dt = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
/// let candidates = generate_futures_candidates("ES1 Index", dt, RollFrequency::Quarterly, 4).unwrap();
///
/// assert!(!candidates.is_empty());
/// // First candidate should be March 2024 (ESH24 Index)
/// assert!(candidates[0].ticker.contains("H24") || candidates[0].ticker.contains("H4"));
/// ```
pub fn generate_futures_candidates(
    gen_ticker: &str,
    dt: NaiveDate,
    freq: RollFrequency,
    count: usize,
) -> Result<Vec<FuturesCandidate>> {
    // Validate it's a generic ticker
    if is_specific_contract(gen_ticker) {
        return Err(ExtError::SpecificTicker(gen_ticker.to_string()));
    }

    let parts = parse_ticker_parts(gen_ticker)?;

    // Generate contract months
    let months = generate_contract_months(dt, freq, count);

    // Check if we're in the same month as reference date
    let now = chrono::Local::now().naive_local().date();
    let same_month = now.month() == dt.month() && now.year() == dt.year();

    // Build candidate tickers
    let candidates = months
        .into_iter()
        .map(|month| {
            let ticker = build_contract_ticker(&parts, month, same_month);
            FuturesCandidate { ticker, month }
        })
        .collect();

    Ok(candidates)
}

/// Generate contract months starting from a given date.
fn generate_contract_months(start: NaiveDate, freq: RollFrequency, count: usize) -> Vec<NaiveDate> {
    let mut months = Vec::with_capacity(count);
    let mut current = start.with_day(1).unwrap_or(start);

    match freq {
        RollFrequency::Monthly => {
            while months.len() < count {
                months.push(current);
                current = next_month(current);
            }
        }
        RollFrequency::Quarterly => {
            // Find next quarterly month
            while months.len() < count {
                if QUARTERLY_MONTHS.contains(&current.month()) {
                    months.push(current);
                }
                current = next_month(current);
            }
        }
    }

    months
}

/// Get the next month from a date.
fn next_month(date: NaiveDate) -> NaiveDate {
    if date.month() == 12 {
        NaiveDate::from_ymd_opt(date.year() + 1, 1, 1).unwrap()
    } else {
        NaiveDate::from_ymd_opt(date.year(), date.month() + 1, 1).unwrap()
    }
}

/// Build a specific contract ticker from parts and month.
fn build_contract_ticker(parts: &TickerParts, month: NaiveDate, same_month: bool) -> String {
    let month_code = MONTH_NUM_TO_CODE.get(&month.month()).unwrap_or(&"F");
    let year = month.year();

    // Use 1-digit year if same month, otherwise 2-digit
    let year_str = if same_month {
        format!("{}", year % 10)
    } else {
        format!("{:02}", year % 100)
    };

    match parts.asset.as_str() {
        "Equity" => {
            let exchange = parts.exchange.as_deref().unwrap_or("US");
            format!(
                "{}{}{} {} {}",
                parts.prefix, month_code, year_str, exchange, parts.asset
            )
        }
        _ => {
            format!("{}{}{} {}", parts.prefix, month_code, year_str, parts.asset)
        }
    }
}

/// Validate that a ticker is generic (not specific).
///
/// # Errors
///
/// Returns `ExtError::SpecificTicker` if the ticker appears to be a specific contract.
pub fn validate_generic_ticker(ticker: &str) -> Result<()> {
    if is_specific_contract(ticker) {
        Err(ExtError::SpecificTicker(ticker.to_string()))
    } else {
        Ok(())
    }
}

/// Extract the contract index from a generic ticker (e.g., "ES1 Index" -> 1).
///
/// Returns 0-based index (so "ES1" returns 0, "ES2" returns 1).
pub fn contract_index(gen_ticker: &str) -> Result<usize> {
    let parts = parse_ticker_parts(gen_ticker)?;
    Ok((parts.index as usize).saturating_sub(1))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_roll_frequency_parse() {
        assert_eq!(RollFrequency::from_str("M"), RollFrequency::Monthly);
        assert_eq!(RollFrequency::from_str("m"), RollFrequency::Monthly);
        assert_eq!(RollFrequency::from_str("Q"), RollFrequency::Quarterly);
        assert_eq!(RollFrequency::from_str("QE"), RollFrequency::Quarterly);
        assert_eq!(RollFrequency::from_str(""), RollFrequency::Monthly);
    }

    #[test]
    fn test_generate_monthly_candidates() {
        let dt = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
        let candidates =
            generate_futures_candidates("ES1 Index", dt, RollFrequency::Monthly, 3).unwrap();

        assert_eq!(candidates.len(), 3);
        // Should start from January 2024
        assert_eq!(candidates[0].month.month(), 1);
        assert_eq!(candidates[1].month.month(), 2);
        assert_eq!(candidates[2].month.month(), 3);
    }

    #[test]
    fn test_generate_quarterly_candidates() {
        let dt = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
        let candidates =
            generate_futures_candidates("ES1 Index", dt, RollFrequency::Quarterly, 4).unwrap();

        assert_eq!(candidates.len(), 4);
        // Should be Mar, Jun, Sep, Dec
        assert_eq!(candidates[0].month.month(), 3);
        assert_eq!(candidates[1].month.month(), 6);
        assert_eq!(candidates[2].month.month(), 9);
        assert_eq!(candidates[3].month.month(), 12);
    }

    #[test]
    fn test_reject_specific_ticker() {
        let dt = NaiveDate::from_ymd_opt(2024, 1, 15).unwrap();
        let result = generate_futures_candidates("ESH24 Index", dt, RollFrequency::Monthly, 3);
        assert!(result.is_err());
    }

    #[test]
    fn test_contract_index() {
        assert_eq!(contract_index("ES1 Index").unwrap(), 0);
        assert_eq!(contract_index("ES2 Index").unwrap(), 1);
        assert_eq!(contract_index("CL3 Comdty").unwrap(), 2);
    }

    #[test]
    fn test_validate_generic_ticker() {
        assert!(validate_generic_ticker("ES1 Index").is_ok());
        assert!(validate_generic_ticker("ESH24 Index").is_err());
    }
}

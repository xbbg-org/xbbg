//! Error types for xbbg-ext.

use thiserror::Error;

/// Result type alias for xbbg-ext operations.
pub type Result<T> = std::result::Result<T, ExtError>;

/// Errors that can occur in xbbg-ext operations.
#[derive(Debug, Error)]
pub enum ExtError {
    /// Failed to parse a date string.
    #[error("failed to parse date '{0}': expected format YYYY-MM-DD, YYYYMMDD, or YYYY/MM/DD")]
    DateParse(String),

    /// Invalid ticker format.
    #[error("invalid ticker format '{0}': expected 'PREFIX ASSET' (e.g., 'ES1 Index')")]
    InvalidTicker(String),

    /// Ticker appears to be specific rather than generic.
    #[error("'{0}' appears to be a specific contract, not generic. Use generic ticker like 'ES1 Index' instead")]
    SpecificTicker(String),

    /// Unknown dividend type.
    #[error("unknown dividend type '{0}': expected one of: all, dvd, split, gross, adjust, adj_fund, with_amt, dvd_amt, gross_amt, projected")]
    UnknownDividendType(String),

    /// Arrow error during DataFrame operations.
    #[error("arrow error: {0}")]
    Arrow(#[from] arrow::error::ArrowError),

    /// Missing required column in DataFrame.
    #[error("missing required column '{0}'")]
    MissingColumn(String),

    /// Empty data - operation cannot proceed.
    #[error("empty data: {0}")]
    EmptyData(String),
}

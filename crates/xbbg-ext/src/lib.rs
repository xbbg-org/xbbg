//! xbbg-ext: Extension utilities for xbbg
//!
//! This crate provides high-performance Rust implementations of common
//! Bloomberg data transformations and utilities:
//!
//! - **constants**: Compile-time maps for futures months, dividend types, etc.
//! - **utils**: Date parsing, DataFrame pivoting, ticker normalization
//! - **resolvers**: Futures and CDX ticker resolution
//! - **transforms**: Currency adjustment, historical data processing

pub mod constants;
pub mod error;
pub mod resolvers;
pub mod transforms;
pub mod utils;

pub use error::{ExtError, Result};

// Re-export commonly used items
pub use constants::{DVD_COLS, DVD_TYPES, ETF_COLS, FUTURES_MONTHS, MONTH_CODES};
pub use utils::date::{fmt_date, parse_date};
pub use utils::pivot::pivot_to_wide;
pub use utils::ticker::{normalize_tickers, parse_ticker_parts, TickerParts};

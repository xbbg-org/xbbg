//! Ticker resolution utilities for futures and CDX contracts.

pub mod cdx;
pub mod futures;

pub use cdx::{cdx_series_from_ticker, CdxInfo};
pub use futures::{
    filter_valid_contracts, generate_futures_candidates, FuturesCandidate, RollFrequency,
};

//! Typed request descriptors for high-level Bloomberg operations.
//!
//! These are *data-only* structs which describe what the caller wants
//! (tickers, fields, ranges, overrides, etc.). Execution lives in the
//! `arrow` module, which turns these into concrete `blpapi` requests and
//! Arrow tables.

pub mod refdata;
pub mod hist;
pub mod intraday_bars;
pub mod intraday_ticks;
pub mod bulk;
pub mod fields;

pub use refdata::ReferenceDataRequest;
pub use hist::HistoricalDataRequest;
pub use intraday_bars::IntradayBarRequest;
pub use intraday_ticks::IntradayTickRequest;
pub use bulk::BulkDataRequest;
pub use fields::{FieldSearchRequest, FieldInfoRequest};

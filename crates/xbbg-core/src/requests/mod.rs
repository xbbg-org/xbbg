//! Typed request descriptors for high-level Bloomberg operations.
//!
//! These are *data-only* structs which describe what the caller wants
//! (tickers, fields, ranges, overrides, etc.). Execution lives in the
//! `arrow` module, which turns these into concrete `blpapi` requests and
//! Arrow tables.

pub mod bulk;
pub mod fields;
pub mod hist;
pub mod intraday_bars;
pub mod intraday_ticks;
pub mod refdata;

pub use bulk::BulkDataRequest;
pub use fields::{FieldInfoRequest, FieldSearchRequest};
pub use hist::HistoricalDataRequest;
pub use intraday_bars::IntradayBarRequest;
pub use intraday_ticks::IntradayTickRequest;
pub use refdata::ReferenceDataRequest;

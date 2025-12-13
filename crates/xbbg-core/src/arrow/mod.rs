//! Arrow integration for `xbbg-core`.
//!
//! This module defines helpers which execute high-level request types
//! against a `Session` and materialize the results as Arrow
//! `RecordBatch` / `Table` in long format.

pub mod fields_arrow;
pub mod hist_arrow;
pub mod intraday_bars_arrow;
pub mod intraday_ticks_arrow;
pub mod refdata_arrow;

pub use fields_arrow::{execute_field_info_arrow, execute_field_search_arrow};
pub use hist_arrow::execute_histdata_arrow;
pub use intraday_bars_arrow::execute_intraday_bars_arrow;
pub use intraday_ticks_arrow::execute_intraday_ticks_arrow;
pub use refdata_arrow::execute_refdata_arrow;

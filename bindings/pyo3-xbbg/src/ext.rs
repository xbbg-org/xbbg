//! PyO3 bindings for xbbg-ext extension utilities.
//!
//! Exposes high-performance Rust implementations to Python.

use arrow::pyarrow::{FromPyArrow, ToPyArrow};
use arrow::record_batch::RecordBatch;
use chrono::Datelike;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use xbbg_ext::constants::{DVD_TYPES, FUTURES_MONTHS, MONTH_CODES};
use xbbg_ext::resolvers::cdx::{cdx_series_from_ticker, gen_to_specific, previous_series_ticker};
use xbbg_ext::resolvers::futures::{
    contract_index, generate_futures_candidates, validate_generic_ticker, RollFrequency,
};
use xbbg_ext::transforms::currency::{build_fx_pair, currencies_needing_conversion, same_currency};
use xbbg_ext::transforms::historical::{rename_dividend_columns, rename_etf_columns};
use xbbg_ext::utils::date::{fmt_date, parse_date};
use xbbg_ext::utils::pivot::{is_long_format, pivot_to_wide};
use xbbg_ext::utils::ticker::{
    build_futures_ticker, filter_equity_tickers, is_specific_contract, normalize_tickers,
    parse_ticker_parts,
};

// =============================================================================
// Date Utilities
// =============================================================================

/// Parse a date string into components (year, month, day).
///
/// Supports: YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD, DD-MM-YYYY, DD/MM/YYYY
#[pyfunction]
#[pyo3(signature = (date_str))]
fn ext_parse_date(date_str: &str) -> PyResult<(i32, u32, u32)> {
    let d = parse_date(date_str).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((d.year(), d.month(), d.day()))
}

/// Format a date to string.
#[pyfunction]
#[pyo3(signature = (year, month, day, fmt=None))]
fn ext_fmt_date(year: i32, month: u32, day: u32, fmt: Option<&str>) -> PyResult<String> {
    use chrono::NaiveDate;
    let d = NaiveDate::from_ymd_opt(year, month, day).ok_or_else(|| {
        PyValueError::new_err(format!("invalid date: {}-{}-{}", year, month, day))
    })?;
    Ok(fmt_date(d, fmt))
}

// =============================================================================
// Pivot Utilities
// =============================================================================

/// Pivot a PyArrow RecordBatch from long to wide format.
///
/// Input: RecordBatch with columns (ticker, field, value)
/// Output: RecordBatch with columns (ticker, field1, field2, ...)
#[pyfunction]
fn ext_pivot_to_wide(py: Python<'_>, batch: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    // Convert PyArrow to Rust RecordBatch
    let rust_batch = RecordBatch::from_pyarrow_bound(batch)
        .map_err(|e| PyValueError::new_err(format!("invalid RecordBatch: {e}")))?;

    // Pivot
    let result = pivot_to_wide(&rust_batch).map_err(|e| PyValueError::new_err(e.to_string()))?;

    // Convert back to PyArrow
    result
        .to_pyarrow(py)
        .map(|b| b.unbind())
        .map_err(|e| PyValueError::new_err(format!("conversion failed: {e}")))
}

/// Check if a RecordBatch is in long format (ticker, field, value).
#[pyfunction]
fn ext_is_long_format(batch: &Bound<'_, PyAny>) -> PyResult<bool> {
    let rust_batch = RecordBatch::from_pyarrow_bound(batch)
        .map_err(|e| PyValueError::new_err(format!("invalid RecordBatch: {e}")))?;
    Ok(is_long_format(&rust_batch))
}

// =============================================================================
// Ticker Utilities
// =============================================================================

/// Parse a Bloomberg ticker into components.
///
/// Returns: (prefix, index, asset, exchange)
#[pyfunction]
fn ext_parse_ticker(ticker: &str) -> PyResult<(String, u32, String, Option<String>)> {
    let parts = parse_ticker_parts(ticker).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((parts.prefix, parts.index, parts.asset, parts.exchange))
}

/// Check if a ticker is a specific contract (not generic).
#[pyfunction]
fn ext_is_specific_contract(ticker: &str) -> bool {
    is_specific_contract(ticker)
}

/// Build a futures ticker from components.
#[pyfunction]
fn ext_build_futures_ticker(prefix: &str, month_code: &str, year: &str, asset: &str) -> String {
    build_futures_ticker(prefix, month_code, year, asset)
}

/// Normalize tickers to a list.
#[pyfunction]
fn ext_normalize_tickers(tickers: Vec<String>) -> Vec<String> {
    let refs: Vec<&str> = tickers.iter().map(|s| s.as_str()).collect();
    normalize_tickers(&refs)
}

/// Filter to equity tickers only.
#[pyfunction]
fn ext_filter_equity_tickers(tickers: Vec<String>) -> Vec<String> {
    let refs: Vec<&str> = tickers.iter().map(|s| s.as_str()).collect();
    filter_equity_tickers(&refs)
}

// =============================================================================
// Futures Resolution
// =============================================================================

/// Generate futures contract candidates.
///
/// Returns list of (ticker, year, month) tuples.
#[pyfunction]
#[pyo3(signature = (gen_ticker, year, month, day, freq="M", count=4))]
fn ext_generate_futures_candidates(
    gen_ticker: &str,
    year: i32,
    month: u32,
    day: u32,
    freq: &str,
    count: usize,
) -> PyResult<Vec<(String, i32, u32)>> {
    use chrono::NaiveDate;

    let dt = NaiveDate::from_ymd_opt(year, month, day).ok_or_else(|| {
        PyValueError::new_err(format!("invalid date: {}-{}-{}", year, month, day))
    })?;

    let roll_freq = RollFrequency::from_str(freq);

    let candidates = generate_futures_candidates(gen_ticker, dt, roll_freq, count)
        .map_err(|e| PyValueError::new_err(e.to_string()))?;

    Ok(candidates
        .into_iter()
        .map(|c| (c.ticker, c.month.year(), c.month.month()))
        .collect())
}

/// Validate that a ticker is generic (not specific).
#[pyfunction]
fn ext_validate_generic_ticker(ticker: &str) -> PyResult<()> {
    validate_generic_ticker(ticker).map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Get the contract index from a generic ticker (0-based).
#[pyfunction]
fn ext_contract_index(gen_ticker: &str) -> PyResult<usize> {
    contract_index(gen_ticker).map_err(|e| PyValueError::new_err(e.to_string()))
}

// =============================================================================
// CDX Resolution
// =============================================================================

/// Parse a CDX ticker.
///
/// Returns: (index, series, tenor, asset, is_generic, series_num)
#[pyfunction]
fn ext_parse_cdx_ticker(
    ticker: &str,
) -> PyResult<(String, String, String, String, bool, Option<u32>)> {
    let info = cdx_series_from_ticker(ticker).map_err(|e| PyValueError::new_err(e.to_string()))?;
    Ok((
        info.index,
        info.series,
        info.tenor,
        info.asset,
        info.is_generic,
        info.series_num,
    ))
}

/// Get the previous series ticker for a CDX index.
#[pyfunction]
fn ext_previous_cdx_series(ticker: &str) -> PyResult<Option<String>> {
    previous_series_ticker(ticker).map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Convert a generic CDX ticker to specific series.
#[pyfunction]
fn ext_cdx_gen_to_specific(gen_ticker: &str, series: u32) -> PyResult<String> {
    gen_to_specific(gen_ticker, series).map_err(|e| PyValueError::new_err(e.to_string()))
}

// =============================================================================
// Currency Utilities
// =============================================================================

/// Build an FX pair ticker for currency conversion.
///
/// Returns: (fx_pair, factor, from_ccy, to_ccy)
#[pyfunction]
fn ext_build_fx_pair(from_ccy: &str, to_ccy: &str) -> (String, f64, String, String) {
    let info = build_fx_pair(from_ccy, to_ccy);
    (info.fx_pair, info.factor, info.from_ccy, info.to_ccy)
}

/// Check if two currencies are effectively the same.
#[pyfunction]
fn ext_same_currency(ccy1: &str, ccy2: &str) -> bool {
    same_currency(ccy1, ccy2)
}

/// Get currencies that need FX conversion.
#[pyfunction]
fn ext_currencies_needing_conversion(currencies: Vec<String>, target: &str) -> Vec<String> {
    let refs: Vec<&str> = currencies.iter().map(|s| s.as_str()).collect();
    currencies_needing_conversion(&refs, target)
}

// =============================================================================
// Column Renaming
// =============================================================================

/// Get dividend column rename mapping.
#[pyfunction]
fn ext_rename_dividend_columns(columns: Vec<String>) -> Vec<(String, String)> {
    let refs: Vec<&str> = columns.iter().map(|s| s.as_str()).collect();
    rename_dividend_columns(&refs)
}

/// Get ETF holdings column rename mapping.
#[pyfunction]
fn ext_rename_etf_columns(columns: Vec<String>) -> Vec<(String, String)> {
    let refs: Vec<&str> = columns.iter().map(|s| s.as_str()).collect();
    rename_etf_columns(&refs)
}

// =============================================================================
// Constants
// =============================================================================

/// Get futures month code for a month name.
#[pyfunction]
fn ext_get_month_code(month: &str) -> Option<String> {
    FUTURES_MONTHS.get(month).map(|s| s.to_string())
}

/// Get month name for a futures month code.
#[pyfunction]
fn ext_get_month_name(code: &str) -> Option<String> {
    MONTH_CODES.get(code).map(|s| s.to_string())
}

/// Get all futures month mappings.
#[pyfunction]
fn ext_get_futures_months(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    for (k, v) in FUTURES_MONTHS.entries() {
        dict.set_item(*k, *v)?;
    }
    Ok(dict)
}

/// Get dividend type field name.
#[pyfunction]
fn ext_get_dvd_type(typ: &str) -> Option<String> {
    DVD_TYPES.get(typ).map(|s| s.to_string())
}

/// Get all dividend type mappings.
#[pyfunction]
fn ext_get_dvd_types(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    for (k, v) in DVD_TYPES.entries() {
        dict.set_item(*k, *v)?;
    }
    Ok(dict)
}

// =============================================================================
// Module Registration
// =============================================================================

/// Register ext functions with the module.
pub fn register_ext_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Date utilities
    m.add_function(wrap_pyfunction!(ext_parse_date, m)?)?;
    m.add_function(wrap_pyfunction!(ext_fmt_date, m)?)?;

    // Pivot utilities
    m.add_function(wrap_pyfunction!(ext_pivot_to_wide, m)?)?;
    m.add_function(wrap_pyfunction!(ext_is_long_format, m)?)?;

    // Ticker utilities
    m.add_function(wrap_pyfunction!(ext_parse_ticker, m)?)?;
    m.add_function(wrap_pyfunction!(ext_is_specific_contract, m)?)?;
    m.add_function(wrap_pyfunction!(ext_build_futures_ticker, m)?)?;
    m.add_function(wrap_pyfunction!(ext_normalize_tickers, m)?)?;
    m.add_function(wrap_pyfunction!(ext_filter_equity_tickers, m)?)?;

    // Futures resolution
    m.add_function(wrap_pyfunction!(ext_generate_futures_candidates, m)?)?;
    m.add_function(wrap_pyfunction!(ext_validate_generic_ticker, m)?)?;
    m.add_function(wrap_pyfunction!(ext_contract_index, m)?)?;

    // CDX resolution
    m.add_function(wrap_pyfunction!(ext_parse_cdx_ticker, m)?)?;
    m.add_function(wrap_pyfunction!(ext_previous_cdx_series, m)?)?;
    m.add_function(wrap_pyfunction!(ext_cdx_gen_to_specific, m)?)?;

    // Currency utilities
    m.add_function(wrap_pyfunction!(ext_build_fx_pair, m)?)?;
    m.add_function(wrap_pyfunction!(ext_same_currency, m)?)?;
    m.add_function(wrap_pyfunction!(ext_currencies_needing_conversion, m)?)?;

    // Column renaming
    m.add_function(wrap_pyfunction!(ext_rename_dividend_columns, m)?)?;
    m.add_function(wrap_pyfunction!(ext_rename_etf_columns, m)?)?;

    // Constants
    m.add_function(wrap_pyfunction!(ext_get_month_code, m)?)?;
    m.add_function(wrap_pyfunction!(ext_get_month_name, m)?)?;
    m.add_function(wrap_pyfunction!(ext_get_futures_months, m)?)?;
    m.add_function(wrap_pyfunction!(ext_get_dvd_type, m)?)?;
    m.add_function(wrap_pyfunction!(ext_get_dvd_types, m)?)?;

    Ok(())
}

//! PyO3 bindings for xbbg-recipes high-level Bloomberg workflows.
//!
//! Exposes all 12 recipe functions to Python via `#[pyfunction]` wrappers.
//! Each function follows the same pattern:
//!
//! 1. Clone `Arc<Engine>` from the `PyEngine` wrapper
//! 2. Schedule async work via `future_into_py`
//! 3. Call the Rust recipe function
//! 4. Convert the resulting `RecordBatch` to PyArrow via zero-copy FFI

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use xbbg_ext::transforms::fixed_income::YieldType;

use crate::{record_batch_to_pyarrow, PyEngine};

/// Convert a RecipeError to a Python RuntimeError.
fn recipe_err(e: xbbg_recipes::RecipeError) -> PyErr {
    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
}

// =============================================================================
// Fixed Income Recipes
// =============================================================================

/// YAS (Yield & Spread Analysis) recipe.
///
/// Retrieves Bloomberg YAS data with optional yield type and pricing parameters.
/// Returns a PyArrow RecordBatch.
///
/// Args:
///     engine: Bloomberg engine instance
///     tickers: Securities to query
///     fields: Fields to retrieve
///     settle_dt: Settlement date (YYYYMMDD format)
///     yield_type: Yield calculation type as integer (1=YTM, 2=YTC, ..., 9=YTAL)
///     spread: Yield spread override
///     yield_val: Yield value override
///     price: Price override
///     benchmark: Benchmark security for spread calculation
#[pyfunction]
#[pyo3(signature = (engine, tickers, fields, settle_dt=None, yield_type=None, spread=None, yield_val=None, price=None, benchmark=None))]
#[allow(clippy::too_many_arguments)]
fn recipe_yas<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    tickers: Vec<String>,
    fields: Vec<String>,
    settle_dt: Option<String>,
    yield_type: Option<u8>,
    spread: Option<f64>,
    yield_val: Option<f64>,
    price: Option<f64>,
    benchmark: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();
    let yt = yield_type.and_then(|y| YieldType::try_from(y).ok());

    future_into_py(py, async move {
        let batch = xbbg_recipes::fixed_income::recipe_yas(
            &eng, tickers, fields, settle_dt, yt, spread, yield_val, price, benchmark,
        )
        .await
        .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Find preferred stocks for a company via BQL.
///
/// Args:
///     engine: Bloomberg engine instance
///     ticker: Company equity ticker (e.g., "BAC US Equity")
///     fields: Additional fields to retrieve (default: id, name)
#[pyfunction]
#[pyo3(signature = (engine, ticker, fields=None))]
fn recipe_preferreds<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    ticker: String,
    fields: Option<Vec<String>>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::fixed_income::recipe_preferreds(&eng, ticker, fields)
            .await
            .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Find corporate bonds for a company via BQL.
///
/// Args:
///     engine: Bloomberg engine instance
///     ticker: Company ticker prefix (e.g., "AAPL")
///     ccy: Currency filter (e.g., "USD"). None for all currencies.
///     fields: Additional fields to retrieve (default: id)
///     active_only: If true, only return active bonds (default: true)
#[pyfunction]
#[pyo3(signature = (engine, ticker, ccy=None, fields=None, active_only=true))]
fn recipe_corporate_bonds<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    ticker: String,
    ccy: Option<String>,
    fields: Option<Vec<String>>,
    active_only: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::fixed_income::recipe_corporate_bonds(
            &eng,
            ticker,
            ccy,
            fields,
            active_only,
        )
        .await
        .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Bloomberg Quote Request — dealer quotes via IntradayTick.
///
/// Args:
///     engine: Bloomberg engine instance
///     ticker: Security ticker (e.g., "US912810TM69 Govt")
///     start_datetime: Start datetime (ISO format)
///     end_datetime: End datetime (ISO format)
///     event_types: Event types to retrieve (default: ["BID", "ASK"])
///     include_broker_codes: Include broker/dealer codes (default: true)
#[pyfunction]
#[pyo3(signature = (engine, ticker, start_datetime, end_datetime, event_types=None, include_broker_codes=true))]
fn recipe_bqr<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    ticker: String,
    start_datetime: String,
    end_datetime: String,
    event_types: Option<Vec<String>>,
    include_broker_codes: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::fixed_income::recipe_bqr(
            &eng,
            ticker,
            start_datetime,
            end_datetime,
            event_types,
            include_broker_codes,
        )
        .await
        .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

// =============================================================================
// Futures / CDX Recipes
// =============================================================================

/// Resolve a generic futures ticker to a specific contract ticker.
///
/// Args:
///     engine: Bloomberg engine instance
///     gen_ticker: Generic futures ticker (e.g., "ES1 Index", "CL2 Comdty")
///     dt: Reference date (YYYYMMDD format)
///     freq: Roll frequency ("M" monthly, "Q"/"QE" quarterly)
#[pyfunction]
#[pyo3(signature = (engine, gen_ticker, dt, freq=None))]
fn recipe_fut_ticker<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    gen_ticker: String,
    dt: String,
    freq: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::futures::recipe_fut_ticker(&eng, gen_ticker, dt, freq)
            .await
            .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Resolve the most active futures contract around a reference date.
///
/// Args:
///     engine: Bloomberg engine instance
///     gen_ticker: Generic futures ticker (e.g., "ES1 Index")
///     dt: Reference date (YYYYMMDD format)
///     freq: Roll frequency ("M" monthly, "Q"/"QE" quarterly)
#[pyfunction]
#[pyo3(signature = (engine, gen_ticker, dt, freq=None))]
fn recipe_active_futures<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    gen_ticker: String,
    dt: String,
    freq: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::futures::recipe_active_futures(&eng, gen_ticker, dt, freq)
            .await
            .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Resolve a generic CDX ticker to the active specific series.
///
/// Args:
///     engine: Bloomberg engine instance
///     gen_ticker: Generic CDX ticker (e.g., "CDX IG CDSI GEN 5Y Corp")
///     dt: Reference date (YYYYMMDD format)
#[pyfunction]
#[pyo3(signature = (engine, gen_ticker, dt))]
fn recipe_cdx_ticker<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    gen_ticker: String,
    dt: String,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::futures::recipe_cdx_ticker(&eng, gen_ticker, dt)
            .await
            .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Resolve the most active CDX series around a reference date.
///
/// Args:
///     engine: Bloomberg engine instance
///     gen_ticker: Generic CDX ticker (e.g., "CDX IG CDSI GEN 5Y Corp")
///     dt: Reference date (YYYYMMDD format)
///     lookback_days: Lookback window for activity comparison (default: 10)
#[pyfunction]
#[pyo3(signature = (engine, gen_ticker, dt, lookback_days=None))]
fn recipe_active_cdx<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    gen_ticker: String,
    dt: String,
    lookback_days: Option<i32>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::futures::recipe_active_cdx(&eng, gen_ticker, dt, lookback_days)
            .await
            .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

// =============================================================================
// Historical Recipes
// =============================================================================

/// Fetch dividend history for securities.
///
/// Args:
///     engine: Bloomberg engine instance
///     tickers: Securities to query
///     start_date: Start date (YYYYMMDD format)
///     end_date: End date (YYYYMMDD format)
///     dvd_type: Dividend type filter (e.g., "all", "regular")
#[pyfunction]
#[pyo3(signature = (engine, tickers, start_date, end_date, dvd_type=None))]
fn recipe_dividend<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    tickers: Vec<String>,
    start_date: String,
    end_date: String,
    dvd_type: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::historical::recipe_dividend(
            &eng, tickers, dvd_type, start_date, end_date,
        )
        .await
        .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Fetch trading volume and turnover for securities.
///
/// Args:
///     engine: Bloomberg engine instance
///     tickers: Securities to query
///     start_date: Start date (YYYYMMDD format)
///     end_date: End date (YYYYMMDD format)
///     ccy: Currency for conversion. None for local currency.
///     factor: Division factor (e.g., 1_000_000.0 for millions)
#[pyfunction]
#[pyo3(signature = (engine, tickers, start_date, end_date, ccy=None, factor=None))]
fn recipe_turnover<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    tickers: Vec<String>,
    start_date: String,
    end_date: String,
    ccy: Option<String>,
    factor: Option<f64>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::historical::recipe_turnover(
            &eng, tickers, start_date, end_date, ccy, factor,
        )
        .await
        .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

/// Fetch ETF constituent holdings via BQL.
///
/// Args:
///     engine: Bloomberg engine instance
///     etf_ticker: ETF ticker (e.g., "SPY US Equity")
///     fields: Additional fields beyond defaults (id_isin, weights, id().position)
#[pyfunction]
#[pyo3(signature = (engine, etf_ticker, fields=None))]
fn recipe_etf_holdings<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    etf_ticker: String,
    fields: Option<Vec<String>>,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::historical::recipe_etf_holdings(&eng, etf_ticker, fields)
            .await
            .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

// =============================================================================
// Currency Recipes
// =============================================================================

/// Fetch historical prices with currency conversion.
///
/// Args:
///     engine: Bloomberg engine instance
///     ticker: Security ticker
///     target_ccy: Target currency (e.g., "USD", "EUR")
///     start_date: Start date (YYYYMMDD format)
///     end_date: End date (YYYYMMDD format)
#[pyfunction]
#[pyo3(signature = (engine, ticker, target_ccy, start_date, end_date))]
fn recipe_currency_conversion<'py>(
    py: Python<'py>,
    engine: &PyEngine,
    ticker: String,
    target_ccy: String,
    start_date: String,
    end_date: String,
) -> PyResult<Bound<'py, PyAny>> {
    let eng = engine.engine.clone();

    future_into_py(py, async move {
        let batch = xbbg_recipes::currency::recipe_currency_conversion(
            &eng, ticker, target_ccy, start_date, end_date,
        )
        .await
        .map_err(recipe_err)?;

        Python::attach(|py| record_batch_to_pyarrow(py, batch))
    })
}

// =============================================================================
// Module Registration
// =============================================================================

/// Register all recipe functions with the Python module.
pub fn register_recipes_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Fixed income
    m.add_function(wrap_pyfunction!(recipe_yas, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_preferreds, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_corporate_bonds, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_bqr, m)?)?;

    // Futures / CDX
    m.add_function(wrap_pyfunction!(recipe_fut_ticker, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_active_futures, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_cdx_ticker, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_active_cdx, m)?)?;

    // Historical
    m.add_function(wrap_pyfunction!(recipe_dividend, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_turnover, m)?)?;
    m.add_function(wrap_pyfunction!(recipe_etf_holdings, m)?)?;

    // Currency
    m.add_function(wrap_pyfunction!(recipe_currency_conversion, m)?)?;

    Ok(())
}

//! PyO3 bindings for xbbg-recipes high-level Bloomberg workflows.
//!
//! Exposes all 12 recipe functions to Python via `#[pyfunction]` wrappers.

use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use xbbg_ext::transforms::fixed_income::YieldType;

use crate::{record_batch_to_pyarrow, PyEngine};

/// Convert a RecipeError to a Python RuntimeError.
fn recipe_err(e: xbbg_recipes::RecipeError) -> PyErr {
    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
}

macro_rules! recipe_wrapper {
    (
        $(#[$meta:meta])*
        |$eng:ident|
        fn $name:ident($($arg:ident : $arg_ty:ty),* $(,)?)
        $(prepare { $($prepare:tt)* })?
        => $call:expr
    ) => {
        $(#[$meta])*
        fn $name<'py>(
            py: Python<'py>,
            engine: &PyEngine,
            $($arg: $arg_ty),*
        ) -> PyResult<Bound<'py, PyAny>> {
            let $eng = engine.engine.clone();
            $($($prepare)*)?

            future_into_py(py, async move {
                let batch = $call.await.map_err(recipe_err)?;
                Python::attach(|py| record_batch_to_pyarrow(py, batch))
            })
        }
    };
}

macro_rules! register_pyfunctions {
    ($module:expr; $($func:ident),+ $(,)?) => {{
        $( $module.add_function(wrap_pyfunction!($func, $module)?)?; )+
        Ok(())
    }};
}

// =============================================================================
// Fixed Income Recipes
// =============================================================================

recipe_wrapper!(
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
    |eng|
    fn recipe_yas(
        tickers: Vec<String>,
        fields: Vec<String>,
        settle_dt: Option<String>,
        yield_type: Option<u8>,
        spread: Option<f64>,
        yield_val: Option<f64>,
        price: Option<f64>,
        benchmark: Option<String>,
    )
    prepare {
        let yt = yield_type.and_then(|y| YieldType::try_from(y).ok());
    }
    => xbbg_recipes::fixed_income::recipe_yas(
        &eng,
        tickers,
        fields,
        settle_dt,
        yt,
        spread,
        yield_val,
        price,
        benchmark,
    )
);

recipe_wrapper!(
    /// Find preferred stocks for a company via BQL.
    ///
    /// Args:
    ///     engine: Bloomberg engine instance
    ///     ticker: Company equity ticker (e.g., "BAC US Equity")
    ///     fields: Additional fields to retrieve (default: id, name)
    #[pyfunction]
    #[pyo3(signature = (engine, ticker, fields=None))]
    |eng|
    fn recipe_preferreds(
        ticker: String,
        fields: Option<Vec<String>>,
    ) => xbbg_recipes::fixed_income::recipe_preferreds(&eng, ticker, fields)
);

recipe_wrapper!(
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
    |eng|
    fn recipe_corporate_bonds(
        ticker: String,
        ccy: Option<String>,
        fields: Option<Vec<String>>,
        active_only: bool,
    ) => xbbg_recipes::fixed_income::recipe_corporate_bonds(
        &eng,
        ticker,
        ccy,
        fields,
        active_only,
    )
);

recipe_wrapper!(
    /// Bloomberg Quote Request - dealer quotes via IntradayTick.
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
    |eng|
    fn recipe_bqr(
        ticker: String,
        start_datetime: String,
        end_datetime: String,
        event_types: Option<Vec<String>>,
        include_broker_codes: bool,
    ) => xbbg_recipes::fixed_income::recipe_bqr(
        &eng,
        ticker,
        start_datetime,
        end_datetime,
        event_types,
        include_broker_codes,
    )
);

// =============================================================================
// Futures / CDX Recipes
// =============================================================================

recipe_wrapper!(
    /// Resolve a generic futures ticker to a specific contract ticker.
    ///
    /// Args:
    ///     engine: Bloomberg engine instance
    ///     gen_ticker: Generic futures ticker (e.g., "ES1 Index", "CL2 Comdty")
    ///     dt: Reference date (YYYYMMDD format)
    ///     freq: Roll frequency ("M" monthly, "Q"/"QE" quarterly)
    #[pyfunction]
    #[pyo3(signature = (engine, gen_ticker, dt, freq=None))]
    |eng|
    fn recipe_fut_ticker(
        gen_ticker: String,
        dt: String,
        freq: Option<String>,
    ) => xbbg_recipes::futures::recipe_fut_ticker(&eng, gen_ticker, dt, freq)
);

recipe_wrapper!(
    /// Resolve the most active futures contract around a reference date.
    ///
    /// Args:
    ///     engine: Bloomberg engine instance
    ///     gen_ticker: Generic futures ticker (e.g., "ES1 Index")
    ///     dt: Reference date (YYYYMMDD format)
    ///     freq: Roll frequency ("M" monthly, "Q"/"QE" quarterly)
    #[pyfunction]
    #[pyo3(signature = (engine, gen_ticker, dt, freq=None))]
    |eng|
    fn recipe_active_futures(
        gen_ticker: String,
        dt: String,
        freq: Option<String>,
    ) => xbbg_recipes::futures::recipe_active_futures(&eng, gen_ticker, dt, freq)
);

recipe_wrapper!(
    /// Resolve a generic CDX ticker to the active specific series.
    ///
    /// Args:
    ///     engine: Bloomberg engine instance
    ///     gen_ticker: Generic CDX ticker (e.g., "CDX IG CDSI GEN 5Y Corp")
    ///     dt: Reference date (YYYYMMDD format)
    #[pyfunction]
    #[pyo3(signature = (engine, gen_ticker, dt))]
    |eng|
    fn recipe_cdx_ticker(
        gen_ticker: String,
        dt: String,
    ) => xbbg_recipes::futures::recipe_cdx_ticker(&eng, gen_ticker, dt)
);

recipe_wrapper!(
    /// Resolve the most active CDX series around a reference date.
    ///
    /// Args:
    ///     engine: Bloomberg engine instance
    ///     gen_ticker: Generic CDX ticker (e.g., "CDX IG CDSI GEN 5Y Corp")
    ///     dt: Reference date (YYYYMMDD format)
    ///     lookback_days: Lookback window for activity comparison (default: 10)
    #[pyfunction]
    #[pyo3(signature = (engine, gen_ticker, dt, lookback_days=None))]
    |eng|
    fn recipe_active_cdx(
        gen_ticker: String,
        dt: String,
        lookback_days: Option<i32>,
    ) => xbbg_recipes::futures::recipe_active_cdx(&eng, gen_ticker, dt, lookback_days)
);

// =============================================================================
// Historical Recipes
// =============================================================================

recipe_wrapper!(
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
    |eng|
    fn recipe_dividend(
        tickers: Vec<String>,
        start_date: String,
        end_date: String,
        dvd_type: Option<String>,
    ) => xbbg_recipes::historical::recipe_dividend(&eng, tickers, dvd_type, start_date, end_date)
);

recipe_wrapper!(
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
    |eng|
    fn recipe_turnover(
        tickers: Vec<String>,
        start_date: String,
        end_date: String,
        ccy: Option<String>,
        factor: Option<f64>,
    ) => xbbg_recipes::historical::recipe_turnover(
        &eng,
        tickers,
        start_date,
        end_date,
        ccy,
        factor,
    )
);

recipe_wrapper!(
    /// Fetch ETF constituent holdings via BQL.
    ///
    /// Args:
    ///     engine: Bloomberg engine instance
    ///     etf_ticker: ETF ticker (e.g., "SPY US Equity")
    ///     fields: Additional fields beyond defaults (id_isin, weights, id().position)
    #[pyfunction]
    #[pyo3(signature = (engine, etf_ticker, fields=None))]
    |eng|
    fn recipe_etf_holdings(
        etf_ticker: String,
        fields: Option<Vec<String>>,
    ) => xbbg_recipes::historical::recipe_etf_holdings(&eng, etf_ticker, fields)
);

// =============================================================================
// Currency Recipes
// =============================================================================

recipe_wrapper!(
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
    |eng|
    fn recipe_currency_conversion(
        ticker: String,
        target_ccy: String,
        start_date: String,
        end_date: String,
    ) => xbbg_recipes::currency::recipe_currency_conversion(
        &eng,
        ticker,
        target_ccy,
        start_date,
        end_date,
    )
);

/// Register all recipe functions with the Python module.
pub fn register_recipes_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    register_pyfunctions!(
        m;
        recipe_yas,
        recipe_preferreds,
        recipe_corporate_bonds,
        recipe_bqr,
        recipe_fut_ticker,
        recipe_active_futures,
        recipe_cdx_ticker,
        recipe_active_cdx,
        recipe_dividend,
        recipe_turnover,
        recipe_etf_holdings,
        recipe_currency_conversion,
    )
}

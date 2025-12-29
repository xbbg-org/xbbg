//! PyO3 bindings for xbbg Bloomberg engine.
//!
//! This module provides Python bindings for the Rust xbbg Engine,
//! exposing async (abdp, abdh, abds, abdib, abdtick) and sync variants.

use std::sync::Arc;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;

use xbbg_async::engine::{Engine, EngineConfig, OutputFormat};

/// Python wrapper for the xbbg Engine.
#[pyclass]
struct PyEngine {
    engine: Arc<Engine>,
}

#[pymethods]
impl PyEngine {
    /// Create a new Engine with optional configuration.
    ///
    /// This blocks while connecting to Bloomberg. GIL is released during connection.
    #[new]
    #[pyo3(signature = (host="localhost", port=8194))]
    fn new(py: Python<'_>, host: &str, port: u16) -> PyResult<Self> {
        let config = EngineConfig {
            server_host: host.to_string(),
            server_port: port,
            ..Default::default()
        };

        // Release GIL during blocking Engine::start()
        let engine = py
            .detach(|| Engine::start(config))
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to start engine: {e}")))?;

        Ok(Self {
            engine: Arc::new(engine),
        })
    }

    // =========================================================================
    // Async API - returns Python coroutines
    // =========================================================================

    /// Async reference data request (abdp).
    ///
    /// Returns a coroutine that resolves to a PyArrow RecordBatch.
    #[pyo3(signature = (tickers, fields, overrides=None, wide=false))]
    fn abdp<'py>(
        &self,
        py: Python<'py>,
        tickers: Vec<String>,
        fields: Vec<String>,
        overrides: Option<Vec<(String, String)>>,
        wide: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let overrides = overrides.unwrap_or_default();
        let format = if wide {
            OutputFormat::Wide
        } else {
            OutputFormat::Long
        };

        future_into_py(py, async move {
            let batch = engine
                .bdp_with_format(tickers, fields, overrides, format)
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("abdp failed: {e}")))?;

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }

    /// Async historical data request (abdh).
    ///
    /// Returns a coroutine that resolves to a PyArrow RecordBatch.
    #[pyo3(signature = (tickers, fields, start_date, end_date, options=None))]
    fn abdh<'py>(
        &self,
        py: Python<'py>,
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        options: Option<Vec<(String, String)>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let options = options.unwrap_or_default();

        future_into_py(py, async move {
            let batch = engine
                .bdh(tickers, fields, start_date, end_date, options)
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("abdh failed: {e}")))?;

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }

    /// Async bulk data request (abds).
    ///
    /// Returns a coroutine that resolves to a PyArrow RecordBatch.
    #[pyo3(signature = (ticker, field, overrides=None))]
    fn abds<'py>(
        &self,
        py: Python<'py>,
        ticker: String,
        field: String,
        overrides: Option<Vec<(String, String)>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let overrides = overrides.unwrap_or_default();

        future_into_py(py, async move {
            let batch = engine
                .bds(ticker, field, overrides)
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("abds failed: {e}")))?;

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }

    /// Async intraday bar request (abdib).
    ///
    /// Returns a coroutine that resolves to a PyArrow RecordBatch.
    #[pyo3(signature = (ticker, event_type, interval, start_datetime, end_datetime))]
    fn abdib<'py>(
        &self,
        py: Python<'py>,
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let batch = engine
                .bdib(ticker, event_type, interval, start_datetime, end_datetime)
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("abdib failed: {e}")))?;

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }

    /// Async intraday tick request (abdtick).
    ///
    /// Returns a coroutine that resolves to a PyArrow RecordBatch.
    #[pyo3(signature = (ticker, start_datetime, end_datetime))]
    fn abdtick<'py>(
        &self,
        py: Python<'py>,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let batch = engine
                .bdtick(ticker, start_datetime, end_datetime)
                .await
                .map_err(|e| PyRuntimeError::new_err(format!("abdtick failed: {e}")))?;

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }
}

/// Convert Arrow RecordBatch to PyArrow RecordBatch using zero-copy FFI.
fn record_batch_to_pyarrow(
    py: Python<'_>,
    batch: arrow::record_batch::RecordBatch,
) -> PyResult<Py<PyAny>> {
    use arrow::pyarrow::ToPyArrow;

    // Zero-copy conversion via Arrow C Data Interface
    batch
        .to_pyarrow(py)
        .map(|b| b.unbind())
        .map_err(|e| PyRuntimeError::new_err(format!("Arrow FFI conversion failed: {e}")))
}

#[pyfunction]
fn version() -> String {
    xbbg_core::version().to_string()
}

#[pymodule]
#[pyo3(name = "_core")]
fn _core(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_class::<PyEngine>()?;
    Ok(())
}

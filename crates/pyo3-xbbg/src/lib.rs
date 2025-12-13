//! PyO3 bindings for xbbg Bloomberg engine.
//!
//! This module provides Python bindings for the Rust xbbg Engine,
//! exposing bdp, bdh, bds, bdib, bdtick, and subscription methods.

use std::sync::Arc;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use xbbg_async::engine::{Engine, EngineConfig, OutputFormat};

/// Python wrapper for the xbbg Engine.
#[pyclass]
struct PyEngine {
    engine: Arc<Engine>,
    rt: Arc<tokio::runtime::Runtime>,
}

#[pymethods]
impl PyEngine {
    /// Create a new Engine with optional configuration.
    #[new]
    #[pyo3(signature = (host="localhost", port=8194))]
    fn new(host: &str, port: u16) -> PyResult<Self> {
        let config = EngineConfig {
            server_host: host.to_string(),
            server_port: port,
            ..Default::default()
        };

        let engine = Engine::start(config)
            .map_err(|e| PyRuntimeError::new_err(format!("Failed to start engine: {e}")))?;

        let rt = engine.runtime().clone();

        Ok(Self {
            engine: Arc::new(engine),
            rt,
        })
    }

    /// Reference data request (bdp).
    ///
    /// Args:
    ///     tickers: List of ticker symbols
    ///     fields: List of field names
    ///     overrides: Optional list of (name, value) override tuples
    ///     wide: If True, return wide format (one column per field)
    ///
    /// Returns:
    ///     PyArrow RecordBatch
    #[pyo3(signature = (tickers, fields, overrides=None, wide=false))]
    fn bdp(
        &self,
        py: Python<'_>,
        tickers: Vec<String>,
        fields: Vec<String>,
        overrides: Option<Vec<(String, String)>>,
        wide: bool,
    ) -> PyResult<PyObject> {
        let engine = self.engine.clone();
        let overrides = overrides.unwrap_or_default();
        let format = if wide {
            OutputFormat::Wide
        } else {
            OutputFormat::Long
        };

        let batch = self
            .rt
            .block_on(async {
                engine
                    .bdp_with_format(tickers, fields, overrides, format)
                    .await
            })
            .map_err(|e| PyRuntimeError::new_err(format!("bdp failed: {e}")))?;

        // Convert Arrow RecordBatch to PyArrow
        record_batch_to_pyarrow(py, batch)
    }

    /// Historical data request (bdh).
    ///
    /// Args:
    ///     tickers: List of ticker symbols
    ///     fields: List of field names
    ///     start_date: Start date (YYYYMMDD format)
    ///     end_date: End date (YYYYMMDD format)
    ///     options: Optional list of (name, value) option tuples
    ///
    /// Returns:
    ///     PyArrow RecordBatch
    #[pyo3(signature = (tickers, fields, start_date, end_date, options=None))]
    fn bdh(
        &self,
        py: Python<'_>,
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        options: Option<Vec<(String, String)>>,
    ) -> PyResult<PyObject> {
        let engine = self.engine.clone();
        let options = options.unwrap_or_default();

        let batch = self
            .rt
            .block_on(async {
                engine
                    .bdh(tickers, fields, start_date, end_date, options)
                    .await
            })
            .map_err(|e| PyRuntimeError::new_err(format!("bdh failed: {e}")))?;

        record_batch_to_pyarrow(py, batch)
    }

    /// Bulk data request (bds).
    ///
    /// Args:
    ///     ticker: Single ticker symbol
    ///     field: Single field name
    ///     overrides: Optional list of (name, value) override tuples
    ///
    /// Returns:
    ///     PyArrow RecordBatch
    #[pyo3(signature = (ticker, field, overrides=None))]
    fn bds(
        &self,
        py: Python<'_>,
        ticker: String,
        field: String,
        overrides: Option<Vec<(String, String)>>,
    ) -> PyResult<PyObject> {
        let engine = self.engine.clone();
        let overrides = overrides.unwrap_or_default();

        let batch = self
            .rt
            .block_on(async { engine.bds(ticker, field, overrides).await })
            .map_err(|e| PyRuntimeError::new_err(format!("bds failed: {e}")))?;

        record_batch_to_pyarrow(py, batch)
    }

    /// Intraday bar request (bdib).
    ///
    /// Args:
    ///     ticker: Single ticker symbol
    ///     event_type: Event type (TRADE, BID, ASK, etc.)
    ///     interval: Bar interval in minutes
    ///     start_datetime: Start datetime (ISO format)
    ///     end_datetime: End datetime (ISO format)
    ///
    /// Returns:
    ///     PyArrow RecordBatch
    #[pyo3(signature = (ticker, event_type, interval, start_datetime, end_datetime))]
    fn bdib(
        &self,
        py: Python<'_>,
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
    ) -> PyResult<PyObject> {
        let engine = self.engine.clone();

        let batch = self
            .rt
            .block_on(async {
                engine
                    .bdib(ticker, event_type, interval, start_datetime, end_datetime)
                    .await
            })
            .map_err(|e| PyRuntimeError::new_err(format!("bdib failed: {e}")))?;

        record_batch_to_pyarrow(py, batch)
    }

    /// Intraday tick request (bdtick).
    ///
    /// Args:
    ///     ticker: Single ticker symbol
    ///     start_datetime: Start datetime (ISO format)
    ///     end_datetime: End datetime (ISO format)
    ///
    /// Returns:
    ///     PyArrow RecordBatch
    #[pyo3(signature = (ticker, start_datetime, end_datetime))]
    fn bdtick(
        &self,
        py: Python<'_>,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
    ) -> PyResult<PyObject> {
        let engine = self.engine.clone();

        let batch = self
            .rt
            .block_on(async { engine.bdtick(ticker, start_datetime, end_datetime).await })
            .map_err(|e| PyRuntimeError::new_err(format!("bdtick failed: {e}")))?;

        record_batch_to_pyarrow(py, batch)
    }
}

/// Convert Arrow RecordBatch to PyArrow RecordBatch.
fn record_batch_to_pyarrow(
    py: Python<'_>,
    batch: arrow::record_batch::RecordBatch,
) -> PyResult<PyObject> {
    // Use arrow's FFI to convert to PyArrow
    // This requires pyarrow to be installed
    let pyarrow = py.import_bound("pyarrow")?;

    // For now, return a placeholder - full FFI implementation would use arrow-rs's pyarrow feature
    // or manually serialize/deserialize via IPC

    // Simple approach: convert to JSON-like dict for each row
    // This is inefficient but works without FFI setup
    let schema = batch.schema();
    let _num_rows = batch.num_rows();
    let num_cols = batch.num_columns();

    let columns = pyo3::types::PyDict::new_bound(py);

    for col_idx in 0..num_cols {
        let field = schema.field(col_idx);
        let col_name = field.name();
        let array = batch.column(col_idx);

        // Convert array to Python list based on type
        let py_list = array_to_pylist(py, array)?;
        columns.set_item(col_name, py_list)?;
    }

    // Create a PyArrow Table from the dict
    let table = pyarrow.call_method1("table", (columns,))?;

    Ok(table.into_py(py))
}

/// Convert Arrow array to Python list.
fn array_to_pylist(py: Python<'_>, array: &dyn arrow::array::Array) -> PyResult<PyObject> {
    use arrow::array::*;
    use arrow::datatypes::*;

    let list = pyo3::types::PyList::empty_bound(py);

    match array.data_type() {
        DataType::Utf8 => {
            let arr = array.as_any().downcast_ref::<StringArray>().unwrap();
            for i in 0..arr.len() {
                if arr.is_null(i) {
                    list.append(py.None())?;
                } else {
                    list.append(arr.value(i))?;
                }
            }
        }
        DataType::Float64 => {
            let arr = array.as_any().downcast_ref::<Float64Array>().unwrap();
            for i in 0..arr.len() {
                if arr.is_null(i) {
                    list.append(py.None())?;
                } else {
                    list.append(arr.value(i))?;
                }
            }
        }
        DataType::Int32 => {
            let arr = array.as_any().downcast_ref::<Int32Array>().unwrap();
            for i in 0..arr.len() {
                if arr.is_null(i) {
                    list.append(py.None())?;
                } else {
                    list.append(arr.value(i))?;
                }
            }
        }
        DataType::Int64 => {
            let arr = array.as_any().downcast_ref::<Int64Array>().unwrap();
            for i in 0..arr.len() {
                if arr.is_null(i) {
                    list.append(py.None())?;
                } else {
                    list.append(arr.value(i))?;
                }
            }
        }
        DataType::Date32 => {
            let arr = array.as_any().downcast_ref::<Date32Array>().unwrap();
            let datetime = py.import_bound("datetime")?;
            for i in 0..arr.len() {
                if arr.is_null(i) {
                    list.append(py.None())?;
                } else {
                    // Convert days since epoch to Python date
                    let days = arr.value(i);
                    let date = datetime.call_method1("date", (1970i32, 1i32, 1i32))?;
                    let timedelta = datetime.call_method1("timedelta", (days,))?;
                    let result = date.call_method1("__add__", (timedelta,))?;
                    list.append(result)?;
                }
            }
        }
        DataType::Timestamp(TimeUnit::Microsecond, _) => {
            let arr = array
                .as_any()
                .downcast_ref::<TimestampMicrosecondArray>()
                .unwrap();
            let datetime = py.import_bound("datetime")?;
            for i in 0..arr.len() {
                if arr.is_null(i) {
                    list.append(py.None())?;
                } else {
                    let micros = arr.value(i);
                    let secs = micros / 1_000_000;
                    let usecs = (micros % 1_000_000) as i32;
                    let dt = datetime
                        .call_method1("datetime", (1970i32, 1i32, 1i32, 0i32, 0i32, 0i32, 0i32))?;
                    let timedelta = datetime.call_method1("timedelta", (secs, usecs))?;
                    let result = dt.call_method1("__add__", (timedelta,))?;
                    list.append(result)?;
                }
            }
        }
        _ => {
            // For unsupported types, use string representation
            for i in 0..array.len() {
                if array.is_null(i) {
                    list.append(py.None())?;
                } else {
                    list.append(format!("<unsupported type>"))?;
                }
            }
        }
    }

    Ok(list.into_py(py))
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

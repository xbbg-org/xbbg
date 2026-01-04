//! PyO3 bindings for xbbg Bloomberg engine.
//!
//! This module provides Python bindings for the Rust xbbg Engine,
//! exposing a generic `request()` method that accepts parameters from Python.
//!
//! # GIL Handling
//!
//! The async API releases the GIL during Bloomberg SDK operations:
//! - `future_into_py` schedules work on tokio (no GIL held)
//! - GIL is only acquired via `Python::attach()` for final Arrow conversion
//! - `py.detach()` releases GIL during blocking `Engine::start()`
//!
//! # Exception Mapping
//!
//! Rust errors are mapped to Python exceptions:
//! - `BlpError::SessionStart` → `BlpSessionError`
//! - `BlpError::OpenService` → `BlpSessionError`
//! - `BlpError::RequestFailure` → `BlpRequestError`
//! - `BlpError::Timeout` → `BlpTimeoutError`
//! - `BlpError::InvalidArgument` → `BlpValidationError`
//! - Other errors → `BlpInternalError`
//!
//! # Logging
//!
//! Rust tracing events are bridged to Python's logging module via pyo3-log.
//! Configure Python logging to see Rust-side events:
//!
//! ```python
//! import logging
//! logging.basicConfig(level=logging.DEBUG)
//! ```

use std::collections::HashMap;
use std::sync::Arc;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_async_runtimes::tokio::future_into_py;
use tracing::{debug, info, warn};

use xbbg_async::engine::{Engine, EngineConfig, ExtractorType, RequestParams};
use xbbg_async::BlpAsyncError;
use xbbg_core::BlpError;

// =============================================================================
// Python Exception Hierarchy (mirrors py-xbbg/src/xbbg/exceptions.py)
// =============================================================================

pyo3::create_exception!(xbbg._core, BlpErrorBase, pyo3::exceptions::PyException);
pyo3::create_exception!(xbbg._core, BlpSessionError, BlpErrorBase);
pyo3::create_exception!(xbbg._core, BlpRequestError, BlpErrorBase);
pyo3::create_exception!(xbbg._core, BlpSecurityError, BlpRequestError);
pyo3::create_exception!(xbbg._core, BlpFieldError, BlpRequestError);
pyo3::create_exception!(xbbg._core, BlpValidationError, BlpErrorBase);
pyo3::create_exception!(xbbg._core, BlpTimeoutError, BlpErrorBase);
pyo3::create_exception!(xbbg._core, BlpInternalError, BlpErrorBase);

/// Convert BlpError to appropriate Python exception.
///
/// Maps each BlpError variant to the corresponding Python exception class,
/// preserving all structured error context (service, operation, cid, etc.).
fn blp_error_to_pyerr(e: BlpError) -> PyErr {
    match e {
        BlpError::SessionStart { source, label } => {
            let msg = format_error_msg("Session start failed", label.as_deref(), source.as_ref());
            BlpSessionError::new_err(msg)
        }
        BlpError::OpenService {
            service,
            source,
            label,
        } => {
            let msg = format!(
                "Failed to open service '{}': {}",
                service,
                format_error_msg("", label.as_deref(), source.as_ref())
            );
            BlpSessionError::new_err(msg)
        }
        BlpError::RequestFailure {
            service,
            operation,
            cid,
            label,
            request_id,
            source,
        } => {
            let mut msg = format!("Request failed on {}", service);
            if let Some(op) = &operation {
                msg.push_str(&format!("::{}", op));
            }
            if let Some(c) = &cid {
                msg.push_str(&format!(" (cid={})", c));
            }
            if let Some(rid) = &request_id {
                msg.push_str(&format!(" [request_id={}]", rid));
            }
            if let Some(l) = &label {
                msg.push_str(&format!(" - {}", l));
            }
            if let Some(s) = &source {
                msg.push_str(&format!(": {}", s));
            }
            BlpRequestError::new_err(msg)
        }
        BlpError::InvalidArgument { detail } => {
            BlpValidationError::new_err(format!("Invalid argument: {}", detail))
        }
        BlpError::Timeout => BlpTimeoutError::new_err("Request timed out"),
        BlpError::TemplateTerminated { cid } => {
            let msg = match cid {
                Some(c) => format!("Request template terminated (cid={})", c),
                None => "Request template terminated".to_string(),
            };
            BlpRequestError::new_err(msg)
        }
        BlpError::SubscriptionFailure { cid, label } => {
            let mut msg = "Subscription failed".to_string();
            if let Some(c) = &cid {
                msg.push_str(&format!(" (cid={})", c));
            }
            if let Some(l) = &label {
                msg.push_str(&format!(": {}", l));
            }
            BlpRequestError::new_err(msg)
        }
        BlpError::Internal { detail } => {
            BlpInternalError::new_err(format!("Internal error: {}", detail))
        }
        BlpError::SchemaOperationNotFound { service, operation } => BlpValidationError::new_err(
            format!("Operation not found: {}::{}", service, operation),
        ),
        BlpError::SchemaElementNotFound { parent, name } => {
            BlpValidationError::new_err(format!("Schema element not found: {}.{}", parent, name))
        }
        BlpError::SchemaTypeMismatch {
            element,
            expected,
            found,
        } => BlpValidationError::new_err(format!(
            "Schema type mismatch at {}: expected {:?}, found {:?}",
            element, expected, found
        )),
        BlpError::SchemaUnsupported { element, detail } => BlpValidationError::new_err(format!(
            "Unsupported schema construct at {}: {}",
            element, detail
        )),
    }
}

/// Convert BlpAsyncError to appropriate Python exception.
fn blp_async_error_to_pyerr(e: BlpAsyncError) -> PyErr {
    match e {
        // Route structured BlpError through the full exception mapper
        BlpAsyncError::Blp(blp_err) => blp_error_to_pyerr(blp_err),

        BlpAsyncError::Internal(msg) => BlpInternalError::new_err(msg),

        BlpAsyncError::StreamFull => {
            BlpInternalError::new_err("Stream buffer full - consumer too slow")
        }
        BlpAsyncError::Cancelled => BlpRequestError::new_err("Request was cancelled"),
        BlpAsyncError::Timeout => BlpTimeoutError::new_err("Request timed out"),
    }
}

/// Helper to format error messages with optional label and source.
fn format_error_msg(
    base: &str,
    label: Option<&str>,
    source: Option<&anyhow::Error>,
) -> String {
    let mut msg = base.to_string();
    if let Some(l) = label {
        if !msg.is_empty() {
            msg.push_str(": ");
        }
        msg.push_str(l);
    }
    if let Some(s) = source {
        if !msg.is_empty() {
            msg.push_str(" - ");
        }
        msg.push_str(&s.to_string());
    }
    if msg.is_empty() {
        "Unknown error".to_string()
    } else {
        msg
    }
}

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
        info!(host = host, port = port, "PyEngine: connecting to Bloomberg");

        let config = EngineConfig {
            server_host: host.to_string(),
            server_port: port,
            ..Default::default()
        };

        // Release GIL during blocking Engine::start()
        let engine = py
            .detach(|| Engine::start(config))
            .map_err(|e| {
                warn!(error = %e, "PyEngine: connection failed");
                blp_async_error_to_pyerr(e)
            })?;

        info!("PyEngine: connected successfully");

        Ok(Self {
            engine: Arc::new(engine),
        })
    }

    // =========================================================================
    // Generic Request API
    // =========================================================================

    /// Generic async Bloomberg request.
    ///
    /// Accepts a dictionary of parameters and returns a PyArrow RecordBatch.
    ///
    /// Required keys:
    /// - service: Bloomberg service URI (e.g., "//blp/refdata")
    /// - operation: Request operation name (e.g., "ReferenceDataRequest")
    /// - extractor: Extractor type hint (e.g., "refdata", "histdata", "intraday_bar")
    ///
    /// Optional keys (depend on request type):
    /// - securities: List of security identifiers
    /// - security: Single security identifier
    /// - fields: List of field names
    /// - overrides: List of (name, value) tuples
    /// - start_date, end_date: For historical requests
    /// - start_datetime, end_datetime: For intraday requests
    /// - event_type: For intraday bars (TRADE, BID, ASK)
    /// - interval: Bar interval in minutes
    /// - options: Additional Bloomberg options
    #[pyo3(signature = (params))]
    fn request<'py>(
        &self,
        py: Python<'py>,
        params: &Bound<'py, PyDict>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        // Extract and convert params to Rust struct
        let rust_params = dict_to_request_params(params)?;

        debug!(
            service = %rust_params.service,
            operation = %rust_params.operation,
            extractor = ?rust_params.extractor,
            securities = ?rust_params.securities,
            fields = ?rust_params.fields,
            "PyEngine: sending request"
        );

        future_into_py(py, async move {
            let batch = engine
                .request(rust_params)
                .await
                .map_err(|e| {
                    warn!(error = %e, "PyEngine: request failed");
                    blp_async_error_to_pyerr(e)
                })?;

            debug!(num_rows = batch.num_rows(), "PyEngine: request completed");

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }

    // =========================================================================
    // Field Type Resolution API
    // =========================================================================

    /// Resolve field types for a list of fields.
    #[pyo3(signature = (fields, overrides=None, default_type="string"))]
    fn resolve_field_types<'py>(
        &self,
        py: Python<'py>,
        fields: Vec<String>,
        overrides: Option<HashMap<String, String>>,
        default_type: &str,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let default = default_type.to_string();

        future_into_py(py, async move {
            let resolved = engine
                .resolve_field_types(&fields, overrides.as_ref(), &default)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            Python::attach(|py| {
                let dict = PyDict::new(py);
                for (k, v) in resolved {
                    dict.set_item(k, v)?;
                }
                Ok(dict.into_any().unbind())
            })
        })
    }

    /// Get field info from cache.
    fn get_field_info(&self, field: &str) -> Option<HashMap<String, String>> {
        self.engine.get_field_info(field).map(|info| {
            let mut map = HashMap::new();
            map.insert("field_id".to_string(), info.field_id);
            map.insert("arrow_type".to_string(), info.arrow_type);
            map.insert("description".to_string(), info.description);
            map.insert("category".to_string(), info.category);
            map
        })
    }

    /// Clear the field type cache.
    fn clear_field_cache(&self) {
        self.engine.clear_field_cache();
    }

    /// Save the field type cache to disk.
    fn save_field_cache(&self) -> PyResult<()> {
        self.engine.save_field_cache().map_err(PyRuntimeError::new_err)
    }
}

/// Convert a Python dictionary to Rust RequestParams.
fn dict_to_request_params(dict: &Bound<'_, PyDict>) -> PyResult<RequestParams> {
    // Required fields
    let service: String = dict
        .get_item("service")?
        .ok_or_else(|| PyRuntimeError::new_err("missing required field: service"))?
        .extract()?;

    let operation: String = dict
        .get_item("operation")?
        .ok_or_else(|| PyRuntimeError::new_err("missing required field: operation"))?
        .extract()?;

    let extractor_str: String = dict
        .get_item("extractor")?
        .ok_or_else(|| PyRuntimeError::new_err("missing required field: extractor"))?
        .extract()?;

    let extractor = ExtractorType::parse(&extractor_str).ok_or_else(|| {
        PyRuntimeError::new_err(format!("invalid extractor type: {}", extractor_str))
    })?;

    // Optional fields
    let securities: Option<Vec<String>> = dict
        .get_item("securities")?
        .map(|v| v.extract())
        .transpose()?;

    let security: Option<String> = dict
        .get_item("security")?
        .map(|v| v.extract())
        .transpose()?;

    let fields: Option<Vec<String>> = dict.get_item("fields")?.map(|v| v.extract()).transpose()?;

    let overrides: Option<Vec<(String, String)>> = dict
        .get_item("overrides")?
        .map(|v| v.extract())
        .transpose()?;

    let start_date: Option<String> = dict
        .get_item("start_date")?
        .map(|v| v.extract())
        .transpose()?;

    let end_date: Option<String> = dict
        .get_item("end_date")?
        .map(|v| v.extract())
        .transpose()?;

    let start_datetime: Option<String> = dict
        .get_item("start_datetime")?
        .map(|v| v.extract())
        .transpose()?;

    let end_datetime: Option<String> = dict
        .get_item("end_datetime")?
        .map(|v| v.extract())
        .transpose()?;

    let event_type: Option<String> = dict
        .get_item("event_type")?
        .map(|v| v.extract())
        .transpose()?;

    let interval: Option<u32> = dict
        .get_item("interval")?
        .map(|v| v.extract())
        .transpose()?;

    let options: Option<Vec<(String, String)>> =
        dict.get_item("options")?.map(|v| v.extract()).transpose()?;

    let field_types: Option<HashMap<String, String>> = dict
        .get_item("field_types")?
        .map(|v| v.extract())
        .transpose()?;

    let search_spec: Option<String> = dict
        .get_item("search_spec")?
        .map(|v| v.extract())
        .transpose()?;

    let field_ids: Option<Vec<String>> = dict
        .get_item("field_ids")?
        .map(|v| v.extract())
        .transpose()?;

    let long_mode: Option<String> = dict
        .get_item("long_mode")?
        .map(|v| v.extract())
        .transpose()?;

    Ok(RequestParams {
        service,
        operation,
        extractor,
        securities,
        security,
        fields,
        overrides,
        start_date,
        end_date,
        start_datetime,
        end_datetime,
        event_type,
        interval,
        options,
        field_types,
        search_spec,
        field_ids,
        long_mode,
    })
}

/// Convert Arrow RecordBatch to PyArrow RecordBatch using zero-copy FFI.
///
/// Uses Arrow's C Data Interface via ToPyArrow for zero-copy conversion.
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
    // Initialize pyo3-log to bridge Rust tracing to Python logging
    // This allows Python's logging.basicConfig(level=logging.DEBUG) to capture Rust events
    pyo3_log::init();

    // Initialize tokio runtime for pyo3-async-runtimes
    // This creates a multi-threaded runtime that handles async Bloomberg operations
    // The runtime is leaked to create a &'static reference as required by the API
    let runtime = Box::leak(Box::new(
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(4)
            .enable_all()
            .build()
            .expect("Failed to create tokio runtime"),
    ));
    pyo3_async_runtimes::tokio::init_with_runtime(runtime)
        .map_err(|_| PyRuntimeError::new_err("Failed to init tokio runtime"))?;

    info!("xbbg._core module initialized");

    // Version from git describe (e.g., "v1.0.0" or "v1.0.0-5-g1a2b3c4")
    // Strip the leading 'v' for Python version string
    let git_version = env!("VERGEN_GIT_DESCRIBE");
    let pkg_version = git_version.strip_prefix('v').unwrap_or(git_version);
    m.add("__version__", pkg_version)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_class::<PyEngine>()?;

    // Register exception classes for use from Python
    m.add("BlpError", _py.get_type::<BlpErrorBase>())?;
    m.add("BlpSessionError", _py.get_type::<BlpSessionError>())?;
    m.add("BlpRequestError", _py.get_type::<BlpRequestError>())?;
    m.add("BlpSecurityError", _py.get_type::<BlpSecurityError>())?;
    m.add("BlpFieldError", _py.get_type::<BlpFieldError>())?;
    m.add("BlpValidationError", _py.get_type::<BlpValidationError>())?;
    m.add("BlpTimeoutError", _py.get_type::<BlpTimeoutError>())?;
    m.add("BlpInternalError", _py.get_type::<BlpInternalError>())?;

    Ok(())
}

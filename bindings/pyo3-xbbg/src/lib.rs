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
//! Rust tracing events are output to stderr via a non-blocking writer.
//! The log level is controlled from Python without any GIL acquisition:
//!
//! ```python
//! import xbbg
//! xbbg.set_log_level("debug")   # sets atomic level, no GIL on log path
//! xbbg.set_log_level("warn")    # default — quiet for end users
//! ```
//!
//! For per-crate control, set `RUST_LOG` before importing xbbg:
//!
//! ```bash
//! RUST_LOG=xbbg_core=trace,xbbg_async=debug python my_script.py
//! ```

use std::collections::{HashMap, HashSet};
use std::sync::atomic::Ordering;
use std::sync::Arc;

use chrono::NaiveDate;
use pyo3::exceptions::{PyRuntimeError, PyStopAsyncIteration, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_async_runtimes::tokio::future_into_py;
use tokio::sync::{watch, Mutex};
use xbbg_log::{debug, info, warn};

use xbbg_async::engine::state::SubscriptionMetrics;
use xbbg_async::engine::{
    Engine, EngineConfig, ExtractorType, RequestParams, SubscriptionCommandHandle,
};
use xbbg_async::{BlpAsyncError, OverflowPolicy, ValidationMode};
use xbbg_core::BlpError;
use xbbg_ext::{ExchangeInfo, MarketInfo, MarketTiming};

mod ext;
mod markets;
mod recipes;

type StreamBatchResult = Result<arrow::record_batch::RecordBatch, BlpError>;
type StreamSender = tokio::sync::mpsc::Sender<StreamBatchResult>;
type StreamReceiver = tokio::sync::mpsc::Receiver<StreamBatchResult>;
type SharedStreamReceiver = Arc<Mutex<Option<StreamReceiver>>>;
type SubscriptionMetricsMap = HashMap<usize, Arc<SubscriptionMetrics>>;

async fn wait_for_subscription_close(close_rx: &mut watch::Receiver<bool>) {
    if *close_rx.borrow() {
        return;
    }

    while close_rx.changed().await.is_ok() {
        if *close_rx.borrow() {
            return;
        }
    }
}

fn subscription_metrics_totals(metrics: &SubscriptionMetricsMap) -> (u64, u64, u64, bool) {
    let messages_received = metrics
        .values()
        .map(|m| m.messages_received.load(Ordering::Relaxed))
        .sum();
    let dropped_batches = metrics
        .values()
        .map(|m| m.dropped_batches.load(Ordering::Relaxed))
        .sum();
    let batches_sent = metrics
        .values()
        .map(|m| m.batches_sent.load(Ordering::Relaxed))
        .sum();
    let slow_consumer = metrics
        .values()
        .any(|m| m.slow_consumer.load(Ordering::Relaxed));

    (
        messages_received,
        dropped_batches,
        batches_sent,
        slow_consumer,
    )
}

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
            let msg = format_error_msg("Session start failed", label.as_deref(), source.as_deref());
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
                format_error_msg("", label.as_deref(), source.as_deref())
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
        BlpError::SchemaOperationNotFound { service, operation } => {
            BlpValidationError::new_err(format!("Operation not found: {}::{}", service, operation))
        }
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
        BlpError::Validation { message, errors } => {
            // Build detailed error message with suggestions
            let details: Vec<String> = errors
                .iter()
                .map(|e| {
                    if let Some(ref suggestion) = e.suggestion {
                        format!("{} (did you mean '{}'?)", e, suggestion)
                    } else {
                        e.to_string()
                    }
                })
                .collect();
            let msg = if details.is_empty() {
                message
            } else {
                format!("{}: {}", message, details.join("; "))
            };
            BlpValidationError::new_err(msg)
        }
    }
}

/// Convert BlpAsyncError to appropriate Python exception.
fn blp_async_error_to_pyerr(e: BlpAsyncError) -> PyErr {
    match e {
        // Route structured BlpError through the full exception mapper
        BlpAsyncError::Blp(blp_err) => blp_error_to_pyerr(blp_err),
        // Explicit BlpError (not From trait)
        BlpAsyncError::BlpError(blp_err) => blp_error_to_pyerr(blp_err),

        BlpAsyncError::Internal(msg) => BlpInternalError::new_err(msg),

        BlpAsyncError::ConfigError { detail } => {
            BlpValidationError::new_err(format!("Configuration error: {}", detail))
        }
        BlpAsyncError::ChannelClosed => BlpInternalError::new_err("Channel closed unexpectedly"),
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
    source: Option<&(dyn std::error::Error + Send + Sync)>,
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

/// Python configuration for the xbbg Engine.
///
/// All settings have sensible defaults - you only need to specify what you want to change.
///
/// The defaults are derived from `EngineConfig::default()` in xbbg-async, so they
/// stay in sync automatically.
#[pyclass]
#[derive(Clone)]
pub struct PyEngineConfig {
    /// Bloomberg server host (default: "localhost")
    #[pyo3(get, set)]
    pub host: String,
    /// Bloomberg server port (default: 8194)
    #[pyo3(get, set)]
    pub port: u16,
    /// Number of pre-warmed request workers (default: 2)
    #[pyo3(get, set)]
    pub request_pool_size: usize,
    /// Number of pre-warmed subscription sessions (default: 1)
    #[pyo3(get, set)]
    pub subscription_pool_size: usize,
    /// Validation mode: "disabled" (default), "strict", or "lenient"
    #[pyo3(get, set)]
    pub validation_mode: String,
    /// Number of ticks to buffer before flushing to Python (default: 1)
    #[pyo3(get, set)]
    pub subscription_flush_threshold: usize,
    /// Bloomberg SDK event queue size (default: 10000)
    #[pyo3(get, set)]
    pub max_event_queue_size: usize,
    /// Internal command channel capacity (default: 256)
    #[pyo3(get, set)]
    pub command_queue_size: usize,
    /// Subscription stream backpressure capacity (default: 256)
    #[pyo3(get, set)]
    pub subscription_stream_capacity: usize,
    /// Overflow policy for slow consumers: "drop_newest" (default), "drop_oldest", "block"
    #[pyo3(get, set)]
    pub overflow_policy: String,
    /// Services to pre-warm on startup (default: ["//blp/refdata", "//blp/apiflds"])
    #[pyo3(get, set)]
    pub warmup_services: Vec<String>,
    /// Custom path for field cache JSON file (default: ~/.xbbg/field_cache.json)
    /// Set to None to use the default path.
    #[pyo3(get, set)]
    pub field_cache_path: Option<String>,
}

#[pymethods]
impl PyEngineConfig {
    /// Create a new configuration with defaults.
    ///
    /// All defaults are derived from the Rust EngineConfig to stay in sync.
    #[new]
    #[pyo3(signature = (**kwargs))]
    fn new(kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let defaults = EngineConfig::default();
        let mut config = Self {
            host: defaults.server_host,
            port: defaults.server_port,
            request_pool_size: defaults.request_pool_size,
            subscription_pool_size: defaults.subscription_pool_size,
            validation_mode: defaults.validation_mode.to_string(),
            subscription_flush_threshold: defaults.subscription_flush_threshold,
            max_event_queue_size: defaults.max_event_queue_size,
            command_queue_size: defaults.command_queue_size,
            subscription_stream_capacity: defaults.subscription_stream_capacity,
            overflow_policy: defaults.overflow_policy.to_string(),
            warmup_services: defaults.warmup_services,
            field_cache_path: None,
        };

        if let Some(kw) = kwargs {
            if let Some(v) = kw.get_item("host")? {
                config.host = v.extract()?;
            }
            if let Some(v) = kw.get_item("port")? {
                config.port = v.extract()?;
            }
            if let Some(v) = kw.get_item("request_pool_size")? {
                config.request_pool_size = v.extract()?;
            }
            if let Some(v) = kw.get_item("subscription_pool_size")? {
                config.subscription_pool_size = v.extract()?;
            }
            if let Some(v) = kw.get_item("validation_mode")? {
                config.validation_mode = v.extract()?;
            }
            if let Some(v) = kw.get_item("subscription_flush_threshold")? {
                config.subscription_flush_threshold = v.extract()?;
            }
            if let Some(v) = kw.get_item("max_event_queue_size")? {
                config.max_event_queue_size = v.extract()?;
            }
            if let Some(v) = kw.get_item("command_queue_size")? {
                config.command_queue_size = v.extract()?;
            }
            if let Some(v) = kw.get_item("subscription_stream_capacity")? {
                config.subscription_stream_capacity = v.extract()?;
            }
            if let Some(v) = kw.get_item("overflow_policy")? {
                config.overflow_policy = v.extract()?;
            }
            if let Some(v) = kw.get_item("warmup_services")? {
                config.warmup_services = v.extract()?;
            }
            if let Some(v) = kw.get_item("field_cache_path")? {
                config.field_cache_path = v.extract()?;
            }
        }

        Ok(config)
    }

    fn __repr__(&self) -> String {
        let fcp_display = self.field_cache_path.as_deref().unwrap_or("default");
        format!(
            "EngineConfig(host='{}', port={}, request_pool_size={}, subscription_pool_size={}, \
             validation_mode='{}', overflow_policy='{}', field_cache_path='{}', warmup_services={:?})",
            self.host,
            self.port,
            self.request_pool_size,
            self.subscription_pool_size,
            self.validation_mode,
            self.overflow_policy,
            fcp_display,
            self.warmup_services
        )
    }
}

impl TryFrom<&PyEngineConfig> for EngineConfig {
    type Error = PyErr;

    fn try_from(py_config: &PyEngineConfig) -> Result<Self, Self::Error> {
        let validation_mode: ValidationMode = py_config
            .validation_mode
            .parse()
            .map_err(|e: String| pyo3::exceptions::PyValueError::new_err(e))?;

        let overflow_policy: OverflowPolicy = py_config
            .overflow_policy
            .parse()
            .map_err(|e: String| pyo3::exceptions::PyValueError::new_err(e))?;

        Ok(EngineConfig {
            server_host: py_config.host.clone(),
            server_port: py_config.port,
            request_pool_size: py_config.request_pool_size,
            subscription_pool_size: py_config.subscription_pool_size,
            validation_mode,
            subscription_flush_threshold: py_config.subscription_flush_threshold,
            max_event_queue_size: py_config.max_event_queue_size,
            command_queue_size: py_config.command_queue_size,
            subscription_stream_capacity: py_config.subscription_stream_capacity,
            overflow_policy,
            warmup_services: py_config.warmup_services.clone(),
            field_cache_path: py_config
                .field_cache_path
                .as_ref()
                .map(std::path::PathBuf::from),
        })
    }
}

/// Python wrapper for the xbbg Engine.
#[pyclass]
struct PyEngine {
    engine: Arc<Engine>,
}

#[pymethods]
impl PyEngine {
    /// Create a new Engine with optional host/port configuration.
    ///
    /// This blocks while connecting to Bloomberg. GIL is released during connection.
    /// For more configuration options, use `Engine.with_config()`.
    #[new]
    #[pyo3(signature = (host="localhost", port=8194))]
    fn new(py: Python<'_>, host: &str, port: u16) -> PyResult<Self> {
        info!(
            host = host,
            port = port,
            "PyEngine: connecting to Bloomberg"
        );

        let config = EngineConfig {
            server_host: host.to_string(),
            server_port: port,
            ..Default::default()
        };

        Self::start_engine(py, config)
    }

    /// Create a new Engine with full configuration.
    ///
    /// This blocks while connecting to Bloomberg. GIL is released during connection.
    ///
    /// Example:
    /// ```python
    /// config = EngineConfig(
    ///     host="localhost",
    ///     port=8194,
    ///     request_pool_size=4,
    ///     subscription_pool_size=8,
    ///     overflow_policy="drop_newest",
    /// )
    /// engine = Engine.with_config(config)
    /// ```
    #[staticmethod]
    fn with_config(py: Python<'_>, config: &PyEngineConfig) -> PyResult<Self> {
        info!(
            host = %config.host,
            port = config.port,
            request_pool_size = config.request_pool_size,
            subscription_pool_size = config.subscription_pool_size,
            "PyEngine: connecting with custom config"
        );

        let rust_config: EngineConfig = config.try_into()?;

        Self::start_engine(py, rust_config)
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
    ///   Use "" / Operation.RAW_REQUEST together with request_operation for raw mode.
    ///
    /// Optional keys:
    /// - extractor: Extractor type hint (e.g., "refdata", "histdata", "intraday_bar")
    ///   If omitted, Rust resolves a default from `operation`.
    /// - request_operation: Actual Bloomberg operation name when operation=""
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
            let batch = engine.request(rust_params).await.map_err(|e| {
                warn!(error = %e, "PyEngine: request failed");
                blp_async_error_to_pyerr(e)
            })?;

            debug!(num_rows = batch.num_rows(), "PyEngine: request completed");

            Python::attach(|py| record_batch_to_pyarrow(py, batch))
        })
    }

    /// Resolve exchange metadata using override -> cache -> Bloomberg waterfall.
    fn resolve_exchange<'py>(
        &self,
        py: Python<'py>,
        ticker: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        future_into_py(py, async move {
            let info = engine.resolve_exchange(&ticker).await;
            Python::attach(|py| exchange_info_to_pydict(py, &info))
        })
    }

    /// Fetch market-level metadata (exchange, timezone, futures cycle info).
    fn fetch_market_info<'py>(
        &self,
        py: Python<'py>,
        ticker: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        future_into_py(py, async move {
            let info = engine
                .fetch_market_info(&ticker)
                .await
                .map_err(blp_async_error_to_pyerr)?;
            Python::attach(|py| market_info_to_pydict(py, &info))
        })
    }

    /// Resolve market timing (BOD/EOD/FINISHED) for a ticker/date.
    #[pyo3(signature = (ticker, date, timing="EOD", tz=None))]
    fn market_timing<'py>(
        &self,
        py: Python<'py>,
        ticker: String,
        date: String,
        timing: &str,
        tz: Option<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let timing = MarketTiming::parse(timing)
            .ok_or_else(|| PyValueError::new_err("timing must be one of: BOD, EOD, FINISHED"))?;
        let date = NaiveDate::parse_from_str(&date, "%Y-%m-%d")
            .map_err(|_| PyValueError::new_err("date must be YYYY-MM-DD"))?;

        future_into_py(py, async move {
            let value = engine
                .resolve_market_timing(&ticker, date, timing, tz.as_deref())
                .await
                .map_err(blp_async_error_to_pyerr)?;
            Python::attach(|py| Ok(value.into_pyobject(py)?.into_any().unbind()))
        })
    }

    /// Invalidate exchange cache (one ticker or all entries).
    #[pyo3(signature = (ticker=None))]
    fn invalidate_exchange_cache(&self, ticker: Option<String>) -> PyResult<()> {
        self.engine
            .invalidate_exchange_cache(ticker.as_deref())
            .map_err(PyRuntimeError::new_err)
    }

    /// Persist exchange cache to disk.
    fn save_exchange_cache(&self, py: Python<'_>) -> PyResult<()> {
        let engine = self.engine.clone();
        py.detach(move || engine.save_exchange_cache())
            .map_err(PyRuntimeError::new_err)
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
    fn save_field_cache(&self, py: Python<'_>) -> PyResult<()> {
        let engine = self.engine.clone();
        py.detach(move || engine.save_field_cache())
            .map_err(PyRuntimeError::new_err)
    }

    /// Get field cache statistics including the active cache path.
    fn field_cache_stats(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let (entry_count, cache_path) = self.engine.field_cache_stats();
        let dict = PyDict::new(py);
        dict.set_item("entry_count", entry_count)?;
        dict.set_item("cache_path", cache_path.to_string_lossy().into_owned())?;
        Ok(dict.into())
    }

    /// Validate Bloomberg field names.
    ///
    /// Queries Bloomberg's field info service to check if the given fields exist.
    /// Returns a list of invalid field names (fields that Bloomberg doesn't recognize).
    ///
    /// Example:
    ///     invalid = await engine.validate_fields(["PX_LAST", "INVALID_FIELD"])
    ///     # invalid = ["INVALID_FIELD"]
    fn validate_fields<'py>(
        &self,
        py: Python<'py>,
        fields: Vec<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let invalid = engine
                .validate_fields(&fields)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            Python::attach(|py| Ok(invalid.into_pyobject(py)?.into_any().unbind()))
        })
    }

    // =========================================================================
    // Schema Cache API
    // =========================================================================

    /// Get service schema (from cache or introspect).
    ///
    /// Returns a dictionary with schema information including operations.
    /// First checks disk cache; if not cached, introspects the service.
    #[pyo3(signature = (service))]
    fn get_schema<'py>(&self, py: Python<'py>, service: String) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let schema = engine
                .get_schema(&service)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            // Convert to JSON string for Python (dereference Arc)
            let json = serde_json::to_string(&*schema)
                .map_err(|e| PyRuntimeError::new_err(format!("serialize schema: {e}")))?;

            Python::attach(|py| Ok(json.into_pyobject(py)?.into_any().unbind()))
        })
    }

    /// Get a specific operation schema.
    ///
    /// Returns operation details including request/response element definitions.
    #[pyo3(signature = (service, operation))]
    fn get_operation<'py>(
        &self,
        py: Python<'py>,
        service: String,
        operation: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let op = engine
                .get_operation(&service, &operation)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            let json = serde_json::to_string(&op)
                .map_err(|e| PyRuntimeError::new_err(format!("serialize operation: {e}")))?;

            Python::attach(|py| Ok(json.into_pyobject(py)?.into_any().unbind()))
        })
    }

    /// List all operations for a service.
    #[pyo3(signature = (service))]
    fn list_operations<'py>(
        &self,
        py: Python<'py>,
        service: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let ops = engine
                .list_operations(&service)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            Python::attach(|py| {
                let list = pyo3::types::PyList::new(py, ops)?;
                Ok(list.into_any().unbind())
            })
        })
    }

    /// Get cached schema without introspection.
    ///
    /// Returns None if the schema is not cached.
    fn get_cached_schema(&self, service: &str) -> Option<String> {
        self.engine
            .get_cached_schema(service)
            .and_then(|s| serde_json::to_string(&*s).ok())
    }

    /// Invalidate a cached schema.
    fn invalidate_schema(&self, service: &str) {
        self.engine.invalidate_schema(service);
    }

    /// Clear all cached schemas.
    fn clear_schema_cache(&self) {
        self.engine.clear_schema_cache();
    }

    /// List all cached service URIs.
    fn list_cached_schemas(&self) -> Vec<String> {
        self.engine.list_cached_schemas()
    }

    // =========================================================================
    // Schema Validation API
    // =========================================================================

    /// Get valid enum values for an element.
    ///
    /// Returns a list of valid enum values, or None if the element is not an enum.
    #[pyo3(signature = (service, operation, element))]
    fn get_enum_values<'py>(
        &self,
        py: Python<'py>,
        service: String,
        operation: String,
        element: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let values = engine
                .get_enum_values(&service, &operation, &element)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            Python::attach(|py| match values {
                Some(v) => {
                    let list = pyo3::types::PyList::new(py, v)?;
                    Ok(list.into_any().unbind())
                }
                None => Ok(py.None()),
            })
        })
    }

    /// List all valid element names for an operation.
    #[pyo3(signature = (service, operation))]
    fn list_valid_elements<'py>(
        &self,
        py: Python<'py>,
        service: String,
        operation: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();

        future_into_py(py, async move {
            let elements = engine
                .list_valid_elements(&service, &operation)
                .await
                .map_err(blp_async_error_to_pyerr)?;

            Python::attach(|py| match elements {
                Some(v) => {
                    let list = pyo3::types::PyList::new(py, v)?;
                    Ok(list.into_any().unbind())
                }
                None => Ok(py.None()),
            })
        })
    }

    // =========================================================================
    // Subscription API
    // =========================================================================

    /// Subscribe to real-time market data.
    ///
    /// Returns a PySubscription that supports async iteration and dynamic add/remove.
    /// GIL is released during async operations; iteration and add/remove use separate
    /// locks to avoid contention.
    ///
    /// Example:
    /// ```python
    /// sub = await engine.subscribe(['AAPL US Equity'], ['LAST_PRICE', 'BID', 'ASK'])
    /// async for batch in sub:
    ///     print(batch)
    /// await sub.unsubscribe()
    /// ```
    #[pyo3(signature = (tickers, fields, flush_threshold=None, overflow_policy=None, stream_capacity=None))]
    fn subscribe<'py>(
        &self,
        py: Python<'py>,
        tickers: Vec<String>,
        fields: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<String>,
        stream_capacity: Option<usize>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let tickers_clone = tickers.clone();
        let fields_clone = fields.clone();

        let op = overflow_policy.as_deref().map(|s| match s {
            "drop_oldest" => OverflowPolicy::DropOldest,
            "block" => OverflowPolicy::Block,
            _ => OverflowPolicy::DropNewest,
        });

        debug!(
            tickers = ?tickers,
            fields = ?fields,
            "PyEngine: creating subscription"
        );

        future_into_py(py, async move {
            let stream = engine
                .subscribe_with_options(
                    "//blp/mktdata".to_string(),
                    tickers_clone.clone(),
                    fields_clone.clone(),
                    vec![],
                    stream_capacity,
                    flush_threshold,
                    op,
                )
                .await
                .map_err(blp_async_error_to_pyerr)?;

            debug!("PyEngine: subscription created");

            // Destructure the SubscriptionStream to separate rx from the rest
            // This allows iteration (rx) and modification (claim) to use separate locks
            let (rx, tx, claim, keys, topic_to_key, metrics, ft, op_policy, service, options) =
                stream.into_parts().map_err(blp_error_to_pyerr)?;

            let (close_signal, _) = watch::channel(false);
            let handle = SubscriptionStreamHandle {
                tx,
                claim: Some(claim),
                keys,
                topics: tickers_clone,
                fields: fields_clone,
                topic_to_key,
                service,
                options,
                flush_threshold: ft,
                overflow_policy: op_policy,
                _stream_capacity: stream_capacity,
                metrics,
            };

            Python::attach(|py| {
                let py_sub = PySubscription {
                    rx: Arc::new(Mutex::new(Some(rx))),
                    stream: Arc::new(Mutex::new(Some(handle))),
                    ops: Arc::new(Mutex::new(())),
                    close_signal,
                };
                Ok(Py::new(py, py_sub)?.into_any())
            })
        })
    }

    /// Subscribe to real-time data with custom service and options.
    ///
    /// This is the generic subscription method for services like //blp/mktvwap.
    ///
    /// Args:
    ///     service: Bloomberg service URI (e.g., "//blp/mktvwap")
    ///     tickers: List of securities to subscribe to
    ///     fields: List of fields to subscribe to
    ///     options: List of subscription options (e.g., ["VWAP_START_TIME=09:30"])
    ///
    /// Example:
    /// ```python
    /// sub = await engine.subscribe_with_options(
    ///     '//blp/mktvwap',
    ///     ['AAPL US Equity'],
    ///     ['RT_PX_VWAP', 'RT_VWAP_VOLUME'],
    ///     ['VWAP_START_TIME=09:30', 'VWAP_END_TIME=16:00']
    /// )
    /// async for batch in sub:
    ///     print(batch)
    /// ```
    #[pyo3(signature = (service, tickers, fields, options=None, flush_threshold=None, overflow_policy=None, stream_capacity=None))]
    #[allow(clippy::too_many_arguments)]
    fn subscribe_with_options<'py>(
        &self,
        py: Python<'py>,
        service: String,
        tickers: Vec<String>,
        fields: Vec<String>,
        options: Option<Vec<String>>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<String>,
        stream_capacity: Option<usize>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let tickers_clone = tickers.clone();
        let fields_clone = fields.clone();
        let options_clone = options.clone().unwrap_or_default();
        let service_clone = service.clone();

        let op = overflow_policy.as_deref().map(|s| match s {
            "drop_oldest" => OverflowPolicy::DropOldest,
            "block" => OverflowPolicy::Block,
            _ => OverflowPolicy::DropNewest,
        });

        debug!(
            service = %service,
            tickers = ?tickers,
            fields = ?fields,
            options = ?options,
            "PyEngine: creating subscription with options"
        );

        future_into_py(py, async move {
            let stream = engine
                .subscribe_with_options(
                    service_clone.clone(),
                    tickers_clone.clone(),
                    fields_clone.clone(),
                    options_clone.clone(),
                    stream_capacity,
                    flush_threshold,
                    op,
                )
                .await
                .map_err(blp_async_error_to_pyerr)?;

            debug!("PyEngine: subscription with options created");

            let (rx, tx, claim, keys, topic_to_key, metrics, ft, op_policy, service, options) =
                stream.into_parts().map_err(blp_error_to_pyerr)?;

            let (close_signal, _) = watch::channel(false);
            let handle = SubscriptionStreamHandle {
                tx,
                claim: Some(claim),
                keys,
                topics: tickers_clone,
                fields: fields_clone,
                topic_to_key,
                service,
                options,
                flush_threshold: ft,
                overflow_policy: op_policy,
                _stream_capacity: stream_capacity,
                metrics,
            };

            Python::attach(|py| {
                let py_sub = PySubscription {
                    rx: Arc::new(Mutex::new(Some(rx))),
                    stream: Arc::new(Mutex::new(Some(handle))),
                    ops: Arc::new(Mutex::new(())),
                    close_signal,
                };
                Ok(Py::new(py, py_sub)?.into_any())
            })
        })
    }

    // =========================================================================
    // Lifecycle Management
    // =========================================================================

    /// Signal engine shutdown (non-blocking).
    ///
    /// Signals all worker threads to stop. They will terminate when they
    /// finish their current work or see the shutdown signal.
    ///
    /// This is called automatically during Python interpreter shutdown via atexit.
    /// You usually don't need to call this directly.
    fn signal_shutdown(&self) {
        info!("PyEngine: signal_shutdown called");
        self.engine.signal_shutdown();
    }

    /// Check if engine is available.
    ///
    /// Returns True if the engine exists. Note that this doesn't guarantee
    /// Bloomberg is still connected - a request might still fail.
    fn is_available(&self) -> bool {
        // Engine exists if we have it
        true
    }
}

impl PyEngine {
    /// Shared helper: release GIL and start Engine on a blocking thread.
    #[allow(clippy::result_large_err)]
    fn start_engine(py: Python<'_>, config: EngineConfig) -> PyResult<Self> {
        // Release GIL during blocking Engine::start().
        // Engine::start() creates Bloomberg sessions and waits for them to connect,
        // which can take seconds — must not hold GIL during this.
        let engine = py.detach(|| Engine::start(config)).map_err(|e| {
            warn!(error = %e, "PyEngine: connection failed");
            blp_async_error_to_pyerr(e)
        })?;

        info!("PyEngine: connected successfully");

        Ok(Self {
            engine: Arc::new(engine),
        })
    }
}

// =============================================================================
// PySubscription - Async iterator for real-time market data
// =============================================================================

/// Python subscription handle for real-time market data.
///
/// Supports:
/// - Async iteration (`async for batch in sub`)
/// - Dynamic add/remove of tickers
/// - Explicit unsubscribe with optional drain
/// - Context manager (`async with`)
///
/// Data arrives as `Result<RecordBatch, BlpError>`:
/// - `Ok(batch)` — yields a PyArrow RecordBatch
/// - `Err(error)` — raises a Python exception (BlpRequestError, BlpInternalError, etc.)
///
/// Design: Uses separate locks for rx (data receiving) vs stream (metadata snapshots),
/// plus a dedicated operation lock to serialize add/remove/unsubscribe without holding
/// the stream metadata lock across Bloomberg awaits.
#[pyclass]
pub struct PySubscription {
    /// Receiver for incoming data - separate lock so iteration doesn't block add/remove
    rx: SharedStreamReceiver,
    /// Stream handle for metadata and modification operations
    stream: Arc<Mutex<Option<SubscriptionStreamHandle>>>,
    /// Serializes add/remove/unsubscribe without holding the stream lock across await.
    ops: Arc<Mutex<()>>,
    /// Signal used to wake pending iteration during unsubscribe/close.
    close_signal: watch::Sender<bool>,
}

/// Internal handle for subscription metadata and operations (without the receiver)
struct SubscriptionStreamHandle {
    tx: StreamSender,
    claim: Option<xbbg_async::engine::SessionClaim>,
    keys: Vec<usize>,
    topics: Vec<String>,
    fields: Vec<String>,
    topic_to_key: std::collections::HashMap<String, usize>,
    service: String,
    options: Vec<String>,
    flush_threshold: Option<usize>,
    overflow_policy: Option<OverflowPolicy>,
    _stream_capacity: Option<usize>,
    metrics: SubscriptionMetricsMap,
}

struct PendingAdd {
    command: SubscriptionCommandHandle,
    new_topics: Vec<String>,
    service: String,
    fields: Vec<String>,
    options: Vec<String>,
    flush_threshold: Option<usize>,
    overflow_policy: Option<OverflowPolicy>,
    tx: StreamSender,
}

struct PendingRemove {
    command: SubscriptionCommandHandle,
    topics: Vec<String>,
    keys: Vec<usize>,
}

impl SubscriptionStreamHandle {
    fn prepare_add(&self, tickers: Vec<String>) -> PyResult<Option<PendingAdd>> {
        let claim = self
            .claim
            .as_ref()
            .ok_or_else(|| PyRuntimeError::new_err("subscription already closed"))?;
        let command = claim.command_handle().map_err(blp_async_error_to_pyerr)?;

        let mut seen_topics = HashSet::new();
        let new_topics: Vec<String> = tickers
            .into_iter()
            .filter(|t| !self.topic_to_key.contains_key(t) && seen_topics.insert(t.clone()))
            .collect();

        if new_topics.is_empty() {
            return Ok(None);
        }

        Ok(Some(PendingAdd {
            command,
            new_topics,
            service: self.service.clone(),
            fields: self.fields.clone(),
            options: self.options.clone(),
            flush_threshold: self.flush_threshold,
            overflow_policy: self.overflow_policy,
            tx: self.tx.clone(),
        }))
    }

    fn apply_add(
        &mut self,
        topics: &[String],
        new_keys: Vec<usize>,
        new_metrics: Vec<Arc<SubscriptionMetrics>>,
    ) {
        for ((topic, key), metric) in topics
            .iter()
            .zip(new_keys.iter())
            .zip(new_metrics.into_iter())
        {
            self.topic_to_key.insert(topic.clone(), *key);
            self.topics.push(topic.clone());
            self.keys.push(*key);
            self.metrics.insert(*key, metric);
        }
    }

    fn prepare_remove(&self, tickers: Vec<String>) -> PyResult<Option<PendingRemove>> {
        let claim = self
            .claim
            .as_ref()
            .ok_or_else(|| PyRuntimeError::new_err("subscription already closed"))?;
        let command = claim.command_handle().map_err(blp_async_error_to_pyerr)?;

        let mut seen_keys = HashSet::new();
        let mut topics = Vec::new();
        let mut keys = Vec::new();

        for ticker in tickers {
            if let Some(&key) = self.topic_to_key.get(&ticker) {
                if seen_keys.insert(key) {
                    topics.push(ticker);
                    keys.push(key);
                }
            }
        }

        if keys.is_empty() {
            return Ok(None);
        }

        Ok(Some(PendingRemove {
            command,
            topics,
            keys,
        }))
    }

    fn apply_remove(&mut self, topics: &[String]) {
        for topic in topics {
            if let Some(key) = self.topic_to_key.remove(topic) {
                self.topics.retain(|t| t != topic);
                self.keys.retain(|k| *k != key);
                self.metrics.remove(&key);
            }
        }
    }
}

#[derive(Clone, Default)]
struct SubscriptionSnapshot {
    present: bool,
    topics: Vec<String>,
    fields: Vec<String>,
    is_active: bool,
    messages_received: u64,
    dropped_batches: u64,
    batches_sent: u64,
    slow_consumer: bool,
}

impl PySubscription {
    fn snapshot_from_stream(
        stream: &Arc<Mutex<Option<SubscriptionStreamHandle>>>,
    ) -> SubscriptionSnapshot {
        let guard = stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => {
                let (messages_received, dropped_batches, batches_sent, slow_consumer) =
                    subscription_metrics_totals(&handle.metrics);
                SubscriptionSnapshot {
                    present: true,
                    topics: handle.topics.clone(),
                    fields: handle.fields.clone(),
                    is_active: !handle.keys.is_empty() && handle.claim.is_some(),
                    messages_received,
                    dropped_batches,
                    batches_sent,
                    slow_consumer,
                }
            }
            None => SubscriptionSnapshot::default(),
        }
    }

    fn snapshot(&self, py: Python<'_>) -> SubscriptionSnapshot {
        let stream = self.stream.clone();
        py.detach(move || Self::snapshot_from_stream(&stream))
    }
}

#[pymethods]
impl PySubscription {
    /// Async iterator protocol.
    fn __aiter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    /// Get next batch of data.
    /// Only locks the rx, not the stream - so add/remove can run concurrently.
    ///
    /// Returns a PyArrow RecordBatch on success.
    /// Raises a Python exception (BlpRequestError, BlpInternalError, etc.) on error.
    /// Raises StopAsyncIteration when the subscription is closed.
    fn __anext__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let rx = self.rx.clone();
        let close_signal = self.close_signal.clone();

        future_into_py(py, async move {
            let mut close_rx = close_signal.subscribe();
            let item = {
                let mut guard = rx.lock().await;
                let rx_ref = guard
                    .as_mut()
                    .ok_or_else(|| PyStopAsyncIteration::new_err("subscription closed"))?;
                tokio::select! {
                    item = rx_ref.recv() => Ok(item),
                    _ = wait_for_subscription_close(&mut close_rx) => Err(()),
                }
            };

            match item {
                Ok(Some(Ok(batch))) => Python::attach(|py| record_batch_to_pyarrow(py, batch)),
                Ok(Some(Err(blp_err))) => Err(blp_error_to_pyerr(blp_err)),
                Ok(None) => Err(PyStopAsyncIteration::new_err("subscription ended")),
                Err(()) => Err(PyStopAsyncIteration::new_err("subscription closed")),
            }
        })
    }

    /// Add tickers to the subscription dynamically.
    /// Iteration can continue while Bloomberg work is in flight.
    #[pyo3(signature = (tickers))]
    fn add<'py>(&self, py: Python<'py>, tickers: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
        let stream = self.stream.clone();
        let ops = self.ops.clone();

        debug!(tickers = ?tickers, "PySubscription: adding tickers");

        future_into_py(py, async move {
            let _op_guard = ops.lock().await;

            let pending = {
                let guard = stream.lock().await;
                let handle = guard
                    .as_ref()
                    .ok_or_else(|| PyRuntimeError::new_err("subscription closed"))?;
                handle.prepare_add(tickers)?
            };

            let Some(pending) = pending else {
                return Ok(());
            };

            // Add new topics using the same stream sender
            let (new_keys, new_metrics) = pending
                .command
                .add_topics(
                    pending.service.clone(),
                    pending.new_topics.clone(),
                    pending.fields.clone(),
                    pending.options.clone(),
                    pending.flush_threshold,
                    pending.overflow_policy,
                    pending.tx.clone(),
                )
                .await
                .map_err(blp_async_error_to_pyerr)?;

            let mut guard = stream.lock().await;
            let handle = guard
                .as_mut()
                .ok_or_else(|| PyRuntimeError::new_err("subscription closed"))?;
            handle.apply_add(&pending.new_topics, new_keys, new_metrics);

            Ok(())
        })
    }

    /// Remove tickers from the subscription dynamically.
    /// Iteration can continue while Bloomberg work is in flight.
    #[pyo3(signature = (tickers))]
    fn remove<'py>(&self, py: Python<'py>, tickers: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
        let stream = self.stream.clone();
        let ops = self.ops.clone();

        debug!(tickers = ?tickers, "PySubscription: removing tickers");

        future_into_py(py, async move {
            let _op_guard = ops.lock().await;

            let pending = {
                let guard = stream.lock().await;
                let handle = guard
                    .as_ref()
                    .ok_or_else(|| PyRuntimeError::new_err("subscription closed"))?;
                handle.prepare_remove(tickers)?
            };

            let Some(pending) = pending else {
                return Ok(());
            };

            pending
                .command
                .unsubscribe(pending.keys.clone())
                .await
                .map_err(blp_async_error_to_pyerr)?;

            let mut guard = stream.lock().await;
            let handle = guard
                .as_mut()
                .ok_or_else(|| PyRuntimeError::new_err("subscription closed"))?;
            handle.apply_remove(&pending.topics);
            Ok(())
        })
    }

    /// Get the currently subscribed tickers.
    #[getter]
    fn tickers(&self, py: Python<'_>) -> Vec<String> {
        self.snapshot(py).topics
    }

    /// Get the subscribed fields.
    #[getter]
    fn fields(&self, py: Python<'_>) -> Vec<String> {
        self.snapshot(py).fields
    }

    /// Check if the subscription is still active.
    #[getter]
    fn is_active(&self, py: Python<'_>) -> bool {
        self.snapshot(py).is_active
    }

    /// Get subscription metrics.
    ///
    /// Returns a dict with keys:
    /// - messages_received: int — total messages received from Bloomberg
    /// - dropped_batches: int — batches dropped due to overflow
    /// - batches_sent: int — batches successfully sent to Python
    /// - slow_consumer: bool — True if DATALOSS was received
    #[getter]
    fn stats(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let snapshot = self.snapshot(py);
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("messages_received", snapshot.messages_received)?;
        dict.set_item("dropped_batches", snapshot.dropped_batches)?;
        dict.set_item("batches_sent", snapshot.batches_sent)?;
        dict.set_item("slow_consumer", snapshot.slow_consumer)?;
        Ok(dict.into())
    }

    /// Unsubscribe and close the stream.
    ///
    /// If drain=True, returns remaining buffered batches before closing.
    #[pyo3(signature = (drain = false))]
    fn unsubscribe<'py>(&self, py: Python<'py>, drain: bool) -> PyResult<Bound<'py, PyAny>> {
        let stream_arc = self.stream.clone();
        let rx_arc = self.rx.clone();
        let ops = self.ops.clone();
        let close_signal = self.close_signal.clone();

        debug!(drain = drain, "PySubscription: unsubscribing");

        future_into_py(py, async move {
            let _op_guard = ops.lock().await;
            let _ = close_signal.send(true);

            // Take the stream handle first so add/remove operations stop immediately.
            let handle = {
                let mut guard = stream_arc.lock().await;
                guard.take()
            };

            let mut remaining = Vec::new();

            // Drain remaining batches if requested (skip errors)
            if drain {
                let rx = {
                    let mut guard = rx_arc.lock().await;
                    guard.take()
                };
                if let Some(mut rx) = rx {
                    while let Ok(item) = rx.try_recv() {
                        if let Ok(batch) = item {
                            remaining.push(batch);
                        }
                    }
                }
            }

            // Unsubscribe from Bloomberg
            if let Some(mut h) = handle {
                if let Some(claim) = h.claim.take() {
                    if !h.keys.is_empty() {
                        let _ = claim.unsubscribe(h.keys.clone()).await;
                    }
                    // claim is dropped here, returning session to pool
                }
            }

            if !remaining.is_empty() {
                Python::attach(|py| {
                    let list = pyo3::types::PyList::empty(py);
                    for batch in remaining {
                        let py_batch = record_batch_to_pyarrow(py, batch)?;
                        list.append(py_batch)?;
                    }
                    Ok(list.into_any().unbind())
                })
            } else {
                Python::attach(|py| Ok(py.None()))
            }
        })
    }

    /// Context manager entry.
    fn __aenter__<'py>(slf: PyRef<'py, Self>) -> PyRef<'py, Self> {
        slf
    }

    /// Context manager exit - unsubscribes automatically.
    #[pyo3(signature = (_exc_type=None, _exc_val=None, _exc_tb=None))]
    fn __aexit__<'py>(
        &self,
        py: Python<'py>,
        _exc_type: Option<Bound<'py, PyAny>>,
        _exc_val: Option<Bound<'py, PyAny>>,
        _exc_tb: Option<Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.unsubscribe(py, false)
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        let snapshot = self.snapshot(py);
        if snapshot.present {
            format!(
                "Subscription(tickers={:?}, fields={:?}, active={})",
                snapshot.topics, snapshot.fields, snapshot.is_active
            )
        } else {
            "Subscription(closed)".to_string()
        }
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

    let (extractor, extractor_set) = match dict.get_item("extractor")? {
        Some(value) => {
            let extractor_str: String = value.extract()?;
            let extractor = ExtractorType::parse(&extractor_str).ok_or_else(|| {
                PyRuntimeError::new_err(format!("invalid extractor type: {}", extractor_str))
            })?;
            (extractor, true)
        }
        None => (ExtractorType::default(), false),
    };

    let request_operation: Option<String> = dict
        .get_item("request_operation")?
        .map(|v| v.extract())
        .transpose()?;

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

    let elements: Option<Vec<(String, String)>> = dict
        .get_item("elements")?
        .map(|v| v.extract())
        .transpose()?;

    let kwargs: Option<HashMap<String, String>> =
        dict.get_item("kwargs")?.map(|v| v.extract()).transpose()?;

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

    let event_types: Option<Vec<String>> = dict
        .get_item("event_types")?
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

    let include_security_errors: bool = dict
        .get_item("include_security_errors")?
        .map(|v| v.extract())
        .transpose()?
        .unwrap_or(false);

    let validate_fields: Option<bool> = dict
        .get_item("validate_fields")?
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

    let format: Option<String> = dict.get_item("format")?.map(|v| v.extract()).transpose()?;

    Ok(RequestParams {
        service,
        operation,
        request_operation,
        extractor,
        extractor_set,
        securities,
        security,
        fields,
        overrides,
        elements,
        kwargs,
        start_date,
        end_date,
        start_datetime,
        end_datetime,
        event_type,
        event_types,
        interval,
        options,
        field_types,
        include_security_errors,
        validate_fields,
        search_spec,
        field_ids,
        format,
    })
}

fn exchange_info_to_pydict(py: Python<'_>, info: &ExchangeInfo) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("ticker", &info.ticker)?;
    dict.set_item("mic", info.mic.clone())?;
    dict.set_item("exch_code", info.exch_code.clone())?;
    dict.set_item("timezone", &info.timezone)?;
    dict.set_item("utc_offset", info.utc_offset)?;
    dict.set_item("source", info.source.as_str())?;
    dict.set_item("day", info.sessions.day.clone())?;
    dict.set_item("allday", info.sessions.allday.clone())?;
    dict.set_item("pre", info.sessions.pre.clone())?;
    dict.set_item("post", info.sessions.post.clone())?;
    dict.set_item("am", info.sessions.am.clone())?;
    dict.set_item("pm", info.sessions.pm.clone())?;
    Ok(dict.into_any().unbind())
}

fn market_info_to_pydict(py: Python<'_>, info: &MarketInfo) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("exch", info.exch.clone())?;
    dict.set_item("tz", info.tz.clone())?;
    dict.set_item("freq", info.freq.clone())?;
    dict.set_item("is_fut", info.is_fut)?;
    Ok(dict.into_any().unbind())
}

/// Convert Arrow RecordBatch to PyArrow RecordBatch using zero-copy FFI.
///
/// Uses Arrow's C Data Interface via ToPyArrow for zero-copy conversion.
pub(crate) fn record_batch_to_pyarrow(
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
    // Initialize zero-GIL logging: tracing -> AtomicLevelFilter -> non-blocking stderr
    //
    // Python controls via xbbg.set_log_level("debug").
    // Developers override with RUST_LOG=xbbg_core=trace,xbbg_async=debug.
    xbbg_log::init();

    // Initialize tokio runtime for pyo3-async-runtimes (future_into_py).
    //
    // pyo3-async-runtimes creates its own runtime on first use via get_runtime()
    // if we don't call init_with_runtime(). This is fine — the Engine also has
    // its own runtime for worker threads. The pyo3-async-runtimes runtime only
    // handles the Python↔Rust async bridge (future_into_py scheduling), while
    // the Engine's runtime handles Bloomberg SDK I/O.

    info!("xbbg._core module initialized");

    // Version from git describe (e.g., "v1.0.0" or "v1.0.0-5-g1a2b3c4")
    // Strip the leading 'v' for Python version string
    let git_version = env!("VERGEN_GIT_DESCRIBE");
    let pkg_version = git_version.strip_prefix('v').unwrap_or(git_version);
    m.add("__version__", pkg_version)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_class::<PyEngine>()?;
    m.add_class::<PyEngineConfig>()?;
    m.add_class::<PySubscription>()?;

    // Register exception classes for use from Python
    m.add("BlpError", _py.get_type::<BlpErrorBase>())?;
    m.add("BlpSessionError", _py.get_type::<BlpSessionError>())?;
    m.add("BlpRequestError", _py.get_type::<BlpRequestError>())?;
    m.add("BlpSecurityError", _py.get_type::<BlpSecurityError>())?;
    m.add("BlpFieldError", _py.get_type::<BlpFieldError>())?;
    m.add("BlpValidationError", _py.get_type::<BlpValidationError>())?;
    m.add("BlpTimeoutError", _py.get_type::<BlpTimeoutError>())?;
    m.add("BlpInternalError", _py.get_type::<BlpInternalError>())?;

    // Logging control (zero-GIL)
    m.add_function(wrap_pyfunction!(set_log_level, m)?)?;
    m.add_function(wrap_pyfunction!(get_log_level, m)?)?;

    // Register ext functions (date, pivot, ticker, futures, cdx, currency utilities)
    ext::register_ext_module(m)?;

    // Register markets functions (session derivation, market rules, timezone inference)
    markets::register(m)?;

    // Register recipe functions (12 high-level Bloomberg workflows)
    recipes::register_recipes_module(m)?;

    Ok(())
}

// =============================================================================
// Logging control — Python-facing functions
// =============================================================================

/// Set the Rust log level.
///
/// Accepts: "trace", "debug", "info", "warn", "error".
/// Default is "warn" (quiet for end users).
///
/// This sets an atomic integer — no GIL is held on the logging hot path.
/// For per-crate control, use the RUST_LOG environment variable instead.
#[pyfunction]
fn set_log_level(level: &str) -> PyResult<()> {
    let lvl = xbbg_log::parse_level(level).ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "Invalid log level '{}'. Expected: trace, debug, info, warn, error",
            level
        ))
    })?;
    xbbg_log::set_level(lvl);
    Ok(())
}

/// Get the current Rust log level as a string.
#[pyfunction]
fn get_log_level() -> &'static str {
    match xbbg_log::current_level() {
        xbbg_log::Level::TRACE => "trace",
        xbbg_log::Level::DEBUG => "debug",
        xbbg_log::Level::INFO => "info",
        xbbg_log::Level::WARN => "warn",
        xbbg_log::Level::ERROR => "error",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicBool, AtomicU64};

    fn metrics(
        messages_received: u64,
        dropped_batches: u64,
        batches_sent: u64,
        slow_consumer: bool,
    ) -> Arc<SubscriptionMetrics> {
        Arc::new(SubscriptionMetrics {
            messages_received: Arc::new(AtomicU64::new(messages_received)),
            dropped_batches: Arc::new(AtomicU64::new(dropped_batches)),
            batches_sent: Arc::new(AtomicU64::new(batches_sent)),
            slow_consumer: Arc::new(AtomicBool::new(slow_consumer)),
        })
    }

    #[test]
    fn subscription_metrics_totals_only_counts_active_entries() {
        let mut metrics_map = SubscriptionMetricsMap::new();
        metrics_map.insert(10, metrics(5, 1, 4, false));
        metrics_map.insert(11, metrics(7, 2, 6, true));

        metrics_map.remove(&10);

        assert_eq!(subscription_metrics_totals(&metrics_map), (7, 2, 6, true));
    }
}

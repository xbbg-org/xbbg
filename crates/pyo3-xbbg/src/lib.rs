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

use pyo3::exceptions::{PyRuntimeError, PyStopAsyncIteration};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_async_runtimes::tokio::future_into_py;
use tokio::sync::Mutex;
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
        // Explicit BlpError (not From trait)
        BlpAsyncError::BlpError(blp_err) => blp_error_to_pyerr(blp_err),

        BlpAsyncError::Internal(msg) => BlpInternalError::new_err(msg),

        BlpAsyncError::ConfigError { detail } => {
            BlpValidationError::new_err(format!("Configuration error: {}", detail))
        }
        BlpAsyncError::ChannelClosed => {
            BlpInternalError::new_err("Channel closed unexpectedly")
        }
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

/// Python configuration for the xbbg Engine.
///
/// All settings have sensible defaults - you only need to specify what you want to change.
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
    /// Number of pre-warmed subscription sessions (default: 4)
    #[pyo3(get, set)]
    pub subscription_pool_size: usize,
}

#[pymethods]
impl PyEngineConfig {
    /// Create a new configuration with defaults.
    #[new]
    #[pyo3(signature = (host="localhost", port=8194, request_pool_size=2, subscription_pool_size=4))]
    fn new(host: &str, port: u16, request_pool_size: usize, subscription_pool_size: usize) -> Self {
        Self {
            host: host.to_string(),
            port,
            request_pool_size,
            subscription_pool_size,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "EngineConfig(host='{}', port={}, request_pool_size={}, subscription_pool_size={})",
            self.host, self.port, self.request_pool_size, self.subscription_pool_size
        )
    }
}

impl From<&PyEngineConfig> for EngineConfig {
    fn from(py_config: &PyEngineConfig) -> Self {
        EngineConfig {
            server_host: py_config.host.clone(),
            server_port: py_config.port,
            request_pool_size: py_config.request_pool_size,
            subscription_pool_size: py_config.subscription_pool_size,
            ..Default::default()
        }
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

        let rust_config: EngineConfig = config.into();

        // Release GIL during blocking Engine::start()
        let engine = py
            .detach(|| Engine::start(rust_config))
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
    #[pyo3(signature = (tickers, fields))]
    fn subscribe<'py>(
        &self,
        py: Python<'py>,
        tickers: Vec<String>,
        fields: Vec<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let engine = self.engine.clone();
        let tickers_clone = tickers.clone();
        let fields_clone = fields.clone();

        debug!(
            tickers = ?tickers,
            fields = ?fields,
            "PyEngine: creating subscription"
        );

        future_into_py(py, async move {
            let stream = engine
                .subscribe(tickers_clone.clone(), fields_clone.clone())
                .await
                .map_err(blp_async_error_to_pyerr)?;

            debug!("PyEngine: subscription created");

            // Destructure the SubscriptionStream to separate rx from the rest
            // This allows iteration (rx) and modification (claim) to use separate locks
            let (rx, tx, claim, keys, topic_to_key) = stream.into_parts();

            let handle = SubscriptionStreamHandle {
                tx,
                claim: Some(claim),
                keys,
                topics: tickers_clone,
                fields: fields_clone,
                topic_to_key,
            };

            Python::attach(|py| {
                let py_sub = PySubscription {
                    rx: Arc::new(Mutex::new(Some(rx))),
                    stream: Arc::new(Mutex::new(Some(handle))),
                };
                Ok(Py::new(py, py_sub)?.into_any())
            })
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
/// Design: Uses separate locks for rx (data receiving) vs stream (add/remove/metadata)
/// to avoid lock contention between iterating and modifying subscriptions.
#[pyclass]
pub struct PySubscription {
    /// Receiver for incoming data - separate lock so iteration doesn't block add/remove
    rx: Arc<Mutex<Option<tokio::sync::mpsc::Receiver<arrow::record_batch::RecordBatch>>>>,
    /// Stream handle for metadata and modification operations
    stream: Arc<Mutex<Option<SubscriptionStreamHandle>>>,
}

/// Internal handle for subscription metadata and operations (without the receiver)
struct SubscriptionStreamHandle {
    tx: tokio::sync::mpsc::Sender<arrow::record_batch::RecordBatch>,
    claim: Option<xbbg_async::engine::SessionClaim>,
    keys: Vec<usize>,
    topics: Vec<String>,
    fields: Vec<String>,
    topic_to_key: std::collections::HashMap<String, usize>,
}

#[pymethods]
impl PySubscription {
    /// Async iterator protocol.
    fn __aiter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    /// Get next batch of data.
    /// Only locks the rx, not the stream - so add/remove can run concurrently.
    fn __anext__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let rx = self.rx.clone();

        future_into_py(py, async move {
            let batch = {
                let mut guard = rx.lock().await;
                let rx_ref = guard.as_mut().ok_or_else(|| {
                    PyStopAsyncIteration::new_err("subscription closed")
                })?;
                rx_ref.recv().await
            };

            match batch {
                Some(batch) => Python::attach(|py| record_batch_to_pyarrow(py, batch)),
                None => Err(PyStopAsyncIteration::new_err("subscription ended")),
            }
        })
    }

    /// Add tickers to the subscription dynamically.
    /// Only locks the stream handle, not rx - so iteration can continue.
    #[pyo3(signature = (tickers))]
    fn add<'py>(&self, py: Python<'py>, tickers: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
        let stream = self.stream.clone();

        debug!(tickers = ?tickers, "PySubscription: adding tickers");

        future_into_py(py, async move {
            let mut guard = stream.lock().await;
            let handle = guard.as_mut().ok_or_else(|| {
                PyRuntimeError::new_err("subscription closed")
            })?;

            // Filter out already subscribed topics
            let new_topics: Vec<String> = tickers
                .into_iter()
                .filter(|t| !handle.topic_to_key.contains_key(t))
                .collect();

            if new_topics.is_empty() {
                return Ok(());
            }

            let claim = handle.claim.as_ref().ok_or_else(|| {
                PyRuntimeError::new_err("subscription already closed")
            })?;

            // Add new topics using the same stream sender
            let new_keys = claim
                .add_topics(new_topics.clone(), handle.fields.clone(), handle.tx.clone())
                .await
                .map_err(blp_async_error_to_pyerr)?;

            // Track new topics
            for (topic, key) in new_topics.iter().zip(new_keys.iter()) {
                handle.topic_to_key.insert(topic.clone(), *key);
                handle.topics.push(topic.clone());
                handle.keys.push(*key);
            }

            Ok(())
        })
    }

    /// Remove tickers from the subscription dynamically.
    /// Only locks the stream handle, not rx - so iteration can continue.
    #[pyo3(signature = (tickers))]
    fn remove<'py>(&self, py: Python<'py>, tickers: Vec<String>) -> PyResult<Bound<'py, PyAny>> {
        let stream = self.stream.clone();

        debug!(tickers = ?tickers, "PySubscription: removing tickers");

        future_into_py(py, async move {
            let mut guard = stream.lock().await;
            let handle = guard.as_mut().ok_or_else(|| {
                PyRuntimeError::new_err("subscription closed")
            })?;

            // Find keys for topics to remove
            let mut keys_to_remove = Vec::new();
            for topic in &tickers {
                if let Some(key) = handle.topic_to_key.remove(topic) {
                    keys_to_remove.push(key);
                    handle.topics.retain(|t| t != topic);
                    handle.keys.retain(|k| *k != key);
                }
            }

            if keys_to_remove.is_empty() {
                return Ok(());
            }

            let claim = handle.claim.as_ref().ok_or_else(|| {
                PyRuntimeError::new_err("subscription already closed")
            })?;

            claim.unsubscribe(keys_to_remove).await.map_err(blp_async_error_to_pyerr)?;
            Ok(())
        })
    }

    /// Get the currently subscribed tickers.
    #[getter]
    fn tickers(&self) -> Vec<String> {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => handle.topics.clone(),
            None => vec![],
        }
    }

    /// Get the subscribed fields.
    #[getter]
    fn fields(&self) -> Vec<String> {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => handle.fields.clone(),
            None => vec![],
        }
    }

    /// Check if the subscription is still active.
    #[getter]
    fn is_active(&self) -> bool {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => !handle.keys.is_empty() && handle.claim.is_some(),
            None => false,
        }
    }

    /// Unsubscribe and close the stream.
    ///
    /// If drain=True, returns remaining buffered batches before closing.
    #[pyo3(signature = (drain = false))]
    fn unsubscribe<'py>(&self, py: Python<'py>, drain: bool) -> PyResult<Bound<'py, PyAny>> {
        let stream_arc = self.stream.clone();
        let rx_arc = self.rx.clone();

        debug!(drain = drain, "PySubscription: unsubscribing");

        future_into_py(py, async move {
            // Take both the stream handle and rx
            let handle = {
                let mut guard = stream_arc.lock().await;
                guard.take()
            };
            let rx = {
                let mut guard = rx_arc.lock().await;
                guard.take()
            };

            let mut remaining = Vec::new();

            // Drain remaining batches if requested
            if drain {
                if let Some(mut rx) = rx {
                    while let Ok(batch) = rx.try_recv() {
                        remaining.push(batch);
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

    fn __repr__(&self) -> String {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => {
                format!(
                    "Subscription(tickers={:?}, fields={:?}, active={})",
                    handle.topics,
                    handle.fields,
                    !handle.keys.is_empty() && handle.claim.is_some()
                )
            }
            None => "Subscription(closed)".to_string(),
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

    let format: Option<String> = dict
        .get_item("format")?
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
        format,
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

    Ok(())
}

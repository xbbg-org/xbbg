//! Three-session Engine for Bloomberg API.
//!
//! Architecture:
//! - Lane A (PumpA): Fast session for real-time subscriptions
//! - Lane B (PumpB): Slow session for bulk requests (bdp/bdh/bds)
//! - Lane C (PumpC): Slow session for intraday requests (bdib/bdtick)
//!
//! All pumps use slab-indexed correlation IDs for O(1) dispatch.
//! Lane C is separate from Lane B to prevent large intraday requests
//! from starving smaller bdp/bdh/bds requests.

mod pump_a;
mod pump_b;
mod pump_c;
pub mod state;

use std::collections::HashMap;
use std::sync::Arc;
use std::thread::JoinHandle;

use arrow::record_batch::RecordBatch;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::BlpError;

use crate::errors::BlpAsyncError;

pub use state::{OutputFormat, RequestState, SubscriptionState};

/// Slab key for O(1) correlation dispatch.
pub type SlabKey = usize;

/// Overflow policy for slow consumers.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum OverflowPolicy {
    /// Drop the newest data when buffer is full (default, non-blocking)
    #[default]
    DropNewest,
    /// Drop the oldest data when buffer is full (requires bounded ring buffer)
    DropOldest,
    /// Block the producer until space is available (use with caution)
    Block,
}

/// Extractor type hint for Arrow conversion.
///
/// Tells the pump which Arrow schema/extractor to use for the response.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ExtractorType {
    /// Reference data: [ticker, field, value, ...]
    #[default]
    RefData,
    /// Historical data: [ticker, date, field, value, ...]
    HistData,
    /// Bulk data: [ticker, field, row_idx, col1, col2, ...]
    BulkData,
    /// Intraday bars: [ticker, time, open, high, low, close, volume, ...]
    IntradayBar,
    /// Intraday ticks: [ticker, time, type, value, size, ...]
    IntradayTick,
    /// Generic flattener: [path, type, value_str, value_num, value_date]
    Generic,
    /// Raw JSON output: [json]
    RawJson,
    /// Field info: [field, type, description, category]
    FieldInfo,
}

impl ExtractorType {
    /// Parse extractor type from string (from Python).
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "refdata" => Some(Self::RefData),
            "histdata" => Some(Self::HistData),
            "bulk" => Some(Self::BulkData),
            "intraday_bar" => Some(Self::IntradayBar),
            "intraday_tick" => Some(Self::IntradayTick),
            "generic" => Some(Self::Generic),
            "raw_json" => Some(Self::RawJson),
            "fieldinfo" => Some(Self::FieldInfo),
            _ => None,
        }
    }
}

/// Generic request parameters from Python.
///
/// This unified struct holds all possible Bloomberg request parameters.
/// Not all fields are used for all request types.
#[derive(Clone, Debug, Default)]
pub struct RequestParams {
    /// Bloomberg service URI (e.g., "//blp/refdata")
    pub service: String,
    /// Request operation name (e.g., "ReferenceDataRequest")
    pub operation: String,
    /// Extractor type hint for Arrow conversion
    pub extractor: ExtractorType,
    /// Multiple securities (for bdp/bdh)
    pub securities: Option<Vec<String>>,
    /// Single security (for intraday)
    pub security: Option<String>,
    /// Fields to retrieve
    pub fields: Option<Vec<String>>,
    /// Field overrides
    pub overrides: Option<Vec<(String, String)>>,
    /// Start date (YYYYMMDD for bdh)
    pub start_date: Option<String>,
    /// End date (YYYYMMDD for bdh)
    pub end_date: Option<String>,
    /// Start datetime (ISO for intraday)
    pub start_datetime: Option<String>,
    /// End datetime (ISO for intraday)
    pub end_datetime: Option<String>,
    /// Event type (TRADE, BID, ASK for intraday)
    pub event_type: Option<String>,
    /// Bar interval in minutes (for bdib)
    pub interval: Option<u32>,
    /// Additional Bloomberg options
    pub options: Option<Vec<(String, String)>>,
    /// Manual field type overrides (for future type resolution)
    pub field_types: Option<HashMap<String, String>>,
    /// Search spec for FieldSearchRequest (//blp/apiflds)
    pub search_spec: Option<String>,
    /// Field IDs for FieldInfoRequest (//blp/apiflds)
    pub field_ids: Option<Vec<String>>,
    /// Long format output mode (String, WithMetadata, Typed)
    pub long_mode: Option<String>,
}

impl RequestParams {
    /// Determine which lane should handle this request based on operation.
    pub fn lane(&self) -> Lane {
        match self.operation.as_str() {
            "IntradayBarRequest" | "IntradayTickRequest" => Lane::C,
            _ => Lane::B,
        }
    }
}

/// Lane designation for request routing.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Lane {
    /// Lane A: Subscriptions
    A,
    /// Lane B: Bulk requests (bdp/bdh/bds)
    B,
    /// Lane C: Intraday requests (bdib/bdtick)
    C,
}

/// Commands sent to the Engine from the public API.
pub enum Command {
    // ─── Generic Request (unified) ───────────────────────────────────────────
    /// Generic Bloomberg request (routes based on params.operation)
    Request {
        params: RequestParams,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Streaming generic request
    RequestStream {
        params: RequestParams,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    },

    // ─── Lane A: Subscriptions ───────────────────────────────────────────────
    /// Subscribe to real-time data
    Subscribe {
        topics: Vec<String>,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
    },
    /// Unsubscribe by slab keys
    Unsubscribe { keys: Vec<SlabKey> },

    // ─── Admin ───────────────────────────────────────────────────────────────
    /// Graceful shutdown
    Shutdown,
}

/// Configuration for the Engine.
pub struct EngineConfig {
    /// Server host (e.g., "localhost")
    pub server_host: String,
    /// Server port (e.g., 8194)
    pub server_port: u16,
    /// Max event queue size (Bloomberg SDK setting)
    pub max_event_queue_size: usize,
    /// Command channel capacity (backpressure)
    pub command_queue_size: usize,
    /// Subscription flush threshold (rows before auto-flush)
    pub subscription_flush_threshold: usize,
    /// Subscription stream capacity (backpressure)
    pub subscription_stream_capacity: usize,
    /// Overflow policy for slow consumers
    pub overflow_policy: OverflowPolicy,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            server_host: "localhost".to_string(),
            server_port: 8194,
            max_event_queue_size: 10_000,
            command_queue_size: 256,
            subscription_flush_threshold: 1000,
            subscription_stream_capacity: 256,
            overflow_policy: OverflowPolicy::default(),
        }
    }
}

impl Clone for EngineConfig {
    fn clone(&self) -> Self {
        Self {
            server_host: self.server_host.clone(),
            server_port: self.server_port,
            max_event_queue_size: self.max_event_queue_size,
            command_queue_size: self.command_queue_size,
            subscription_flush_threshold: self.subscription_flush_threshold,
            subscription_stream_capacity: self.subscription_stream_capacity,
            overflow_policy: self.overflow_policy,
        }
    }
}

/// Three-session Bloomberg Engine.
///
/// Owns three pump threads:
/// - Lane A (fast): subscriptions, real-time market data
/// - Lane B (slow): bulk requests (bdp/bdh/bds)
/// - Lane C (slow): intraday requests (bdib/bdtick)
pub struct Engine {
    /// Command channel to Lane A (subscriptions)
    cmd_a: mpsc::Sender<Command>,
    /// Command channel to Lane B (bulk requests)
    cmd_b: mpsc::Sender<Command>,
    /// Command channel to Lane C (intraday requests)
    cmd_c: mpsc::Sender<Command>,
    /// Pump thread handle for Lane A
    _pump_a: JoinHandle<()>,
    /// Pump thread handle for Lane B
    _pump_b: JoinHandle<()>,
    /// Pump thread handle for Lane C
    _pump_c: JoinHandle<()>,
    /// Tokio runtime for async ops
    rt: Arc<tokio::runtime::Runtime>,
}

impl Engine {
    /// Create and start a new Engine with three Bloomberg sessions.
    pub fn start(config: EngineConfig) -> Result<Self, BlpAsyncError> {
        let rt = Arc::new(
            tokio::runtime::Builder::new_multi_thread()
                .enable_all()
                .build()
                .map_err(|e| BlpAsyncError::Internal(format!("tokio runtime: {e}")))?,
        );

        // Create command channels with backpressure
        let (cmd_a_tx, cmd_a_rx) = mpsc::channel(config.command_queue_size);
        let (cmd_b_tx, cmd_b_rx) = mpsc::channel(config.command_queue_size);
        let (cmd_c_tx, cmd_c_rx) = mpsc::channel(config.command_queue_size);

        // Start Lane A (fast/subscriptions)
        let config_a = config.clone();
        let pump_a = std::thread::Builder::new()
            .name("blp-pump-a".into())
            .spawn(move || {
                if let Err(e) = pump_a::run(config_a, cmd_a_rx) {
                    tracing::error!("PumpA exited with error: {e:?}");
                }
            })
            .map_err(|e| BlpAsyncError::Internal(format!("spawn pump_a: {e}")))?;

        // Start Lane B (slow/bulk)
        let config_b = config.clone();
        let pump_b = std::thread::Builder::new()
            .name("blp-pump-b".into())
            .spawn(move || {
                if let Err(e) = pump_b::run(config_b, cmd_b_rx) {
                    tracing::error!("PumpB exited with error: {e:?}");
                }
            })
            .map_err(|e| BlpAsyncError::Internal(format!("spawn pump_b: {e}")))?;

        // Start Lane C (slow/intraday)
        let config_c = config.clone();
        let pump_c = std::thread::Builder::new()
            .name("blp-pump-c".into())
            .spawn(move || {
                if let Err(e) = pump_c::run(config_c, cmd_c_rx) {
                    tracing::error!("PumpC exited with error: {e:?}");
                }
            })
            .map_err(|e| BlpAsyncError::Internal(format!("spawn pump_c: {e}")))?;

        Ok(Self {
            cmd_a: cmd_a_tx,
            cmd_b: cmd_b_tx,
            cmd_c: cmd_c_tx,
            _pump_a: pump_a,
            _pump_b: pump_b,
            _pump_c: pump_c,
            rt,
        })
    }

    // ─── Generic Request API ─────────────────────────────────────────────────

    /// Generic Bloomberg request - routes based on operation type.
    ///
    /// This is the primary API for all Bloomberg requests. The operation
    /// determines which lane handles the request:
    /// - IntradayBarRequest, IntradayTickRequest → Lane C
    /// - All other requests → Lane B
    pub async fn request(&self, params: RequestParams) -> Result<RecordBatch, BlpAsyncError> {
        let (tx, rx) = oneshot::channel();
        let lane = params.lane();

        let cmd = Command::Request { params, reply: tx };

        match lane {
            Lane::B => self.cmd_b.send(cmd).await,
            Lane::C => self.cmd_c.send(cmd).await,
            Lane::A => {
                return Err(BlpAsyncError::Internal(
                    "Lane A is for subscriptions, use subscribe() instead".into(),
                ))
            }
        }
        .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;

        rx.await
            .map_err(|_| BlpAsyncError::Internal("reply dropped".into()))?
            .map_err(BlpAsyncError::from)
    }

    /// Streaming generic request - routes based on operation type.
    pub async fn request_stream(
        &self,
        params: RequestParams,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(256);
        let lane = params.lane();

        let cmd = Command::RequestStream { params, stream: tx };

        match lane {
            Lane::B => self.cmd_b.send(cmd).await,
            Lane::C => self.cmd_c.send(cmd).await,
            Lane::A => {
                return Err(BlpAsyncError::Internal(
                    "Lane A is for subscriptions, use subscribe() instead".into(),
                ))
            }
        }
        .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;

        Ok(rx)
    }

    // ─── Subscriptions ───────────────────────────────────────────────────────

    /// Subscribe to real-time data - routes to Lane A.
    pub async fn subscribe(
        &self,
        topics: Vec<String>,
        fields: Vec<String>,
    ) -> Result<mpsc::Receiver<RecordBatch>, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(256);
        self.cmd_a
            .send(Command::Subscribe {
                topics,
                fields,
                stream: tx,
            })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(rx)
    }

    /// Unsubscribe by slab keys - routes to Lane A.
    pub async fn unsubscribe(&self, keys: Vec<SlabKey>) -> Result<(), BlpAsyncError> {
        self.cmd_a
            .send(Command::Unsubscribe { keys })
            .await
            .map_err(|_| BlpAsyncError::Internal("engine shutdown".into()))?;
        Ok(())
    }

    // ─── Field Type Resolution ──────────────────────────────────────────────

    /// Resolve field types for a list of fields.
    ///
    /// This queries //blp/apiflds for any fields not already in the cache,
    /// updates the cache, and returns a HashMap of field -> arrow_type_string.
    ///
    /// The resolution hierarchy is:
    /// 1. Manual overrides (passed in)
    /// 2. Physical cache (~/.xbbg/field_cache.parquet)
    /// 3. API query (//blp/apiflds FieldInfoRequest)
    /// 4. Defaults (based on request type)
    pub async fn resolve_field_types(
        &self,
        fields: &[String],
        manual_overrides: Option<&HashMap<String, String>>,
        default_type: &str,
    ) -> Result<HashMap<String, String>, BlpAsyncError> {
        use crate::field_cache::global_resolver;

        let resolver = global_resolver();

        // Find fields not in cache (and not manually overridden)
        let uncached: Vec<String> = fields
            .iter()
            .filter(|f| {
                // Skip if manually overridden
                if let Some(overrides) = manual_overrides {
                    if overrides.contains_key(*f) || overrides.contains_key(&f.to_uppercase()) {
                        return false;
                    }
                }
                // Check if in cache
                resolver.get(f).is_none()
            })
            .cloned()
            .collect();

        // Query //blp/apiflds for uncached fields
        if !uncached.is_empty() {
            tracing::debug!(fields = ?uncached, "Querying //blp/apiflds for field types");

            let params = RequestParams {
                service: "//blp/apiflds".to_string(),
                operation: "FieldInfoRequest".to_string(),
                extractor: ExtractorType::FieldInfo,
                field_ids: Some(uncached.clone()),
                ..Default::default()
            };

            match self.request(params).await {
                Ok(batch) => {
                    // Update cache from response
                    resolver.insert_from_response(&batch);

                    // Save cache to disk (async, don't block)
                    let resolver_clone = resolver.clone();
                    self.rt.spawn(async move {
                        if let Err(e) = resolver_clone.save_to_disk() {
                            tracing::warn!(error = %e, "Failed to save field cache");
                        }
                    });
                }
                Err(e) => {
                    tracing::warn!(error = %e, "Failed to query field types, using defaults");
                }
            }
        }

        // Now resolve all types using the updated cache
        Ok(resolver.resolve_types(fields, manual_overrides, default_type))
    }

    /// Pre-populate the field type cache for a list of fields.
    pub async fn cache_field_types(&self, fields: &[String]) -> Result<(), BlpAsyncError> {
        let _ = self.resolve_field_types(fields, None, "string").await?;
        Ok(())
    }

    /// Get field info from cache (doesn't query API).
    pub fn get_field_info(&self, field: &str) -> Option<crate::field_cache::FieldInfo> {
        crate::field_cache::global_resolver().get(field)
    }

    /// Clear the field type cache.
    pub fn clear_field_cache(&self) {
        crate::field_cache::global_resolver().clear();
    }

    /// Save the field type cache to disk.
    pub fn save_field_cache(&self) -> Result<(), String> {
        crate::field_cache::global_resolver().save_to_disk()
    }

    // ─── Admin ───────────────────────────────────────────────────────────────

    /// Graceful shutdown of all sessions.
    pub async fn shutdown(self) -> Result<(), BlpAsyncError> {
        // Send shutdown to all lanes
        let _ = self.cmd_a.send(Command::Shutdown).await;
        let _ = self.cmd_b.send(Command::Shutdown).await;
        let _ = self.cmd_c.send(Command::Shutdown).await;
        Ok(())
    }

    /// Get the tokio runtime (for spawning tasks).
    pub fn runtime(&self) -> &Arc<tokio::runtime::Runtime> {
        &self.rt
    }
}

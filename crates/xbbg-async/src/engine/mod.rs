//! Worker Pool Engine for Bloomberg API.
//!
//! Architecture:
//! - RequestWorkerPool: Pre-warmed workers for all request types (bdp/bdh/bds/bdib/bdtick)
//! - SubscriptionSessionPool: Pre-warmed sessions for subscriptions (each gets dedicated session)
//!
//! Workers use slab-indexed correlation IDs for O(1) dispatch.
//! Pool sizes are configurable with sensible defaults.

mod request_pool;
pub mod state;
mod subscription_pool;
mod worker;

use std::collections::HashMap;
use std::sync::Arc;

use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::BlpError;

use crate::errors::BlpAsyncError;

pub use request_pool::RequestWorkerPool;
pub use state::{OutputFormat, RequestState, SubscriptionState};
pub use subscription_pool::{SessionClaim, SubscriptionSessionPool};
pub use worker::{UnifiedRequestState, WorkerCommand, WorkerHandle};

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
    /// Output format (long, long_typed, long_metadata, wide)
    pub format: Option<String>,
}

/// Configuration for the Engine.
#[derive(Clone)]
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
    /// Number of request workers (default: 2)
    pub request_pool_size: usize,
    /// Number of subscription sessions (default: 4)
    pub subscription_pool_size: usize,
    /// Services to pre-warm on request workers
    pub warmup_services: Vec<String>,
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
            request_pool_size: 2,
            subscription_pool_size: 4,
            warmup_services: vec![
                "//blp/refdata".to_string(),
                "//blp/apiflds".to_string(),
            ],
        }
    }
}

/// Worker Pool Bloomberg Engine.
///
/// Uses pre-warmed worker pools for efficient request handling:
/// - RequestWorkerPool: Handles all request types with round-robin dispatch
/// - SubscriptionSessionPool: Provides isolated sessions for subscriptions
pub struct Engine {
    /// Pool of request workers
    request_pool: RequestWorkerPool,
    /// Pool of subscription sessions
    subscription_pool: Arc<SubscriptionSessionPool>,
    /// Tokio runtime for async ops
    rt: Arc<tokio::runtime::Runtime>,
    /// Configuration
    config: Arc<EngineConfig>,
}

impl Engine {
    /// Create and start a new Engine with worker pools.
    pub fn start(config: EngineConfig) -> Result<Self, BlpAsyncError> {
        let config = Arc::new(config);

        let rt = Arc::new(
            tokio::runtime::Builder::new_multi_thread()
                .enable_all()
                .build()
                .map_err(|e| BlpAsyncError::Internal(format!("tokio runtime: {e}")))?,
        );

        tracing::info!(
            request_pool_size = config.request_pool_size,
            subscription_pool_size = config.subscription_pool_size,
            "starting Engine with worker pools"
        );

        // Create request worker pool
        let request_pool = RequestWorkerPool::new(config.request_pool_size, config.clone())?;

        // Create subscription session pool
        let subscription_pool =
            Arc::new(SubscriptionSessionPool::new(config.subscription_pool_size, config.clone())?);

        tracing::info!("Engine started with worker pools");

        Ok(Self {
            request_pool,
            subscription_pool,
            rt,
            config,
        })
    }

    // ─── Generic Request API ─────────────────────────────────────────────────

    /// Generic Bloomberg request - dispatches to worker pool.
    ///
    /// All request types are handled by the same pool of workers.
    pub async fn request(&self, params: RequestParams) -> Result<RecordBatch, BlpAsyncError> {
        self.request_pool.request(params).await
    }

    /// Streaming generic request - dispatches to worker pool.
    pub async fn request_stream(
        &self,
        params: RequestParams,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        self.request_pool.request_stream(params).await
    }

    // ─── Subscriptions ───────────────────────────────────────────────────────

    /// Subscribe to real-time data.
    ///
    /// Claims a dedicated session from the pool for this subscription.
    /// The session is returned to the pool when the SubscriptionHandle is dropped.
    pub async fn subscribe(
        &self,
        topics: Vec<String>,
        fields: Vec<String>,
    ) -> Result<(mpsc::Receiver<RecordBatch>, SubscriptionHandle<'_>), BlpAsyncError> {
        let (tx, rx) = mpsc::channel(self.config.subscription_stream_capacity);

        // Claim a session from the pool
        let claim = self.subscription_pool.claim()?;

        // Start the subscription
        let keys = claim.subscribe(topics, fields, tx).await?;

        let handle = SubscriptionHandle {
            claim: Some(claim),
            keys,
        };

        Ok((rx, handle))
    }

    // ─── Field Type Resolution ──────────────────────────────────────────────

    /// Resolve field types for a list of fields.
    ///
    /// This queries //blp/apiflds for any fields not already in the cache,
    /// updates the cache, and returns a HashMap of field -> arrow_type_string.
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
                if let Some(overrides) = manual_overrides {
                    if overrides.contains_key(*f) || overrides.contains_key(&f.to_uppercase()) {
                        return false;
                    }
                }
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
                    resolver.insert_from_response(&batch);

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

    // ─── Pool Info ──────────────────────────────────────────────────────────

    /// Get the number of request workers.
    pub fn request_worker_count(&self) -> usize {
        self.request_pool.size()
    }

    /// Get the number of available subscription sessions.
    pub fn available_subscription_sessions(&self) -> usize {
        self.subscription_pool.available_count()
    }

    // ─── Admin ───────────────────────────────────────────────────────────────

    /// Graceful shutdown of all workers.
    pub fn shutdown(mut self) {
        tracing::info!("Engine shutdown requested");
        self.request_pool.shutdown();
        self.subscription_pool.shutdown();
    }

    /// Get the tokio runtime (for spawning tasks).
    pub fn runtime(&self) -> &Arc<tokio::runtime::Runtime> {
        &self.rt
    }
}

/// Handle for managing a subscription.
///
/// Releases the session back to the pool on drop.
pub struct SubscriptionHandle<'a> {
    claim: Option<SessionClaim<'a>>,
    keys: Vec<SlabKey>,
}

impl<'a> SubscriptionHandle<'a> {
    /// Explicitly unsubscribe and release the session.
    pub async fn unsubscribe(mut self) -> Result<(), BlpAsyncError> {
        if let Some(claim) = self.claim.take() {
            claim.unsubscribe(self.keys.clone()).await?;
        }
        Ok(())
    }

    /// Get the subscription keys (for debugging).
    pub fn keys(&self) -> &[SlabKey] {
        &self.keys
    }
}

impl<'a> Drop for SubscriptionHandle<'a> {
    fn drop(&mut self) {
        // Session is automatically released when claim is dropped
    }
}

// ─── Legacy Command Types (kept for pump_a compatibility) ──────────────────

/// Commands sent to subscription pumps.
#[allow(dead_code)]
pub(crate) enum Command {
    Subscribe {
        topics: Vec<String>,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
    },
    Unsubscribe {
        keys: Vec<SlabKey>,
    },
    Request {
        params: RequestParams,
        reply: tokio::sync::oneshot::Sender<Result<RecordBatch, BlpError>>,
    },
    RequestStream {
        params: RequestParams,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    },
    Shutdown,
}

// ─── Legacy Lane Types (deprecated) ────────────────────────────────────────

/// Lane designation - deprecated, kept for compatibility.
#[deprecated(note = "Lane routing replaced by worker pool dispatch")]
#[allow(dead_code)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Lane {
    A,
    B,
    C,
}

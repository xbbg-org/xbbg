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

use arrow::array::Array;
use arrow::record_batch::RecordBatch;
use tokio::sync::mpsc;

use xbbg_core::BlpError;

use crate::errors::BlpAsyncError;

pub use request_pool::RequestWorkerPool;
pub use state::{OutputFormat, SubscriptionState};
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

impl std::str::FromStr for OverflowPolicy {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "drop_newest" | "dropnewest" => Ok(Self::DropNewest),
            "drop_oldest" | "dropoldest" => Ok(Self::DropOldest),
            "block" => Ok(Self::Block),
            _ => Err(format!(
                "unknown overflow policy '{}': expected drop_newest, drop_oldest, or block",
                s
            )),
        }
    }
}

impl std::fmt::Display for OverflowPolicy {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::DropNewest => write!(f, "drop_newest"),
            Self::DropOldest => write!(f, "drop_oldest"),
            Self::Block => write!(f, "block"),
        }
    }
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
    /// BQL: Bloomberg Query Language responses
    Bql,
    /// BSRCH: Bloomberg Search responses
    Bsrch,
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
            "bql" => Some(Self::Bql),
            "bsrch" => Some(Self::Bsrch),
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
    /// Field overrides (for standard Bloomberg override format)
    pub overrides: Option<Vec<(String, String)>>,
    /// Generic request elements (for BQL expression, bsrch domain, etc.)
    pub elements: Option<Vec<(String, String)>>,
    /// JSON request body for complex nested structures (e.g., tasvc studyRequest)
    pub json_elements: Option<String>,
    /// Start date (YYYYMMDD for bdh)
    pub start_date: Option<String>,
    /// End date (YYYYMMDD for bdh)
    pub end_date: Option<String>,
    /// Start datetime (ISO for intraday)
    pub start_datetime: Option<String>,
    /// End datetime (ISO for intraday)
    pub end_datetime: Option<String>,
    /// Event type (TRADE, BID, ASK for intraday bars - singular)
    pub event_type: Option<String>,
    /// Event types (TRADE, BID, ASK for intraday ticks - array)
    pub event_types: Option<Vec<String>>,
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

/// Validation mode for request validation.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ValidationMode {
    /// Error on invalid fields/requests
    Strict,
    /// Warn but still send request
    Lenient,
    /// Skip validation entirely (default)
    #[default]
    Disabled,
}

impl std::str::FromStr for ValidationMode {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "strict" => Ok(Self::Strict),
            "lenient" => Ok(Self::Lenient),
            "disabled" | "off" | "none" => Ok(Self::Disabled),
            _ => Err(format!(
                "unknown validation mode '{}': expected strict, lenient, or disabled",
                s
            )),
        }
    }
}

impl std::fmt::Display for ValidationMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Strict => write!(f, "strict"),
            Self::Lenient => write!(f, "lenient"),
            Self::Disabled => write!(f, "disabled"),
        }
    }
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
    /// Validation mode for requests (default: Strict)
    pub validation_mode: ValidationMode,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            server_host: "localhost".to_string(),
            server_port: 8194,
            max_event_queue_size: 10_000,
            command_queue_size: 256,
            subscription_flush_threshold: 1,
            subscription_stream_capacity: 256,
            overflow_policy: OverflowPolicy::default(),
            request_pool_size: 2,
            subscription_pool_size: 4,
            warmup_services: vec![
                crate::services::Service::RefData.to_string(),
                crate::services::Service::ApiFlds.to_string(),
            ],
            validation_mode: ValidationMode::default(),
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
    /// Schema cache (in-memory + disk)
    schema_cache: crate::schema::SchemaCache,
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

        xbbg_log::info!(
            request_pool_size = config.request_pool_size,
            subscription_pool_size = config.subscription_pool_size,
            "starting Engine with worker pools"
        );

        // Create request worker pool
        let request_pool = RequestWorkerPool::new(config.request_pool_size, config.clone())?;

        // Create subscription session pool
        let subscription_pool = Arc::new(SubscriptionSessionPool::new(
            config.subscription_pool_size,
            config.clone(),
        )?);

        xbbg_log::info!("Engine started with worker pools");

        Ok(Self {
            request_pool,
            subscription_pool,
            rt,
            config,
            schema_cache: crate::schema::SchemaCache::new(),
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

    /// Subscribe to real-time market data (//blp/mktdata).
    ///
    /// Claims a dedicated session from the pool for this subscription.
    /// Returns a `SubscriptionStream` that provides:
    /// - Async iteration over incoming data
    /// - Dynamic add/remove of tickers
    /// - Explicit unsubscribe with optional drain
    ///
    /// The session is returned to the pool when the stream is dropped.
    pub async fn subscribe(
        &self,
        topics: Vec<String>,
        fields: Vec<String>,
    ) -> Result<SubscriptionStream, BlpAsyncError> {
        self.subscribe_with_options(crate::services::Service::MktData.to_string(), topics, fields, vec![])
            .await
    }

    /// Subscribe to real-time data with custom service and options.
    ///
    /// This is the generic subscription method that supports different services
    /// (e.g., //blp/mktdata, //blp/mktvwap) and subscription options.
    ///
    /// # Arguments
    /// * `service` - Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap")
    /// * `topics` - Securities to subscribe to
    /// * `fields` - Fields to subscribe to
    /// * `options` - Subscription options (e.g., ["VWAP_START_TIME=09:30"])
    pub async fn subscribe_with_options(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
    ) -> Result<SubscriptionStream, BlpAsyncError> {
        let (tx, rx) = mpsc::channel(self.config.subscription_stream_capacity);

        // Claim a session from the pool (uses Arc-based claim for 'static lifetime)
        let claim = self.subscription_pool.claim()?;

        // Start the subscription
        let keys = claim
            .subscribe(
                service.clone(),
                topics.clone(),
                fields.clone(),
                options.clone(),
                tx.clone(),
            )
            .await?;

        // Build topic -> key mapping
        let topic_to_key: std::collections::HashMap<String, SlabKey> =
            topics.iter().cloned().zip(keys.iter().cloned()).collect();

        let stream = SubscriptionStream {
            rx,
            tx,
            claim: Some(claim),
            keys,
            topics,
            fields,
            topic_to_key,
            service,
            options,
        };

        Ok(stream)
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
            xbbg_log::debug!(fields = ?uncached, "Querying //blp/apiflds for field types");

            let params = RequestParams {
                service: crate::services::Service::ApiFlds.to_string(),
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
                            xbbg_log::warn!(error = %e, "Failed to save field cache");
                        }
                    });
                }
                Err(e) => {
                    xbbg_log::warn!(error = %e, "Failed to query field types, using defaults");
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

    /// Validate Bloomberg field names.
    ///
    /// Queries `//blp/apiflds` for the given fields and returns a list of
    /// invalid field names (fields that Bloomberg doesn't recognize).
    ///
    /// # Example
    /// ```ignore
    /// let invalid = engine.validate_fields(&["PX_LAST", "INVALID_FIELD"]).await?;
    /// // invalid = ["INVALID_FIELD"]
    /// ```
    pub async fn validate_fields(&self, fields: &[String]) -> Result<Vec<String>, BlpAsyncError> {
        if fields.is_empty() {
            return Ok(Vec::new());
        }

        // Query //blp/apiflds for the fields
        let params = RequestParams {
            service: crate::services::Service::ApiFlds.to_string(),
            operation: "FieldInfoRequest".to_string(),
            extractor: ExtractorType::FieldInfo,
            field_ids: Some(fields.to_vec()),
            ..Default::default()
        };

        let batch = self.request(params).await?;

        // Get the field column from the response
        let field_col = batch
            .column_by_name("field")
            .and_then(|c| c.as_any().downcast_ref::<arrow::array::StringArray>());

        let valid_fields: std::collections::HashSet<String> = match field_col {
            Some(col) => (0..col.len())
                .filter_map(|i| {
                    if col.is_null(i) {
                        None
                    } else {
                        Some(col.value(i).to_uppercase())
                    }
                })
                .collect(),
            None => std::collections::HashSet::new(),
        };

        // Find fields that weren't returned (invalid)
        let invalid: Vec<String> = fields
            .iter()
            .filter(|f| !valid_fields.contains(&f.to_uppercase()))
            .cloned()
            .collect();

        Ok(invalid)
    }

    /// Check if field validation is enabled based on validation mode.
    pub fn is_field_validation_enabled(&self) -> bool {
        self.config.validation_mode != ValidationMode::Disabled
    }

    // ─── Schema Introspection ─────────────────────────────────────────────────

    /// Get the schema for a Bloomberg service.
    ///
    /// Checks the cache first; if not cached, introspects the service via a worker
    /// and caches the result both in memory and on disk.
    pub async fn get_schema(
        &self,
        service: &str,
    ) -> Result<Arc<crate::schema::ServiceSchema>, BlpAsyncError> {
        // Check cache first
        if let Some(schema) = self.schema_cache.get(service) {
            return Ok(schema);
        }

        // Introspect via worker
        let schema = self.request_pool.introspect_schema(service.to_string()).await?;

        // Cache and return
        Ok(self.schema_cache.insert(service, schema))
    }

    /// Get a specific operation's schema from a service.
    ///
    /// This is a convenience method that gets the full service schema and
    /// extracts the requested operation.
    pub async fn get_operation(
        &self,
        service: &str,
        operation: &str,
    ) -> Result<crate::schema::OperationSchema, BlpAsyncError> {
        let schema = self.get_schema(service).await?;

        schema
            .get_operation(operation)
            .cloned()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: format!("Operation '{}' not found in service '{}'", operation, service),
            })
    }

    /// List all operations for a service.
    pub async fn list_operations(&self, service: &str) -> Result<Vec<String>, BlpAsyncError> {
        let schema = self.get_schema(service).await?;
        Ok(schema.operation_names())
    }

    /// Get cached schema without triggering introspection.
    ///
    /// Returns None if the schema is not in the cache.
    pub fn get_cached_schema(&self, service: &str) -> Option<Arc<crate::schema::ServiceSchema>> {
        self.schema_cache.get(service)
    }

    /// Invalidate a cached schema (removes from memory and disk).
    pub fn invalidate_schema(&self, service: &str) {
        self.schema_cache.invalidate(service);
    }

    /// Clear all cached schemas.
    pub fn clear_schema_cache(&self) {
        self.schema_cache.clear();
    }

    /// List all cached service URIs.
    pub fn list_cached_schemas(&self) -> Vec<String> {
        self.schema_cache.list()
    }

    /// Get valid enum values for a request element.
    ///
    /// Returns None if the element is not an enum or doesn't exist.
    pub async fn get_enum_values(
        &self,
        service: &str,
        operation: &str,
        element: &str,
    ) -> Result<Option<Vec<String>>, BlpAsyncError> {
        let op_schema = self.get_operation(service, operation).await?;
        Ok(op_schema.find_request_enum_values(element))
    }

    /// List all valid element names for a request.
    ///
    /// Returns None if the operation doesn't exist.
    pub async fn list_valid_elements(
        &self,
        service: &str,
        operation: &str,
    ) -> Result<Option<Vec<String>>, BlpAsyncError> {
        let op_schema = self.get_operation(service, operation).await?;
        Ok(Some(op_schema.request_element_names()))
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

    /// Signal shutdown to all workers (non-blocking).
    ///
    /// Workers will terminate when they see the shutdown signal.
    /// Used by Drop and Python atexit to avoid blocking.
    pub fn signal_shutdown(&self) {
        xbbg_log::info!("Engine signal_shutdown requested");
        self.request_pool.signal_shutdown();
        self.subscription_pool.signal_shutdown();
    }

    /// Graceful shutdown - waits for all workers to finish (blocking).
    ///
    /// Use this for clean shutdown when you can afford to wait.
    /// Consumes the Engine.
    pub fn shutdown_blocking(mut self) {
        xbbg_log::info!("Engine shutdown_blocking requested");
        self.request_pool.shutdown_blocking();
        self.subscription_pool.shutdown_blocking();
    }

    /// Get the tokio runtime (for spawning tasks).
    pub fn runtime(&self) -> &Arc<tokio::runtime::Runtime> {
        &self.rt
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        // Non-blocking: signal all workers to shut down.
        // For blocking shutdown, call shutdown_blocking() explicitly before dropping.
        self.signal_shutdown();
    }
}

/// Stream for receiving real-time market data with dynamic subscription control.
///
/// Provides async iteration over incoming data and methods to dynamically
/// add/remove tickers while the subscription is active.
///
/// The underlying session is released back to the pool on drop.
pub struct SubscriptionStream {
    /// Receiver for incoming data batches.
    rx: mpsc::Receiver<RecordBatch>,
    /// Sender for adding new topics (shares channel with existing subs).
    tx: mpsc::Sender<RecordBatch>,
    /// Session claim (released on drop).
    claim: Option<SessionClaim>,
    /// Current slab keys for all subscribed topics.
    keys: Vec<SlabKey>,
    /// Currently subscribed topics.
    topics: Vec<String>,
    /// Subscribed fields.
    fields: Vec<String>,
    /// Mapping from topic to its slab key for removal.
    topic_to_key: std::collections::HashMap<String, SlabKey>,
    /// Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap").
    service: String,
    /// Subscription options.
    options: Vec<String>,
}

impl SubscriptionStream {
    /// Receive the next batch of data.
    ///
    /// Returns None when the subscription is closed.
    pub async fn next(&mut self) -> Option<RecordBatch> {
        self.rx.recv().await
    }

    /// Try to receive data without blocking.
    pub fn try_next(&mut self) -> Option<RecordBatch> {
        self.rx.try_recv().ok()
    }

    /// Add tickers to the subscription dynamically.
    ///
    /// New tickers will start receiving data on the same stream.
    pub async fn add(&mut self, topics: Vec<String>) -> Result<(), BlpAsyncError> {
        let claim = self
            .claim
            .as_ref()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "subscription already closed".to_string(),
            })?;

        // Filter out already subscribed topics
        let new_topics: Vec<String> = topics
            .into_iter()
            .filter(|t| !self.topic_to_key.contains_key(t))
            .collect();

        if new_topics.is_empty() {
            return Ok(());
        }

        xbbg_log::debug!(topics = ?new_topics, "adding topics to subscription");

        // Add new topics using the same stream sender
        let new_keys = claim
            .add_topics(
                self.service.clone(),
                new_topics.clone(),
                self.fields.clone(),
                self.options.clone(),
                self.tx.clone(),
            )
            .await?;

        // Track new topics
        for (topic, key) in new_topics.iter().zip(new_keys.iter()) {
            self.topic_to_key.insert(topic.clone(), *key);
            self.topics.push(topic.clone());
            self.keys.push(*key);
        }

        Ok(())
    }

    /// Remove tickers from the subscription dynamically.
    ///
    /// Removed tickers will stop receiving data.
    pub async fn remove(&mut self, topics: Vec<String>) -> Result<(), BlpAsyncError> {
        let claim = self
            .claim
            .as_ref()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "subscription already closed".to_string(),
            })?;

        // Find keys for topics to remove
        let mut keys_to_remove = Vec::new();
        for topic in &topics {
            if let Some(key) = self.topic_to_key.remove(topic) {
                keys_to_remove.push(key);
                self.topics.retain(|t| t != topic);
                self.keys.retain(|k| *k != key);
            }
        }

        if keys_to_remove.is_empty() {
            return Ok(());
        }

        xbbg_log::debug!(topics = ?topics, keys = ?keys_to_remove, "removing topics from subscription");

        claim.unsubscribe(keys_to_remove).await
    }

    /// Get the currently subscribed topics.
    pub fn topics(&self) -> &[String] {
        &self.topics
    }

    /// Get the subscribed fields.
    pub fn fields(&self) -> &[String] {
        &self.fields
    }

    /// Check if any topics are still subscribed.
    pub fn is_active(&self) -> bool {
        !self.keys.is_empty() && self.claim.is_some()
    }

    /// Unsubscribe from all topics and close the stream.
    ///
    /// If `drain` is true, returns remaining buffered batches before closing.
    pub async fn unsubscribe(mut self, drain: bool) -> Result<Vec<RecordBatch>, BlpAsyncError> {
        let mut remaining = Vec::new();

        if drain {
            // Drain any remaining batches
            while let Ok(batch) = self.rx.try_recv() {
                remaining.push(batch);
            }
        }

        if let Some(claim) = self.claim.take() {
            if !self.keys.is_empty() {
                claim.unsubscribe(self.keys.clone()).await?;
            }
        }

        self.keys.clear();
        self.topics.clear();
        self.topic_to_key.clear();

        Ok(remaining)
    }

    /// Close the stream without explicit unsubscribe (drop handles cleanup).
    pub fn close(mut self) {
        self.claim.take(); // Session returns to pool on drop
    }

    /// Destructure the stream into its component parts.
    ///
    /// Used by PyO3 layer to separate rx (for iteration) from claim (for add/remove)
    /// so they can use independent locks and avoid contention.
    ///
    /// Consumes self without running Drop (since we're taking ownership of parts).
    #[allow(clippy::type_complexity)]
    pub fn into_parts(
        self,
    ) -> (
        mpsc::Receiver<RecordBatch>,
        mpsc::Sender<RecordBatch>,
        SessionClaim,
        Vec<SlabKey>,
        std::collections::HashMap<String, SlabKey>,
        String,      // service
        Vec<String>, // options
    ) {
        use std::mem::ManuallyDrop;
        use std::ptr;

        // Prevent Drop from running — we're taking ownership of each field individually.
        let mut this = ManuallyDrop::new(self);

        // SAFETY: We read each field exactly once from the ManuallyDrop wrapper.
        // The wrapper prevents the destructor from running, so no double-free.
        unsafe {
            let rx = ptr::read(&this.rx);
            let tx = ptr::read(&this.tx);
            let claim = ptr::read(&mut this.claim)
                .expect("into_parts called on already-closed stream");
            let keys = ptr::read(&this.keys);
            let topic_to_key = ptr::read(&this.topic_to_key);
            let service = ptr::read(&this.service);
            let options = ptr::read(&this.options);

            (rx, tx, claim, keys, topic_to_key, service, options)
        }
    }
}

impl Drop for SubscriptionStream {
    fn drop(&mut self) {
        // Session is automatically released when claim is dropped
    }
}

//! Worker Pool Engine for Bloomberg API.
//!
//! Architecture:
//! - RequestWorkerPool: Pre-warmed workers for all request types (bdp/bdh/bds/bdib/bdtick)
//! - SubscriptionSessionPool: Pre-warmed sessions for subscriptions (each gets dedicated session)
//!
//! Workers use slab-indexed correlation IDs for O(1) dispatch.
//! Pool sizes are configurable with sensible defaults.

mod exchange;
mod exchange_cache;
mod request_pool;
pub mod state;
mod subscription_pool;
mod worker;

use std::collections::{HashMap, HashSet};
use std::str::FromStr;
use std::sync::Arc;

use arrow::array::Array;
use arrow::record_batch::RecordBatch;
use parking_lot::Mutex;
use tokio::sync::mpsc;

use xbbg_core::BlpError;

use crate::errors::BlpAsyncError;
use crate::request_builder::RequestBuilder;
use crate::services::{Operation, Service};
use exchange_cache::ExchangeCache;

// ExtractorType is defined in services.rs (generated from defs/bloomberg.toml).
// Re-export here so existing `use xbbg_async::engine::ExtractorType` paths keep working.
pub use crate::services::ExtractorType;

pub use request_pool::RequestWorkerPool;
use state::SubscriptionMetrics;
pub use state::{OutputFormat, SubscriptionState};
pub use subscription_pool::{SessionClaim, SubscriptionCommandHandle, SubscriptionSessionPool};
pub use worker::{UnifiedRequestState, WorkerCommand, WorkerHandle};

fn parse_operation_lossless(operation: &str) -> Operation {
    match Operation::from_str(operation) {
        Ok(operation) => operation,
        Err(never) => match never {},
    }
}

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

/// Why Bloomberg stopped a single subscribed topic.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SubscriptionFailureKind {
    Failure,
    Terminated,
}

impl SubscriptionFailureKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Failure => "failure",
            Self::Terminated => "terminated",
        }
    }
}

/// Recorded non-fatal failure for a single topic in a multi-topic subscription.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SubscriptionFailureInfo {
    pub topic: String,
    pub reason: String,
    pub kind: SubscriptionFailureKind,
}

/// Shared subscription status visible to worker and consumer-facing handles.
#[derive(Default)]
pub struct SubscriptionStatusState {
    keys: Vec<SlabKey>,
    topics: Vec<String>,
    topic_to_key: HashMap<String, SlabKey>,
    metrics: HashMap<SlabKey, Arc<SubscriptionMetrics>>,
    failures: Vec<SubscriptionFailureInfo>,
}

pub type SharedSubscriptionStatus = Arc<Mutex<SubscriptionStatusState>>;

impl SubscriptionStatusState {
    pub fn from_active(
        topics: Vec<String>,
        keys: Vec<SlabKey>,
        metrics: HashMap<SlabKey, Arc<SubscriptionMetrics>>,
    ) -> Self {
        let topic_to_key = topics.iter().cloned().zip(keys.iter().copied()).collect();
        Self {
            keys,
            topics,
            topic_to_key,
            metrics,
            failures: Vec::new(),
        }
    }

    pub fn add_active(
        &mut self,
        topics: &[String],
        keys: &[SlabKey],
        metrics: Vec<Arc<SubscriptionMetrics>>,
    ) {
        for ((topic, key), metric) in topics.iter().zip(keys.iter()).zip(metrics.into_iter()) {
            self.topic_to_key.insert(topic.clone(), *key);
            self.topics.push(topic.clone());
            self.keys.push(*key);
            self.metrics.insert(*key, metric);
        }
    }

    pub fn remove_topic(&mut self, topic: &str) -> Option<SlabKey> {
        let key = self.topic_to_key.remove(topic)?;
        self.topics.retain(|existing| existing != topic);
        self.keys.retain(|existing| *existing != key);
        self.metrics.remove(&key);
        Some(key)
    }

    pub fn remove_key(&mut self, key: SlabKey) -> Option<String> {
        let topic = self
            .topic_to_key
            .iter()
            .find_map(|(topic, existing_key)| (*existing_key == key).then(|| topic.clone()))?;
        self.remove_topic(&topic);
        Some(topic)
    }

    pub fn record_failure(
        &mut self,
        key: SlabKey,
        reason: String,
        kind: SubscriptionFailureKind,
    ) -> Option<String> {
        let topic = self.remove_key(key)?;
        self.failures.push(SubscriptionFailureInfo {
            topic: topic.clone(),
            reason,
            kind,
        });
        Some(topic)
    }

    pub fn clear_active(&mut self) {
        self.keys.clear();
        self.topics.clear();
        self.topic_to_key.clear();
        self.metrics.clear();
    }

    pub fn keys(&self) -> &[SlabKey] {
        &self.keys
    }

    pub fn topics(&self) -> &[String] {
        &self.topics
    }

    pub fn fields_metrics(&self) -> &HashMap<SlabKey, Arc<SubscriptionMetrics>> {
        &self.metrics
    }

    pub fn topic_to_key(&self) -> &HashMap<String, SlabKey> {
        &self.topic_to_key
    }

    pub fn failures(&self) -> &[SubscriptionFailureInfo] {
        &self.failures
    }

    pub fn has_active_topics(&self) -> bool {
        !self.keys.is_empty()
    }
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
    /// Actual Bloomberg operation name when using the RawRequest marker.
    pub request_operation: Option<String>,
    /// Extractor type hint for Arrow conversion
    pub extractor: ExtractorType,
    /// Whether extractor was explicitly provided by the caller.
    pub extractor_set: bool,
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
    /// Raw kwargs to route into elements/overrides using schema-driven logic.
    pub kwargs: Option<HashMap<String, String>>,
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
    /// Include security error rows in RefData long output when present.
    pub include_security_errors: bool,
    /// Optional per-request field validation override.
    ///
    /// - Some(true): force strict field validation for this request
    /// - Some(false): disable field validation for this request
    /// - None: follow engine-level validation_mode
    pub validate_fields: Option<bool>,
    /// Search spec for FieldSearchRequest (//blp/apiflds)
    pub search_spec: Option<String>,
    /// Field IDs for FieldInfoRequest (//blp/apiflds)
    pub field_ids: Option<Vec<String>>,
    /// Output format (long, long_typed, long_metadata, wide)
    pub format: Option<String>,
}

impl RequestParams {
    pub(crate) fn is_raw_request(&self) -> bool {
        matches!(
            parse_operation_lossless(&self.operation),
            Operation::RawRequest
        )
    }

    pub(crate) fn effective_operation(&self) -> &str {
        if self.is_raw_request() {
            self.request_operation.as_deref().unwrap_or_default()
        } else {
            &self.operation
        }
    }

    /// Apply default values derived from operation semantics.
    pub fn with_defaults(mut self) -> Self {
        if !self.extractor_set {
            let operation = parse_operation_lossless(&self.operation);
            self.extractor = operation.default_extractor();
        }
        self
    }

    /// Validate request parameters for known Bloomberg operations.
    pub fn validate(&self) -> Result<(), BlpAsyncError> {
        if self.service.is_empty() {
            return Err(BlpAsyncError::ConfigError {
                detail: "service is required".to_string(),
            });
        }

        let operation = parse_operation_lossless(&self.operation);
        if matches!(operation, Operation::RawRequest) {
            if self
                .request_operation
                .as_ref()
                .is_none_or(|operation| operation.is_empty())
            {
                return Err(BlpAsyncError::ConfigError {
                    detail: "request_operation is required for RawRequest".to_string(),
                });
            }
        } else if self.operation.is_empty() {
            return Err(BlpAsyncError::ConfigError {
                detail: "operation is required".to_string(),
            });
        }

        match operation {
            Operation::ReferenceData => self.validate_reference_data(),
            Operation::HistoricalData => self.validate_historical_data(),
            Operation::IntradayBar => self.validate_intraday_bar(),
            Operation::IntradayTick => self.validate_intraday_tick(),
            Operation::FieldInfo | Operation::FieldSearch => {
                self.validate_field_request(&operation)
            }
            // Unknown/custom operations run in power-user mode.
            Operation::Beqs
            | Operation::PortfolioData
            | Operation::InstrumentList
            | Operation::CurveList
            | Operation::GovtList
            | Operation::BqlSendQuery
            | Operation::ExcelGetGrid
            | Operation::StudyRequest
            | Operation::RawRequest
            | Operation::Custom(_) => Ok(()),
        }
    }

    fn validate_reference_data(&self) -> Result<(), BlpAsyncError> {
        if !self.has_securities() {
            return Err(BlpAsyncError::ConfigError {
                detail: "securities is required for ReferenceDataRequest".to_string(),
            });
        }

        if !self.has_fields() {
            return Err(BlpAsyncError::ConfigError {
                detail: "fields is required for ReferenceDataRequest".to_string(),
            });
        }

        Ok(())
    }

    fn validate_historical_data(&self) -> Result<(), BlpAsyncError> {
        if !self.has_securities() {
            return Err(BlpAsyncError::ConfigError {
                detail: "securities is required for HistoricalDataRequest".to_string(),
            });
        }

        if !self.has_fields() {
            return Err(BlpAsyncError::ConfigError {
                detail: "fields is required for HistoricalDataRequest".to_string(),
            });
        }

        if !self.has_start_date() {
            return Err(BlpAsyncError::ConfigError {
                detail: "start_date is required for HistoricalDataRequest".to_string(),
            });
        }

        if !self.has_end_date() {
            return Err(BlpAsyncError::ConfigError {
                detail: "end_date is required for HistoricalDataRequest".to_string(),
            });
        }

        Ok(())
    }

    fn validate_intraday_bar(&self) -> Result<(), BlpAsyncError> {
        if !self.has_security() {
            return Err(BlpAsyncError::ConfigError {
                detail: "security is required for IntradayBarRequest".to_string(),
            });
        }

        if !self.has_event_type() {
            return Err(BlpAsyncError::ConfigError {
                detail: "event_type is required for IntradayBarRequest".to_string(),
            });
        }

        if self.interval.is_none() {
            return Err(BlpAsyncError::ConfigError {
                detail: "interval is required for IntradayBarRequest".to_string(),
            });
        }

        if !self.has_start_datetime() {
            return Err(BlpAsyncError::ConfigError {
                detail: "start_datetime is required for IntradayBarRequest".to_string(),
            });
        }

        if !self.has_end_datetime() {
            return Err(BlpAsyncError::ConfigError {
                detail: "end_datetime is required for IntradayBarRequest".to_string(),
            });
        }

        Ok(())
    }

    fn validate_intraday_tick(&self) -> Result<(), BlpAsyncError> {
        if !self.has_security() {
            return Err(BlpAsyncError::ConfigError {
                detail: "security is required for IntradayTickRequest".to_string(),
            });
        }

        if !self.has_start_datetime() {
            return Err(BlpAsyncError::ConfigError {
                detail: "start_datetime is required for IntradayTickRequest".to_string(),
            });
        }

        if !self.has_end_datetime() {
            return Err(BlpAsyncError::ConfigError {
                detail: "end_datetime is required for IntradayTickRequest".to_string(),
            });
        }

        Ok(())
    }

    fn validate_field_request(&self, operation: &Operation) -> Result<(), BlpAsyncError> {
        let has_fields = self.has_fields();

        match operation {
            Operation::FieldInfo => {
                let has_field_ids = self.field_ids.as_ref().is_some_and(|ids| !ids.is_empty());
                if !has_fields && !has_field_ids {
                    return Err(BlpAsyncError::ConfigError {
                        detail: "fields is required for field metadata requests".to_string(),
                    });
                }
            }
            Operation::FieldSearch => {
                let has_search_spec = self.search_spec.as_ref().is_some_and(|s| !s.is_empty());
                if !has_fields && !has_search_spec {
                    return Err(BlpAsyncError::ConfigError {
                        detail: "fields is required for field metadata requests".to_string(),
                    });
                }
            }
            _ => {}
        }

        Ok(())
    }

    fn has_securities(&self) -> bool {
        self.securities
            .as_ref()
            .is_some_and(|values| !values.is_empty())
    }

    fn has_security(&self) -> bool {
        self.security
            .as_ref()
            .is_some_and(|value| !value.is_empty())
    }

    fn has_fields(&self) -> bool {
        self.fields
            .as_ref()
            .is_some_and(|values| !values.is_empty())
    }

    fn has_start_date(&self) -> bool {
        self.start_date
            .as_ref()
            .is_some_and(|value| !value.is_empty())
    }

    fn has_end_date(&self) -> bool {
        self.end_date
            .as_ref()
            .is_some_and(|value| !value.is_empty())
    }

    fn has_start_datetime(&self) -> bool {
        self.start_datetime
            .as_ref()
            .is_some_and(|value| !value.is_empty())
    }

    fn has_end_datetime(&self) -> bool {
        self.end_datetime
            .as_ref()
            .is_some_and(|value| !value.is_empty())
    }

    fn has_event_type(&self) -> bool {
        self.event_type
            .as_ref()
            .is_some_and(|value| !value.is_empty())
    }
}

fn merge_raw_kwargs_into_elements(params: &mut RequestParams, kwargs: HashMap<String, String>) {
    if kwargs.is_empty() {
        return;
    }

    let mut keys: Vec<String> = kwargs.keys().cloned().collect();
    keys.sort();

    let elements = params.elements.get_or_insert_with(Vec::new);
    for key in keys {
        if let Some(value) = kwargs.get(&key) {
            elements.push((key, value.clone()));
        }
    }
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
    /// Custom path for the field cache JSON file (default: ~/.xbbg/field_cache.json)
    pub field_cache_path: Option<std::path::PathBuf>,
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
            subscription_pool_size: 1,
            warmup_services: vec![
                crate::services::Service::RefData.to_string(),
                crate::services::Service::ApiFlds.to_string(),
            ],
            validation_mode: ValidationMode::default(),
            field_cache_path: None,
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
    /// Exchange metadata cache (in-memory + disk)
    exchange_cache: ExchangeCache,
}

impl Engine {
    /// Create and start a new Engine with worker pools.
    pub fn start(config: EngineConfig) -> Result<Self, BlpAsyncError> {
        let config = Arc::new(config);

        // Initialize field cache with configured path (must happen before any field resolution)
        crate::field_cache::init_global_resolver(config.field_cache_path.clone());

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

        let total_sessions = config.request_pool_size + config.subscription_pool_size;
        xbbg_log::info!(
            request_workers = config.request_pool_size,
            subscription_workers = config.subscription_pool_size,
            total_bloomberg_sessions = total_sessions,
            host = %config.server_host,
            port = config.server_port,
            "Engine ready"
        );

        Ok(Self {
            request_pool,
            subscription_pool,
            rt,
            config,
            schema_cache: crate::schema::SchemaCache::new(),
            exchange_cache: ExchangeCache::new(),
        })
    }

    // ─── Generic Request API ─────────────────────────────────────────────────

    /// Generic Bloomberg request - dispatches to worker pool.
    ///
    /// All request types are handled by the same pool of workers.
    pub async fn request(&self, params: RequestParams) -> Result<RecordBatch, BlpAsyncError> {
        let params = self.prepare_request_params(params)?;
        self.maybe_validate_request_fields(&params).await?;
        self.request_pool.request(params).await
    }

    /// Streaming generic request - dispatches to worker pool.
    pub async fn request_stream(
        &self,
        params: RequestParams,
    ) -> Result<mpsc::Receiver<Result<RecordBatch, BlpError>>, BlpAsyncError> {
        let params = self.prepare_request_params(params)?;
        self.maybe_validate_request_fields(&params).await?;
        self.request_pool.request_stream(params).await
    }

    /// Resolve defaults, validate, and schema-route kwargs before dispatch.
    fn prepare_request_params(
        &self,
        params: RequestParams,
    ) -> Result<RequestParams, BlpAsyncError> {
        let mut params = params.with_defaults();
        params.validate()?;

        let kwargs = params.kwargs.take().unwrap_or_default();
        if params.is_raw_request() {
            merge_raw_kwargs_into_elements(&mut params, kwargs);
            return Ok(params);
        }

        let routed = RequestBuilder::route_kwargs(
            &self.schema_cache,
            &params.service,
            &params.operation,
            kwargs,
            params.overrides.take(),
        );

        if !routed.elements.is_empty() {
            params
                .elements
                .get_or_insert_with(Vec::new)
                .extend(routed.elements);
        }

        params.overrides = if routed.overrides.is_empty() {
            None
        } else {
            Some(routed.overrides)
        };

        for warning in routed.warnings {
            xbbg_log::warn!(
                service = %params.service,
                operation = %params.operation,
                warning = %warning,
                "request parameter routing warning"
            );
        }

        Ok(params)
    }

    /// Validate request fields against Bloomberg field metadata when enabled.
    async fn maybe_validate_request_fields(
        &self,
        params: &RequestParams,
    ) -> Result<(), BlpAsyncError> {
        let validation_mode = match params.validate_fields {
            Some(true) => ValidationMode::Strict,
            Some(false) => ValidationMode::Disabled,
            None => self.config.validation_mode,
        };

        if validation_mode == ValidationMode::Disabled {
            return Ok(());
        }

        if params.service != Service::RefData.to_string() {
            return Ok(());
        }

        let operation = parse_operation_lossless(&params.operation);
        if !matches!(
            operation,
            Operation::ReferenceData | Operation::HistoricalData
        ) {
            return Ok(());
        }

        let Some(fields) = params.fields.as_ref() else {
            return Ok(());
        };
        if fields.is_empty() {
            return Ok(());
        }

        let invalid_fields = self.validate_fields(fields).await?;
        if invalid_fields.is_empty() {
            return Ok(());
        }

        let detail = format!("Unknown Bloomberg field(s): {}", invalid_fields.join(", "));
        if validation_mode == ValidationMode::Lenient {
            xbbg_log::warn!(
                service = %params.service,
                operation = %params.operation,
                invalid_fields = ?invalid_fields,
                "field validation warning"
            );
            return Ok(());
        }

        Err(BlpAsyncError::ConfigError { detail })
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
        self.subscribe_with_options(
            crate::services::Service::MktData.to_string(),
            topics,
            fields,
            vec![],
            None,
            None,
            None,
        )
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
    #[allow(clippy::too_many_arguments)]
    pub async fn subscribe_with_options(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        stream_capacity: Option<usize>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
    ) -> Result<SubscriptionStream, BlpAsyncError> {
        let (tx, rx) =
            mpsc::channel(stream_capacity.unwrap_or(self.config.subscription_stream_capacity));
        let status = Arc::new(Mutex::new(SubscriptionStatusState::default()));

        // Claim a session from the pool (uses Arc-based claim for 'static lifetime)
        let claim = self.subscription_pool.claim()?;

        // Start the subscription
        let (keys, raw_metrics) = claim
            .subscribe(
                service.clone(),
                topics.clone(),
                fields.clone(),
                options.clone(),
                flush_threshold,
                overflow_policy,
                tx.clone(),
                status.clone(),
            )
            .await?;

        let metrics = keys.iter().cloned().zip(raw_metrics).collect();
        *status.lock() = SubscriptionStatusState::from_active(topics.clone(), keys, metrics);

        let stream = SubscriptionStream {
            rx,
            tx,
            claim: Some(claim),
            fields,
            service,
            options,
            status,
            flush_threshold,
            overflow_policy,
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

    /// Get field cache statistics including the active cache file path.
    pub fn field_cache_stats(&self) -> (usize, std::path::PathBuf) {
        crate::field_cache::global_resolver().stats()
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

        let params = self.prepare_request_params(params)?;
        let batch = self.request_pool.request(params).await?;

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
        let schema = self
            .request_pool
            .introspect_schema(service.to_string())
            .await?;

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
                detail: format!(
                    "Operation '{}' not found in service '{}'",
                    operation, service
                ),
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
/// Data arrives as `Result<RecordBatch, BlpError>`:
/// - `Ok(batch)` — normal data
/// - `Err(error)` — subscription failure, session death, etc.
///
/// The underlying session is released back to the pool on drop.
pub struct SubscriptionStream {
    /// Receiver for incoming data batches (or errors).
    rx: mpsc::Receiver<Result<RecordBatch, BlpError>>,
    /// Sender for adding new topics (shares channel with existing subs).
    tx: mpsc::Sender<Result<RecordBatch, BlpError>>,
    /// Session claim (released on drop).
    claim: Option<SessionClaim>,
    /// Subscribed fields.
    fields: Vec<String>,
    /// Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap").
    service: String,
    /// Subscription options.
    options: Vec<String>,
    /// Shared active/failed topic status.
    status: SharedSubscriptionStatus,
    /// Optional flush threshold override.
    flush_threshold: Option<usize>,
    /// Optional overflow policy override.
    overflow_policy: Option<OverflowPolicy>,
}

impl SubscriptionStream {
    fn command_handle(&self) -> Result<SubscriptionCommandHandle, BlpAsyncError> {
        self.claim
            .as_ref()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "subscription already closed".to_string(),
            })?
            .command_handle()
    }

    /// Receive the next batch of data or an error.
    ///
    /// Returns:
    /// - `Some(Ok(batch))` — normal data
    /// - `Some(Err(error))` — subscription failure, session death, etc.
    /// - `None` — subscription is closed
    pub async fn next(&mut self) -> Option<Result<RecordBatch, BlpError>> {
        self.rx.recv().await
    }

    /// Try to receive data without blocking.
    pub fn try_next(&mut self) -> Option<Result<RecordBatch, BlpError>> {
        self.rx.try_recv().ok()
    }

    /// Add tickers to the subscription dynamically.
    ///
    /// New tickers will start receiving data on the same stream.
    pub async fn add(&mut self, topics: Vec<String>) -> Result<(), BlpAsyncError> {
        let command = self.command_handle()?;
        let mut seen_topics = HashSet::new();
        let status = self.status.lock();

        // Filter out already subscribed topics
        let new_topics: Vec<String> = topics
            .into_iter()
            .filter(|t| !status.topic_to_key().contains_key(t) && seen_topics.insert(t.clone()))
            .collect();
        drop(status);

        if new_topics.is_empty() {
            return Ok(());
        }

        xbbg_log::debug!(topics = ?new_topics, "adding topics to subscription");

        // Add new topics using the same stream sender
        let (new_keys, new_metrics) = command
            .add_topics(
                self.service.clone(),
                new_topics.clone(),
                self.fields.clone(),
                self.options.clone(),
                self.flush_threshold,
                self.overflow_policy,
                self.tx.clone(),
                self.status.clone(),
            )
            .await?;

        self.status
            .lock()
            .add_active(&new_topics, &new_keys, new_metrics);

        Ok(())
    }

    /// Remove tickers from the subscription dynamically.
    ///
    /// Removed tickers will stop receiving data.
    pub async fn remove(&mut self, topics: Vec<String>) -> Result<(), BlpAsyncError> {
        let command = self.command_handle()?;
        let mut seen_keys = HashSet::new();
        let status = self.status.lock();

        // Find keys for topics to remove
        let mut keys_to_remove = Vec::new();
        let mut topics_to_remove = Vec::new();
        for topic in topics {
            if let Some(&key) = status.topic_to_key().get(&topic) {
                if seen_keys.insert(key) {
                    keys_to_remove.push(key);
                    topics_to_remove.push(topic);
                }
            }
        }
        drop(status);

        if keys_to_remove.is_empty() {
            return Ok(());
        }

        xbbg_log::debug!(topics = ?topics_to_remove, keys = ?keys_to_remove, "removing topics from subscription");

        command.unsubscribe(keys_to_remove.clone()).await?;

        let mut status = self.status.lock();
        for topic in topics_to_remove {
            status.remove_topic(&topic);
        }

        Ok(())
    }

    /// Get the currently subscribed topics.
    pub fn topics(&self) -> Vec<String> {
        self.status.lock().topics().to_vec()
    }

    /// Get the subscribed fields.
    pub fn fields(&self) -> &[String] {
        &self.fields
    }

    /// Check if any topics are still subscribed.
    pub fn is_active(&self) -> bool {
        self.claim.is_some() && self.status.lock().has_active_topics()
    }

    /// Unsubscribe from all topics and close the stream.
    ///
    /// If `drain` is true, returns remaining buffered batches before closing.
    /// Errors in the drain are silently discarded — only successful batches are returned.
    pub async fn unsubscribe(mut self, drain: bool) -> Result<Vec<RecordBatch>, BlpAsyncError> {
        let mut remaining = Vec::new();

        if drain {
            // Drain any remaining batches (skip errors)
            while let Ok(item) = self.rx.try_recv() {
                if let Ok(batch) = item {
                    remaining.push(batch);
                }
            }
        }

        if let Some(claim) = self.claim.take() {
            let keys = self.status.lock().keys().to_vec();
            if !keys.is_empty() {
                claim.unsubscribe(keys).await?;
            }
        }

        self.status.lock().clear_active();

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
    ///
    /// Returns an error if the stream was already closed and no longer owns a session claim.
    #[allow(clippy::type_complexity)]
    pub fn into_parts(
        self,
    ) -> Result<
        (
            mpsc::Receiver<Result<RecordBatch, BlpError>>,
            mpsc::Sender<Result<RecordBatch, BlpError>>,
            SessionClaim,
            SharedSubscriptionStatus,
            Option<usize>,          // flush_threshold
            Option<OverflowPolicy>, // overflow_policy
            String,                 // service
            Vec<String>,            // options
        ),
        BlpError,
    > {
        use std::mem::ManuallyDrop;
        use std::ptr;

        // Prevent Drop from running — we're taking ownership of each field individually.
        let this = ManuallyDrop::new(self);

        // SAFETY: We read each field exactly once from the ManuallyDrop wrapper.
        // The wrapper prevents the destructor from running, so no double-free.
        unsafe {
            let rx = ptr::read(&this.rx);
            let tx = ptr::read(&this.tx);
            let claim = ptr::read(&this.claim);
            let status = ptr::read(&this.status);
            let flush_threshold = ptr::read(&this.flush_threshold);
            let overflow_policy = ptr::read(&this.overflow_policy);
            let service = ptr::read(&this.service);
            let options = ptr::read(&this.options);

            let Some(claim) = claim else {
                return Err(BlpError::Internal {
                    detail: "SubscriptionStream::into_parts called on already-closed stream"
                        .to_string(),
                });
            };

            Ok((
                rx,
                tx,
                claim,
                status,
                flush_threshold,
                overflow_policy,
                service,
                options,
            ))
        }
    }
}

impl Drop for SubscriptionStream {
    fn drop(&mut self) {
        // Session is automatically released when claim is dropped
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicBool;
    use std::sync::atomic::AtomicU64;

    #[test]
    fn raw_request_uses_request_operation_for_validation_and_dispatch() {
        let params = RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::RawRequest.to_string(),
            request_operation: Some(Operation::ReferenceData.to_string()),
            ..Default::default()
        };

        assert!(params.is_raw_request());
        assert_eq!(params.effective_operation(), "ReferenceDataRequest");
        assert!(params.validate().is_ok());
    }

    #[test]
    fn raw_request_requires_request_operation() {
        let params = RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::RawRequest.to_string(),
            ..Default::default()
        };

        let err = params.validate().unwrap_err().to_string();
        assert!(err.contains("request_operation is required for RawRequest"));
    }

    #[test]
    fn merge_raw_kwargs_into_elements_preserves_existing_elements_and_sorts_kwargs() {
        let mut params = RequestParams {
            elements: Some(vec![("alpha".to_string(), "1".to_string())]),
            ..Default::default()
        };

        merge_raw_kwargs_into_elements(
            &mut params,
            HashMap::from([
                ("zeta".to_string(), "9".to_string()),
                ("beta".to_string(), "2".to_string()),
            ]),
        );

        assert_eq!(
            params.elements,
            Some(vec![
                ("alpha".to_string(), "1".to_string()),
                ("beta".to_string(), "2".to_string()),
                ("zeta".to_string(), "9".to_string()),
            ])
        );
    }

    #[test]
    fn subscription_status_records_failure_and_removes_active_topic() {
        let metric = Arc::new(SubscriptionMetrics {
            messages_received: Arc::new(AtomicU64::new(0)),
            dropped_batches: Arc::new(AtomicU64::new(0)),
            batches_sent: Arc::new(AtomicU64::new(0)),
            slow_consumer: Arc::new(AtomicBool::new(false)),
        });
        let mut status = SubscriptionStatusState::from_active(
            vec!["SPY US Equity".to_string(), "/isin/BMG8192H1557".to_string()],
            vec![10, 11],
            HashMap::from([(10, metric.clone()), (11, metric)]),
        );

        let topic = status.record_failure(
            11,
            "Security is not valid for subscription [EX336]".to_string(),
            SubscriptionFailureKind::Failure,
        );

        assert_eq!(topic.as_deref(), Some("/isin/BMG8192H1557"));
        assert_eq!(status.topics(), &["SPY US Equity".to_string()]);
        assert_eq!(status.keys(), &[10]);
        assert_eq!(status.failures().len(), 1);
        assert_eq!(status.failures()[0].kind, SubscriptionFailureKind::Failure);
        assert_eq!(status.failures()[0].topic, "/isin/BMG8192H1557");
    }
}

use std::collections::HashMap;
use std::io::Cursor;
use std::str::FromStr;
use std::sync::atomic::Ordering;
use std::sync::Arc;

use arrow::ipc::writer::StreamWriter;
use arrow::record_batch::RecordBatch;
use napi::bindgen_prelude::{Buffer, Error, Status};
use napi_derive::napi;
use tokio::sync::Mutex;
use xbbg_async::engine::state::SubscriptionMetrics;
use xbbg_async::engine::{Engine, EngineConfig, ExtractorType, OverflowPolicy, RequestParams};
use xbbg_async::{BlpAsyncError, ValidationMode};
use xbbg_core::BlpError;

type StreamBatchResult = std::result::Result<RecordBatch, BlpError>;
type StreamReceiver = tokio::sync::mpsc::Receiver<StreamBatchResult>;
type SharedStreamReceiver = Arc<Mutex<Option<StreamReceiver>>>;

struct SubscriptionStreamHandle {
    tx: tokio::sync::mpsc::Sender<StreamBatchResult>,
    claim: Option<xbbg_async::engine::SessionClaim>,
    keys: Vec<usize>,
    topics: Vec<String>,
    fields: Vec<String>,
    topic_to_key: HashMap<String, usize>,
    service: String,
    options: Vec<String>,
    flush_threshold: Option<usize>,
    overflow_policy: Option<OverflowPolicy>,
    _stream_capacity: Option<usize>,
    metrics: Vec<Arc<SubscriptionMetrics>>,
}

#[napi(object)]
pub struct StringPair {
    pub key: String,
    pub value: String,
}

#[napi(object)]
pub struct EngineConfigInput {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub request_pool_size: Option<u32>,
    pub subscription_pool_size: Option<u32>,
    pub validation_mode: Option<String>,
    pub subscription_flush_threshold: Option<u32>,
    pub max_event_queue_size: Option<u32>,
    pub command_queue_size: Option<u32>,
    pub subscription_stream_capacity: Option<u32>,
    pub overflow_policy: Option<String>,
    pub warmup_services: Option<Vec<String>>,
}

#[napi(object)]
pub struct RequestInput {
    pub service: String,
    pub operation: String,
    pub extractor: Option<String>,
    pub securities: Option<Vec<String>>,
    pub security: Option<String>,
    pub fields: Option<Vec<String>>,
    pub overrides: Option<Vec<StringPair>>,
    pub elements: Option<Vec<StringPair>>,
    pub kwargs: Option<Vec<StringPair>>,
    pub json_elements: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub start_datetime: Option<String>,
    pub end_datetime: Option<String>,
    pub event_type: Option<String>,
    pub event_types: Option<Vec<String>>,
    pub interval: Option<u32>,
    pub options: Option<Vec<StringPair>>,
    pub field_types: Option<Vec<StringPair>>,
    pub include_security_errors: Option<bool>,
    pub search_spec: Option<String>,
    pub field_ids: Option<Vec<String>>,
    pub format: Option<String>,
}

#[napi(object)]
pub struct FieldInfoOutput {
    pub field_id: String,
    pub arrow_type: String,
    pub description: String,
    pub category: String,
}

#[napi(object)]
pub struct SubscriptionStats {
    pub messages_received: i64,
    pub dropped_batches: i64,
    pub batches_sent: i64,
    pub slow_consumer: bool,
}

fn to_i64_saturating(value: u64) -> i64 {
    if value > i64::MAX as u64 {
        i64::MAX
    } else {
        value as i64
    }
}

impl TryFrom<EngineConfigInput> for EngineConfig {
    type Error = Error;

    fn try_from(input: EngineConfigInput) -> Result<Self, Self::Error> {
        let defaults = EngineConfig::default();

        let validation_mode = match input.validation_mode {
            Some(mode) => ValidationMode::from_str(&mode)
                .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?,
            None => defaults.validation_mode,
        };

        let overflow_policy = match input.overflow_policy {
            Some(policy) => OverflowPolicy::from_str(&policy)
                .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?,
            None => defaults.overflow_policy,
        };

        Ok(EngineConfig {
            server_host: input.host.unwrap_or(defaults.server_host),
            server_port: input.port.unwrap_or(defaults.server_port),
            request_pool_size: input
                .request_pool_size
                .map(|v| v as usize)
                .unwrap_or(defaults.request_pool_size),
            subscription_pool_size: input
                .subscription_pool_size
                .map(|v| v as usize)
                .unwrap_or(defaults.subscription_pool_size),
            validation_mode,
            subscription_flush_threshold: input
                .subscription_flush_threshold
                .map(|v| v as usize)
                .unwrap_or(defaults.subscription_flush_threshold),
            max_event_queue_size: input
                .max_event_queue_size
                .map(|v| v as usize)
                .unwrap_or(defaults.max_event_queue_size),
            command_queue_size: input
                .command_queue_size
                .map(|v| v as usize)
                .unwrap_or(defaults.command_queue_size),
            subscription_stream_capacity: input
                .subscription_stream_capacity
                .map(|v| v as usize)
                .unwrap_or(defaults.subscription_stream_capacity),
            overflow_policy,
            warmup_services: input.warmup_services.unwrap_or(defaults.warmup_services),
        })
    }
}

impl TryFrom<RequestInput> for RequestParams {
    type Error = Error;

    fn try_from(input: RequestInput) -> Result<Self, Self::Error> {
        let mut extractor = ExtractorType::default();
        let mut extractor_set = false;
        if let Some(name) = input.extractor {
            extractor = ExtractorType::parse(&name).ok_or_else(|| {
                Error::new(
                    Status::InvalidArg,
                    format!("invalid extractor type: {name}"),
                )
            })?;
            extractor_set = true;
        }

        Ok(RequestParams {
            service: input.service,
            operation: input.operation,
            extractor,
            extractor_set,
            securities: input.securities,
            security: input.security,
            fields: input.fields,
            overrides: pairs_to_tuples(input.overrides),
            elements: pairs_to_tuples(input.elements),
            kwargs: pairs_to_map(input.kwargs),
            json_elements: input.json_elements,
            start_date: input.start_date,
            end_date: input.end_date,
            start_datetime: input.start_datetime,
            end_datetime: input.end_datetime,
            event_type: input.event_type,
            event_types: input.event_types,
            interval: input.interval,
            options: pairs_to_tuples(input.options),
            field_types: pairs_to_map(input.field_types),
            include_security_errors: input.include_security_errors.unwrap_or(false),
            search_spec: input.search_spec,
            field_ids: input.field_ids,
            format: input.format,
        })
    }
}

fn pairs_to_tuples(input: Option<Vec<StringPair>>) -> Option<Vec<(String, String)>> {
    input.map(|pairs| {
        pairs
            .into_iter()
            .map(|pair| (pair.key, pair.value))
            .collect()
    })
}

fn pairs_to_map(input: Option<Vec<StringPair>>) -> Option<HashMap<String, String>> {
    input.map(|pairs| {
        pairs
            .into_iter()
            .map(|pair| (pair.key, pair.value))
            .collect()
    })
}

fn to_ipc_buffer(batch: RecordBatch) -> napi::Result<Buffer> {
    let schema = batch.schema();
    let mut cursor = Cursor::new(Vec::<u8>::new());

    {
        let mut writer = StreamWriter::try_new(&mut cursor, &schema).map_err(|e| {
            Error::new(
                Status::GenericFailure,
                format!("Arrow IPC writer init failed: {e}"),
            )
        })?;

        writer.write(&batch).map_err(|e| {
            Error::new(
                Status::GenericFailure,
                format!("Arrow IPC write failed: {e}"),
            )
        })?;

        writer.finish().map_err(|e| {
            Error::new(
                Status::GenericFailure,
                format!("Arrow IPC finalize failed: {e}"),
            )
        })?;
    }

    Ok(Buffer::from(cursor.into_inner()))
}

fn blp_error_to_napi(e: BlpError) -> Error {
    match e {
        BlpError::SessionStart { source, label } => {
            let msg = format_error_msg("Session start failed", label.as_deref(), source.as_deref());
            Error::new(Status::GenericFailure, msg)
        }
        BlpError::OpenService {
            service,
            source,
            label,
        } => {
            let msg = format!(
                "Failed to open service '{service}': {}",
                format_error_msg("", label.as_deref(), source.as_deref())
            );
            Error::new(Status::GenericFailure, msg)
        }
        BlpError::RequestFailure {
            service,
            operation,
            cid,
            label,
            request_id,
            source,
        } => {
            let mut msg = format!("Request failed on {service}");
            if let Some(op) = operation {
                msg.push_str(&format!("::{op}"));
            }
            if let Some(c) = cid {
                msg.push_str(&format!(" (cid={c})"));
            }
            if let Some(rid) = request_id {
                msg.push_str(&format!(" [request_id={rid}]"));
            }
            if let Some(l) = label {
                msg.push_str(&format!(" - {l}"));
            }
            if let Some(s) = source {
                msg.push_str(&format!(": {s}"));
            }
            Error::new(Status::GenericFailure, msg)
        }
        BlpError::InvalidArgument { detail } => {
            Error::new(Status::InvalidArg, format!("Invalid argument: {detail}"))
        }
        BlpError::Timeout => Error::new(Status::GenericFailure, "Request timed out"),
        BlpError::TemplateTerminated { cid } => {
            let msg = match cid {
                Some(c) => format!("Request template terminated (cid={c})"),
                None => "Request template terminated".to_string(),
            };
            Error::new(Status::GenericFailure, msg)
        }
        BlpError::SubscriptionFailure { cid, label } => {
            let mut msg = "Subscription failed".to_string();
            if let Some(c) = cid {
                msg.push_str(&format!(" (cid={c})"));
            }
            if let Some(l) = label {
                msg.push_str(&format!(": {l}"));
            }
            Error::new(Status::GenericFailure, msg)
        }
        BlpError::Internal { detail } => {
            Error::new(Status::GenericFailure, format!("Internal error: {detail}"))
        }
        BlpError::SchemaOperationNotFound { service, operation } => Error::new(
            Status::InvalidArg,
            format!("Operation not found: {service}::{operation}"),
        ),
        BlpError::SchemaElementNotFound { parent, name } => Error::new(
            Status::InvalidArg,
            format!("Schema element not found: {parent}.{name}"),
        ),
        BlpError::SchemaTypeMismatch {
            element,
            expected,
            found,
        } => Error::new(
            Status::InvalidArg,
            format!("Schema type mismatch at {element}: expected {expected}, found {found}"),
        ),
        BlpError::SchemaUnsupported { element, detail } => Error::new(
            Status::InvalidArg,
            format!("Unsupported schema construct at {element}: {detail}"),
        ),
        BlpError::Validation { message, errors } => {
            let details: Vec<String> = errors
                .iter()
                .map(|e| {
                    if let Some(ref suggestion) = e.suggestion {
                        format!("{e} (did you mean '{suggestion}'?)")
                    } else {
                        e.to_string()
                    }
                })
                .collect();
            let msg = if details.is_empty() {
                message
            } else {
                format!("{message}: {}", details.join("; "))
            };
            Error::new(Status::InvalidArg, msg)
        }
    }
}

fn blp_async_error_to_napi(e: BlpAsyncError) -> Error {
    match e {
        BlpAsyncError::Blp(blp_err) => blp_error_to_napi(blp_err),
        BlpAsyncError::BlpError(blp_err) => blp_error_to_napi(blp_err),
        BlpAsyncError::ConfigError { detail } => {
            Error::new(Status::InvalidArg, format!("Configuration error: {detail}"))
        }
        BlpAsyncError::ChannelClosed => {
            Error::new(Status::GenericFailure, "Channel closed unexpectedly")
        }
        BlpAsyncError::StreamFull => Error::new(
            Status::GenericFailure,
            "Stream buffer full - consumer too slow",
        ),
        BlpAsyncError::Cancelled => Error::new(Status::GenericFailure, "Request was cancelled"),
        BlpAsyncError::Timeout => Error::new(Status::GenericFailure, "Request timed out"),
        BlpAsyncError::Internal(msg) => Error::new(Status::GenericFailure, msg),
    }
}

fn recipe_error_to_napi(e: xbbg_recipes::RecipeError) -> Error {
    Error::new(Status::GenericFailure, e.to_string())
}

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

#[napi]
pub fn version() -> String {
    xbbg_core::version().to_string()
}

#[napi]
pub fn set_log_level(level: String) -> napi::Result<()> {
    let lvl = xbbg_log::parse_level(&level).ok_or_else(|| {
        Error::new(
            Status::InvalidArg,
            format!("Invalid log level '{level}'. Expected: trace, debug, info, warn, error"),
        )
    })?;
    xbbg_log::set_level(lvl);
    Ok(())
}

#[napi]
pub fn get_log_level() -> String {
    match xbbg_log::current_level() {
        xbbg_log::Level::TRACE => "trace",
        xbbg_log::Level::DEBUG => "debug",
        xbbg_log::Level::INFO => "info",
        xbbg_log::Level::WARN => "warn",
        xbbg_log::Level::ERROR => "error",
    }
    .to_string()
}

#[napi]
pub struct JsEngine {
    engine: Arc<Engine>,
}

#[napi]
impl JsEngine {
    #[napi(constructor)]
    pub fn new(host: Option<String>, port: Option<u16>) -> napi::Result<Self> {
        let config = EngineConfig {
            server_host: host.unwrap_or_else(|| "localhost".to_string()),
            server_port: port.unwrap_or(8194),
            ..Default::default()
        };
        Self::start_engine(config)
    }

    #[napi(factory)]
    pub fn with_config(config: EngineConfigInput) -> napi::Result<Self> {
        Self::start_engine(config.try_into()?)
    }

    #[napi]
    pub async fn request(&self, params: RequestInput) -> napi::Result<Buffer> {
        let rust_params: RequestParams = params.try_into()?;
        let batch = self
            .engine
            .request(rust_params)
            .await
            .map_err(blp_async_error_to_napi)?;
        to_ipc_buffer(batch)
    }


    #[napi]
    pub async fn resolve_field_types(
        &self,
        fields: Vec<String>,
        overrides: Option<Vec<StringPair>>,
        default_type: Option<String>,
    ) -> napi::Result<Vec<StringPair>> {
        let map = self
            .engine
            .resolve_field_types(
                &fields,
                pairs_to_map(overrides).as_ref(),
                default_type.as_deref().unwrap_or("string"),
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        Ok(map
            .into_iter()
            .map(|(key, value)| StringPair { key, value })
            .collect())
    }

    #[napi]
    pub fn get_field_info(&self, field: String) -> Option<FieldInfoOutput> {
        self.engine
            .get_field_info(&field)
            .map(|info| FieldInfoOutput {
                field_id: info.field_id,
                arrow_type: info.arrow_type,
                description: info.description,
                category: info.category,
            })
    }

    #[napi]
    pub fn clear_field_cache(&self) {
        self.engine.clear_field_cache();
    }

    #[napi]
    pub fn save_field_cache(&self) -> napi::Result<()> {
        self.engine
            .save_field_cache()
            .map_err(|e| Error::new(Status::GenericFailure, e))
    }

    #[napi]
    pub async fn validate_fields(&self, fields: Vec<String>) -> napi::Result<Vec<String>> {
        self.engine
            .validate_fields(&fields)
            .await
            .map_err(blp_async_error_to_napi)
    }

    #[napi]
    pub fn is_field_validation_enabled(&self) -> bool {
        self.engine.is_field_validation_enabled()
    }

    #[napi]
    pub async fn get_schema(&self, service: String) -> napi::Result<String> {
        let schema = self
            .engine
            .get_schema(&service)
            .await
            .map_err(blp_async_error_to_napi)?;
        serde_json::to_string(&*schema)
            .map_err(|e| Error::new(Status::GenericFailure, format!("serialize schema: {e}")))
    }

    #[napi]
    pub async fn get_operation(&self, service: String, operation: String) -> napi::Result<String> {
        let op = self
            .engine
            .get_operation(&service, &operation)
            .await
            .map_err(blp_async_error_to_napi)?;
        serde_json::to_string(&op)
            .map_err(|e| Error::new(Status::GenericFailure, format!("serialize operation: {e}")))
    }

    #[napi]
    pub async fn list_operations(&self, service: String) -> napi::Result<Vec<String>> {
        self.engine
            .list_operations(&service)
            .await
            .map_err(blp_async_error_to_napi)
    }

    #[napi]
    pub fn get_cached_schema(&self, service: String) -> Option<String> {
        self.engine
            .get_cached_schema(&service)
            .and_then(|s| serde_json::to_string(&*s).ok())
    }

    #[napi]
    pub fn invalidate_schema(&self, service: String) {
        self.engine.invalidate_schema(&service);
    }

    #[napi]
    pub fn clear_schema_cache(&self) {
        self.engine.clear_schema_cache();
    }

    #[napi]
    pub fn list_cached_schemas(&self) -> Vec<String> {
        self.engine.list_cached_schemas()
    }

    #[napi]
    pub async fn get_enum_values(
        &self,
        service: String,
        operation: String,
        element: String,
    ) -> napi::Result<Option<Vec<String>>> {
        self.engine
            .get_enum_values(&service, &operation, &element)
            .await
            .map_err(blp_async_error_to_napi)
    }

    #[napi]
    pub async fn list_valid_elements(
        &self,
        service: String,
        operation: String,
    ) -> napi::Result<Option<Vec<String>>> {
        self.engine
            .list_valid_elements(&service, &operation)
            .await
            .map_err(blp_async_error_to_napi)
    }

    #[napi]
    pub async fn subscribe(
        &self,
        tickers: Vec<String>,
        fields: Vec<String>,
    ) -> napi::Result<JsSubscription> {
        let stream = self
            .engine
            .subscribe_with_options(
                "//blp/mktdata".to_string(),
                tickers.clone(),
                fields.clone(),
                vec![],
                None,
                None,
                None,
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        Ok(JsSubscription::from_stream(stream, tickers, fields, None))
    }

    #[napi]
    #[allow(clippy::too_many_arguments)]
    pub async fn subscribe_with_options(
        &self,
        service: String,
        tickers: Vec<String>,
        fields: Vec<String>,
        options: Option<Vec<String>>,
        flush_threshold: Option<u32>,
        overflow_policy: Option<String>,
        stream_capacity: Option<u32>,
    ) -> napi::Result<JsSubscription> {
        let overflow = match overflow_policy {
            Some(policy) => Some(
                OverflowPolicy::from_str(&policy)
                    .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?,
            ),
            None => None,
        };

        let stream = self
            .engine
            .subscribe_with_options(
                service,
                tickers.clone(),
                fields.clone(),
                options.unwrap_or_default(),
                stream_capacity.map(|v| v as usize),
                flush_threshold.map(|v| v as usize),
                overflow,
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        Ok(JsSubscription::from_stream(
            stream,
            tickers,
            fields,
            stream_capacity.map(|v| v as usize),
        ))
    }

    #[napi]
    pub fn signal_shutdown(&self) {
        self.engine.signal_shutdown();
    }

    #[napi]
    pub fn is_available(&self) -> bool {
        true
    }


    #[napi]
    pub async fn recipe_bqr(
        &self,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
        event_types: Option<Vec<String>>,
        include_broker_codes: Option<bool>,
    ) -> napi::Result<Buffer> {
        let engine = self.engine.clone();
        let batch = xbbg_recipes::fixed_income::recipe_bqr(
            &engine,
            ticker,
            start_datetime,
            end_datetime,
            event_types,
            include_broker_codes.unwrap_or(true),
        )
        .await
        .map_err(recipe_error_to_napi)?;
        to_ipc_buffer(batch)
    }

    fn start_engine(config: EngineConfig) -> napi::Result<Self> {
        let engine = Engine::start(config).map_err(blp_async_error_to_napi)?;
        Ok(Self {
            engine: Arc::new(engine),
        })
    }
}

#[napi]
pub struct JsSubscription {
    rx: SharedStreamReceiver,
    stream: Arc<Mutex<Option<SubscriptionStreamHandle>>>,
}

#[napi]
impl JsSubscription {
    fn from_stream(
        stream: xbbg_async::engine::SubscriptionStream,
        tickers: Vec<String>,
        fields: Vec<String>,
        stream_capacity: Option<usize>,
    ) -> Self {
        let (rx, tx, claim, keys, topic_to_key, metrics, ft, op_policy, service, options) =
            stream.into_parts();
        let handle = SubscriptionStreamHandle {
            tx,
            claim: Some(claim),
            keys,
            topics: tickers,
            fields,
            topic_to_key,
            service,
            options,
            flush_threshold: ft,
            overflow_policy: op_policy,
            _stream_capacity: stream_capacity,
            metrics,
        };
        Self {
            rx: Arc::new(Mutex::new(Some(rx))),
            stream: Arc::new(Mutex::new(Some(handle))),
        }
    }

    #[napi]
    pub async fn next(&self) -> napi::Result<Option<Buffer>> {
        let item = {
            let mut guard = self.rx.lock().await;
            let rx = guard
                .as_mut()
                .ok_or_else(|| Error::new(Status::GenericFailure, "subscription closed"))?;
            rx.recv().await
        };

        match item {
            Some(Ok(batch)) => Ok(Some(to_ipc_buffer(batch)?)),
            Some(Err(e)) => Err(blp_error_to_napi(e)),
            None => Ok(None),
        }
    }

    #[napi]
    pub async fn add(&self, tickers: Vec<String>) -> napi::Result<()> {
        let mut guard = self.stream.lock().await;
        let handle = guard
            .as_mut()
            .ok_or_else(|| Error::new(Status::GenericFailure, "subscription closed"))?;

        let new_topics: Vec<String> = tickers
            .into_iter()
            .filter(|ticker| !handle.topic_to_key.contains_key(ticker))
            .collect();
        if new_topics.is_empty() {
            return Ok(());
        }

        let claim = handle
            .claim
            .as_ref()
            .ok_or_else(|| Error::new(Status::GenericFailure, "subscription already closed"))?;

        let (new_keys, new_metrics) = claim
            .add_topics(
                handle.service.clone(),
                new_topics.clone(),
                handle.fields.clone(),
                handle.options.clone(),
                handle.flush_threshold,
                handle.overflow_policy,
                handle.tx.clone(),
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        for (topic, key) in new_topics.iter().zip(new_keys.iter()) {
            handle.topic_to_key.insert(topic.clone(), *key);
            handle.topics.push(topic.clone());
            handle.keys.push(*key);
        }
        handle.metrics.extend(new_metrics);
        Ok(())
    }

    #[napi]
    pub async fn remove(&self, tickers: Vec<String>) -> napi::Result<()> {
        let mut guard = self.stream.lock().await;
        let handle = guard
            .as_mut()
            .ok_or_else(|| Error::new(Status::GenericFailure, "subscription closed"))?;

        let mut keys_to_remove = Vec::new();
        for ticker in &tickers {
            if let Some(key) = handle.topic_to_key.remove(ticker) {
                keys_to_remove.push(key);
                handle.topics.retain(|topic| topic != ticker);
                handle.keys.retain(|k| *k != key);
            }
        }
        if keys_to_remove.is_empty() {
            return Ok(());
        }

        let claim = handle
            .claim
            .as_ref()
            .ok_or_else(|| Error::new(Status::GenericFailure, "subscription already closed"))?;
        claim
            .unsubscribe(keys_to_remove)
            .await
            .map_err(blp_async_error_to_napi)
    }

    #[napi(getter)]
    pub fn tickers(&self) -> Vec<String> {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => handle.topics.clone(),
            None => Vec::new(),
        }
    }

    #[napi(getter)]
    pub fn fields(&self) -> Vec<String> {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => handle.fields.clone(),
            None => Vec::new(),
        }
    }

    #[napi(getter)]
    pub fn is_active(&self) -> bool {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => !handle.keys.is_empty() && handle.claim.is_some(),
            None => false,
        }
    }

    #[napi(getter)]
    pub fn stats(&self) -> SubscriptionStats {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => SubscriptionStats {
                messages_received: to_i64_saturating(
                    handle
                        .metrics
                        .iter()
                        .map(|metric| metric.messages_received.load(Ordering::Relaxed))
                        .sum(),
                ),
                dropped_batches: to_i64_saturating(
                    handle
                        .metrics
                        .iter()
                        .map(|metric| metric.dropped_batches.load(Ordering::Relaxed))
                        .sum(),
                ),
                batches_sent: to_i64_saturating(
                    handle
                        .metrics
                        .iter()
                        .map(|metric| metric.batches_sent.load(Ordering::Relaxed))
                        .sum(),
                ),
                slow_consumer: handle
                    .metrics
                    .iter()
                    .any(|metric| metric.slow_consumer.load(Ordering::Relaxed)),
            },
            None => SubscriptionStats {
                messages_received: 0,
                dropped_batches: 0,
                batches_sent: 0,
                slow_consumer: false,
            },
        }
    }

    #[napi]
    pub async fn unsubscribe(&self, drain: Option<bool>) -> napi::Result<Option<Vec<Buffer>>> {
        let drain = drain.unwrap_or(false);
        let handle = {
            let mut guard = self.stream.lock().await;
            guard.take()
        };
        let rx = {
            let mut guard = self.rx.lock().await;
            guard.take()
        };

        let mut remaining = Vec::new();
        if drain {
            if let Some(mut rx) = rx {
                while let Ok(item) = rx.try_recv() {
                    if let Ok(batch) = item {
                        remaining.push(to_ipc_buffer(batch)?);
                    }
                }
            }
        }

        if let Some(mut handle) = handle {
            if let Some(claim) = handle.claim.take() {
                if !handle.keys.is_empty() {
                    let _ = claim.unsubscribe(handle.keys.clone()).await;
                }
            }
        }

        if remaining.is_empty() {
            Ok(None)
        } else {
            Ok(Some(remaining))
        }
    }
}

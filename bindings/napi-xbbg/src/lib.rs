mod ext;

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
use xbbg_async::engine::{
    Engine, EngineConfig, ExtractorType, OverflowPolicy, RequestParams, SharedSubscriptionStatus,
};
use xbbg_async::{BlpAsyncError, ValidationMode};
use xbbg_core::{AuthConfig, BlpError};

type StreamBatchResult = std::result::Result<RecordBatch, BlpError>;
type StreamReceiver = tokio::sync::mpsc::Receiver<StreamBatchResult>;
type SharedStreamReceiver = Arc<Mutex<Option<StreamReceiver>>>;

struct SubscriptionStreamHandle {
    tx: tokio::sync::mpsc::Sender<StreamBatchResult>,
    claim: Option<xbbg_async::engine::SessionClaim>,
    fields: Vec<String>,
    all_fields: bool,
    service: String,
    options: Vec<String>,
    flush_threshold: Option<usize>,
    overflow_policy: Option<OverflowPolicy>,
    status: SharedSubscriptionStatus,
}

#[napi(object)]
pub struct StringPair {
    pub key: String,
    pub value: String,
}

#[napi(object)]
pub struct ServerAddressInput {
    pub host: String,
    pub port: u16,
}

#[napi(object)]
pub struct AuthConfigInput {
    pub method: String,
    pub app_name: Option<String>,
    pub dir_property: Option<String>,
    pub user_id: Option<String>,
    pub ip_address: Option<String>,
    pub token: Option<String>,
}

#[napi(object)]
pub struct TlsConfigInput {
    pub client_credentials: Option<String>,
    pub client_credentials_password: Option<String>,
    pub trust_material: Option<String>,
    pub handshake_timeout_ms: Option<i32>,
    pub crl_fetch_timeout_ms: Option<i32>,
}

#[napi(object)]
pub struct RetryPolicyInput {
    pub max_retries: Option<u32>,
    pub initial_delay_ms: Option<i64>,
    pub backoff_factor: Option<f64>,
    pub max_delay_ms: Option<i64>,
}

#[napi(object)]
pub struct Socks5ConfigInput {
    pub host: String,
    pub port: u16,
}

#[napi(object)]
pub struct EngineConfigInput {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub servers: Option<Vec<ServerAddressInput>>,
    pub zfp_remote: Option<String>,
    pub request_pool_size: Option<u32>,
    pub subscription_pool_size: Option<u32>,
    pub validation_mode: Option<String>,
    pub subscription_flush_threshold: Option<u32>,
    pub max_event_queue_size: Option<u32>,
    pub command_queue_size: Option<u32>,
    pub subscription_stream_capacity: Option<u32>,
    pub overflow_policy: Option<String>,
    pub warmup_services: Option<Vec<String>>,
    pub field_cache_path: Option<String>,
    pub auth: Option<AuthConfigInput>,
    pub tls: Option<TlsConfigInput>,
    pub num_start_attempts: Option<u32>,
    pub auto_restart_on_disconnection: Option<bool>,
    pub max_recovery_attempts: Option<u32>,
    pub recovery_timeout_ms: Option<i64>,
    pub retry_policy: Option<RetryPolicyInput>,
    pub health_check_interval_ms: Option<i64>,
    pub sdk_log_level: Option<String>,
    pub socks5: Option<Socks5ConfigInput>,
}

#[napi(object)]
pub struct RequestInput {
    pub service: String,
    pub operation: String,
    pub request_operation: Option<String>,
    pub request_id: Option<String>,
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
    pub request_tz: Option<String>,
    pub output_tz: Option<String>,
    pub event_type: Option<String>,
    pub event_types: Option<Vec<String>>,
    pub interval: Option<u32>,
    pub options: Option<Vec<StringPair>>,
    pub field_types: Option<Vec<StringPair>>,
    pub include_security_errors: Option<bool>,
    pub validate_fields: Option<bool>,
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

fn require_auth_value(value: Option<&String>, field: &str, method: &str) -> Result<String, Error> {
    value
        .cloned()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            Error::new(
                Status::InvalidArg,
                format!("auth.{field} is required for auth.method='{method}'"),
            )
        })
}

fn require_non_negative_duration(value: i64, field: &str) -> Result<u64, Error> {
    u64::try_from(value).map_err(|_| {
        Error::new(
            Status::InvalidArg,
            format!("{field} must be a non-negative integer number of milliseconds"),
        )
    })
}

fn require_non_negative_timeout(value: i32, field: &str) -> Result<i32, Error> {
    if value < 0 {
        return Err(Error::new(
            Status::InvalidArg,
            format!("{field} must be a non-negative integer number of milliseconds"),
        ));
    }
    Ok(value)
}

fn build_auth_config(input: Option<&AuthConfigInput>) -> Result<Option<AuthConfig>, Error> {
    let Some(input) = input else {
        return Ok(None);
    };

    let method = input.method.trim().to_ascii_lowercase();
    let auth = match method.as_str() {
        "" | "none" => None,
        "user" => Some(AuthConfig::User),
        "app" => Some(AuthConfig::App {
            app_name: require_auth_value(input.app_name.as_ref(), "appName", &method)?,
        }),
        "userapp" => Some(AuthConfig::UserApp {
            app_name: require_auth_value(input.app_name.as_ref(), "appName", &method)?,
        }),
        "dir" | "directory" => Some(AuthConfig::Directory {
            property_name: require_auth_value(input.dir_property.as_ref(), "dirProperty", &method)?,
        }),
        "manual" => Some(AuthConfig::Manual {
            app_name: require_auth_value(input.app_name.as_ref(), "appName", &method)?,
            user_id: require_auth_value(input.user_id.as_ref(), "userId", &method)?,
            ip_address: require_auth_value(input.ip_address.as_ref(), "ipAddress", &method)?,
        }),
        "token" => Some(AuthConfig::Token {
            token: require_auth_value(input.token.as_ref(), "token", &method)?,
        }),
        other => {
            return Err(Error::new(
                Status::InvalidArg,
                format!(
                    "invalid auth.method: {other}. Must be one of ['none', 'user', 'app', 'userapp', 'dir', 'directory', 'manual', 'token']",
                ),
            ));
        }
    };

    Ok(auth)
}

impl TryFrom<EngineConfigInput> for EngineConfig {
    type Error = Error;

    fn try_from(input: EngineConfigInput) -> Result<Self, Self::Error> {
        let mut config = EngineConfig::default();
        let auth = build_auth_config(input.auth.as_ref())?;

        let validation_mode = match input.validation_mode {
            Some(mode) => ValidationMode::from_str(&mode)
                .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?,
            None => config.validation_mode,
        };

        let overflow_policy = match input.overflow_policy {
            Some(policy) => OverflowPolicy::from_str(&policy)
                .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?,
            None => config.overflow_policy,
        };

        if let Some(host) = input.host {
            config.server_host = host;
        }
        if let Some(port) = input.port {
            config.server_port = port;
        }
        if let Some(servers) = input.servers {
            config.servers = servers
                .into_iter()
                .map(|server| (server.host, server.port))
                .collect();
        }
        if let Some(zfp_remote) = input.zfp_remote {
            config.zfp_remote = Some(
                zfp_remote
                    .parse()
                    .map_err(|e: String| Error::new(Status::InvalidArg, e))?,
            );
        }
        if let Some(size) = input.request_pool_size {
            config.request_pool_size = size as usize;
        }
        if let Some(size) = input.subscription_pool_size {
            config.subscription_pool_size = size as usize;
        }
        if let Some(size) = input.subscription_flush_threshold {
            config.subscription_flush_threshold = size as usize;
        }
        if let Some(size) = input.max_event_queue_size {
            config.max_event_queue_size = size as usize;
        }
        if let Some(size) = input.command_queue_size {
            config.command_queue_size = size as usize;
        }
        if let Some(size) = input.subscription_stream_capacity {
            config.subscription_stream_capacity = size as usize;
        }
        if let Some(services) = input.warmup_services {
            config.warmup_services = services;
        }
        if let Some(field_cache_path) = input.field_cache_path {
            config.field_cache_path = Some(field_cache_path.into());
        }
        if let Some(tls) = input.tls {
            config.tls_client_credentials = tls.client_credentials;
            config.tls_client_credentials_password = tls.client_credentials_password;
            config.tls_trust_material = tls.trust_material;
            config.tls_handshake_timeout_ms = tls
                .handshake_timeout_ms
                .map(|value| require_non_negative_timeout(value, "tls.handshakeTimeoutMs"))
                .transpose()?;
            config.tls_crl_fetch_timeout_ms = tls
                .crl_fetch_timeout_ms
                .map(|value| require_non_negative_timeout(value, "tls.crlFetchTimeoutMs"))
                .transpose()?;
        }
        if let Some(num_start_attempts) = input.num_start_attempts {
            config.num_start_attempts = num_start_attempts as usize;
        }
        if let Some(auto_restart) = input.auto_restart_on_disconnection {
            config.auto_restart_on_disconnection = auto_restart;
        }
        if let Some(max_recovery_attempts) = input.max_recovery_attempts {
            config.max_recovery_attempts = max_recovery_attempts as usize;
        }
        if let Some(recovery_timeout_ms) = input.recovery_timeout_ms {
            config.recovery_timeout_ms =
                require_non_negative_duration(recovery_timeout_ms, "recoveryTimeoutMs")?;
        }
        if let Some(retry_policy) = input.retry_policy {
            if let Some(max_retries) = retry_policy.max_retries {
                config.retry_policy.max_retries = max_retries;
            }
            if let Some(initial_delay_ms) = retry_policy.initial_delay_ms {
                config.retry_policy.initial_delay_ms =
                    require_non_negative_duration(initial_delay_ms, "retryPolicy.initialDelayMs")?;
            }
            if let Some(backoff_factor) = retry_policy.backoff_factor {
                config.retry_policy.backoff_factor = backoff_factor;
            }
            if let Some(max_delay_ms) = retry_policy.max_delay_ms {
                config.retry_policy.max_delay_ms =
                    require_non_negative_duration(max_delay_ms, "retryPolicy.maxDelayMs")?;
            }
        }
        if let Some(health_check_interval_ms) = input.health_check_interval_ms {
            config.health_check_interval_ms =
                require_non_negative_duration(health_check_interval_ms, "healthCheckIntervalMs")?;
        }
        if let Some(sdk_log_level) = input.sdk_log_level {
            config.sdk_log_level = sdk_log_level
                .parse()
                .map_err(|e: String| Error::new(Status::InvalidArg, e))?;
        }
        if let Some(socks5) = input.socks5 {
            config.socks5_host = Some(socks5.host);
            config.socks5_port = Some(socks5.port);
        }

        config.validation_mode = validation_mode;
        config.overflow_policy = overflow_policy;
        config.auth = auth;

        Ok(config)
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

        let mut elements = pairs_to_tuples(input.elements);
        if let Some(raw_json) = input.json_elements {
            let value: serde_json::Value = serde_json::from_str(&raw_json).map_err(|e| {
                Error::new(
                    Status::InvalidArg,
                    format!("invalid jsonElements payload: {e}"),
                )
            })?;
            let flattened = elements.get_or_insert_with(Vec::new);
            flatten_json_elements(None, &value, flattened)?;
        }

        Ok(RequestParams {
            service: input.service,
            operation: input.operation,
            request_operation: input.request_operation,
            request_id: input.request_id,
            extractor,
            extractor_set,
            securities: input.securities,
            security: input.security,
            fields: input.fields,
            overrides: pairs_to_tuples(input.overrides),
            elements,
            kwargs: pairs_to_map(input.kwargs),
            start_date: input.start_date,
            end_date: input.end_date,
            start_datetime: input.start_datetime,
            end_datetime: input.end_datetime,
            request_tz: input.request_tz,
            output_tz: input.output_tz,
            event_type: input.event_type,
            event_types: input.event_types,
            interval: input.interval,
            options: pairs_to_tuples(input.options),
            field_types: pairs_to_map(input.field_types),
            include_security_errors: input.include_security_errors.unwrap_or(false),
            validate_fields: input.validate_fields,
            search_spec: input.search_spec,
            field_ids: input.field_ids,
            format: input.format,
        })
    }
}

fn flatten_json_elements(
    path: Option<&str>,
    value: &serde_json::Value,
    out: &mut Vec<(String, String)>,
) -> Result<(), Error> {
    match value {
        serde_json::Value::Object(map) => {
            if map.is_empty() {
                return Ok(());
            }
            for (key, child) in map {
                let next_path = match path {
                    Some(prefix) if !prefix.is_empty() => format!("{prefix}.{key}"),
                    _ => key.clone(),
                };
                flatten_json_elements(Some(&next_path), child, out)?;
            }
            Ok(())
        }
        serde_json::Value::Array(items) => {
            let path = path.ok_or_else(|| {
                Error::new(
                    Status::InvalidArg,
                    "jsonElements must be a JSON object at the top level",
                )
            })?;

            if path.contains('.') {
                out.push((
                    path.to_string(),
                    serde_json::to_string(items).map_err(|e| {
                        Error::new(
                            Status::GenericFailure,
                            format!("failed to serialize nested jsonElements array: {e}"),
                        )
                    })?,
                ));
            } else {
                for item in items {
                    out.push((path.to_string(), json_value_to_string(item)?));
                }
            }

            Ok(())
        }
        _ => {
            let path = path.ok_or_else(|| {
                Error::new(
                    Status::InvalidArg,
                    "jsonElements must be a JSON object at the top level",
                )
            })?;
            out.push((path.to_string(), json_value_to_string(value)?));
            Ok(())
        }
    }
}

fn json_value_to_string(value: &serde_json::Value) -> Result<String, Error> {
    match value {
        serde_json::Value::Null => Ok("null".to_string()),
        serde_json::Value::Bool(flag) => Ok(flag.to_string()),
        serde_json::Value::Number(number) => Ok(number.to_string()),
        serde_json::Value::String(text) => Ok(text.clone()),
        serde_json::Value::Array(_) | serde_json::Value::Object(_) => serde_json::to_string(value)
            .map_err(|e| {
                Error::new(
                    Status::GenericFailure,
                    format!("failed to serialize jsonElements value: {e}"),
                )
            }),
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
        BlpAsyncError::SessionLost {
            worker_id,
            in_flight_count,
        } => Error::new(
            Status::GenericFailure,
            format!(
                "Session lost on worker {worker_id}; {in_flight_count} in-flight requests failed"
            ),
        ),
        BlpAsyncError::AllWorkersDown { pool_size } => Error::new(
            Status::GenericFailure,
            format!("All {pool_size} request workers are down"),
        ),
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
                false,
                vec![],
                None,
                None,
                None,
                None,
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        JsSubscription::from_stream(stream, tickers, fields, None)
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
                false,
                options.unwrap_or_default(),
                stream_capacity.map(|v| v as usize),
                flush_threshold.map(|v| v as usize),
                overflow,
                None,
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        JsSubscription::from_stream(stream, tickers, fields, stream_capacity.map(|v| v as usize))
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
        _tickers: Vec<String>,
        fields: Vec<String>,
        _stream_capacity: Option<usize>,
    ) -> napi::Result<Self> {
        let (rx, tx, claim, status, ft, op_policy, service, options, all_fields) =
            stream.into_parts().map_err(blp_error_to_napi)?;
        let handle = SubscriptionStreamHandle {
            tx,
            claim: Some(claim),
            fields,
            all_fields,
            service,
            options,
            flush_threshold: ft,
            overflow_policy: op_policy,
            status,
        };
        Ok(Self {
            rx: Arc::new(Mutex::new(Some(rx))),
            stream: Arc::new(Mutex::new(Some(handle))),
        })
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

        let new_topics: Vec<String> = {
            let status = handle.status.lock();
            tickers
                .into_iter()
                .filter(|ticker| !status.topic_to_key().contains_key(ticker))
                .collect()
        };
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
                handle.all_fields,
                handle.options.clone(),
                handle.flush_threshold,
                handle.overflow_policy,
                handle.tx.clone(),
                handle.status.clone(),
            )
            .await
            .map_err(blp_async_error_to_napi)?;

        handle
            .status
            .lock()
            .add_active(&new_topics, &new_keys, new_metrics);
        Ok(())
    }

    #[napi]
    pub async fn remove(&self, tickers: Vec<String>) -> napi::Result<()> {
        let mut guard = self.stream.lock().await;
        let handle = guard
            .as_mut()
            .ok_or_else(|| Error::new(Status::GenericFailure, "subscription closed"))?;

        let (keys_to_remove, topics_to_remove) = {
            let status = handle.status.lock();
            let mut keys_to_remove = Vec::new();
            let mut topics_to_remove = Vec::new();
            for ticker in &tickers {
                if let Some(&key) = status.topic_to_key().get(ticker) {
                    keys_to_remove.push(key);
                    topics_to_remove.push(ticker.clone());
                }
            }
            (keys_to_remove, topics_to_remove)
        };
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
            .map_err(blp_async_error_to_napi)?;

        let mut status = handle.status.lock();
        for ticker in topics_to_remove {
            status.remove_topic(&ticker);
        }

        Ok(())
    }

    #[napi(getter)]
    pub fn tickers(&self) -> Vec<String> {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => handle.status.lock().topics().to_vec(),
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
            Some(handle) => handle.claim.is_some() && handle.status.lock().has_active_topics(),
            None => false,
        }
    }

    #[napi(getter)]
    pub fn stats(&self) -> SubscriptionStats {
        let guard = self.stream.blocking_lock();
        match guard.as_ref() {
            Some(handle) => {
                let status = handle.status.lock();
                let metrics: Vec<_> = status.fields_metrics().values().cloned().collect();
                SubscriptionStats {
                    messages_received: to_i64_saturating(
                        metrics
                            .iter()
                            .map(|metric| metric.messages_received.load(Ordering::Relaxed))
                            .sum(),
                    ),
                    dropped_batches: to_i64_saturating(
                        metrics
                            .iter()
                            .map(|metric| metric.dropped_batches.load(Ordering::Relaxed))
                            .sum(),
                    ),
                    batches_sent: to_i64_saturating(
                        metrics
                            .iter()
                            .map(|metric| metric.batches_sent.load(Ordering::Relaxed))
                            .sum(),
                    ),
                    slow_consumer: metrics
                        .iter()
                        .any(|metric| metric.slow_consumer.load(Ordering::Relaxed)),
                }
            }
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
                let keys = handle.status.lock().keys().to_vec();
                if !keys.is_empty() {
                    let _ = claim.unsubscribe(keys).await;
                }
            }
            handle.status.lock().clear_active();
        }

        if remaining.is_empty() {
            Ok(None)
        } else {
            Ok(Some(remaining))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn engine_config_input_defaults_leave_auth_unset() {
        let config = EngineConfig::try_from(EngineConfigInput {
            host: None,
            port: None,
            servers: None,
            zfp_remote: None,
            request_pool_size: None,
            subscription_pool_size: None,
            validation_mode: None,
            subscription_flush_threshold: None,
            max_event_queue_size: None,
            command_queue_size: None,
            subscription_stream_capacity: None,
            overflow_policy: None,
            warmup_services: None,
            field_cache_path: None,
            auth: None,
            tls: None,
            num_start_attempts: None,
            auto_restart_on_disconnection: None,
            max_recovery_attempts: None,
            recovery_timeout_ms: None,
            retry_policy: None,
            health_check_interval_ms: None,
            sdk_log_level: None,
            socks5: None,
        })
        .expect("default config should convert");

        assert_eq!(config.auth, None);
        assert_eq!(config.server_host, "localhost");
        assert_eq!(config.server_port, 8194);
    }

    #[test]
    fn engine_config_input_maps_bpipe_and_auth_options() {
        let config = EngineConfig::try_from(EngineConfigInput {
            host: Some("primary.example.com".to_string()),
            port: Some(8194),
            servers: Some(vec![
                ServerAddressInput {
                    host: "primary.example.com".to_string(),
                    port: 8194,
                },
                ServerAddressInput {
                    host: "secondary.example.com".to_string(),
                    port: 8196,
                },
            ]),
            zfp_remote: Some("8194".to_string()),
            request_pool_size: Some(4),
            subscription_pool_size: Some(2),
            validation_mode: Some("strict".to_string()),
            subscription_flush_threshold: Some(8),
            max_event_queue_size: Some(16_000),
            command_queue_size: Some(512),
            subscription_stream_capacity: Some(1024),
            overflow_policy: Some("block".to_string()),
            warmup_services: Some(vec!["//blp/refdata".to_string()]),
            field_cache_path: Some("/tmp/xbbg-field-cache.json".to_string()),
            auth: Some(AuthConfigInput {
                method: "manual".to_string(),
                app_name: Some("app-name".to_string()),
                dir_property: None,
                user_id: Some("123456".to_string()),
                ip_address: Some("10.0.0.1".to_string()),
                token: None,
            }),
            tls: Some(TlsConfigInput {
                client_credentials: Some("/tmp/client.p12".to_string()),
                client_credentials_password: Some("secret".to_string()),
                trust_material: Some("/tmp/trust.p7".to_string()),
                handshake_timeout_ms: Some(2000),
                crl_fetch_timeout_ms: Some(3000),
            }),
            num_start_attempts: Some(5),
            auto_restart_on_disconnection: Some(false),
            max_recovery_attempts: Some(7),
            recovery_timeout_ms: Some(45_000),
            retry_policy: Some(RetryPolicyInput {
                max_retries: Some(3),
                initial_delay_ms: Some(250),
                backoff_factor: Some(1.5),
                max_delay_ms: Some(5_000),
            }),
            health_check_interval_ms: Some(12_000),
            sdk_log_level: Some("warn".to_string()),
            socks5: Some(Socks5ConfigInput {
                host: "proxy.example.com".to_string(),
                port: 1080,
            }),
        })
        .expect("config with auth should convert");

        assert_eq!(
            config.servers,
            vec![
                ("primary.example.com".to_string(), 8194),
                ("secondary.example.com".to_string(), 8196),
            ]
        );
        assert_eq!(
            config.zfp_remote,
            Some(xbbg_core::zfp::ZfpRemote::Remote8194)
        );
        assert_eq!(
            config.auth,
            Some(AuthConfig::Manual {
                app_name: "app-name".to_string(),
                user_id: "123456".to_string(),
                ip_address: "10.0.0.1".to_string(),
            })
        );
        assert_eq!(
            config.field_cache_path,
            Some(std::path::PathBuf::from("/tmp/xbbg-field-cache.json"))
        );
        assert_eq!(
            config.tls_client_credentials.as_deref(),
            Some("/tmp/client.p12")
        );
        assert_eq!(
            config.tls_client_credentials_password.as_deref(),
            Some("secret")
        );
        assert_eq!(config.tls_trust_material.as_deref(), Some("/tmp/trust.p7"));
        assert_eq!(config.tls_handshake_timeout_ms, Some(2000));
        assert_eq!(config.tls_crl_fetch_timeout_ms, Some(3000));
        assert_eq!(config.num_start_attempts, 5);
        assert!(!config.auto_restart_on_disconnection);
        assert_eq!(config.max_recovery_attempts, 7);
        assert_eq!(config.recovery_timeout_ms, 45_000);
        assert_eq!(config.retry_policy.max_retries, 3);
        assert_eq!(config.retry_policy.initial_delay_ms, 250);
        assert_eq!(config.retry_policy.backoff_factor, 1.5);
        assert_eq!(config.retry_policy.max_delay_ms, 5_000);
        assert_eq!(config.health_check_interval_ms, 12_000);
        assert_eq!(config.socks5_host.as_deref(), Some("proxy.example.com"));
        assert_eq!(config.socks5_port, Some(1080));
    }

    #[test]
    fn engine_config_input_requires_auth_fields_for_selected_method() {
        let err = match EngineConfig::try_from(EngineConfigInput {
            host: None,
            port: None,
            servers: None,
            zfp_remote: None,
            request_pool_size: None,
            subscription_pool_size: None,
            validation_mode: None,
            subscription_flush_threshold: None,
            max_event_queue_size: None,
            command_queue_size: None,
            subscription_stream_capacity: None,
            overflow_policy: None,
            warmup_services: None,
            field_cache_path: None,
            auth: Some(AuthConfigInput {
                method: "app".to_string(),
                app_name: None,
                dir_property: None,
                user_id: None,
                ip_address: None,
                token: None,
            }),
            tls: None,
            num_start_attempts: None,
            auto_restart_on_disconnection: None,
            max_recovery_attempts: None,
            recovery_timeout_ms: None,
            retry_policy: None,
            health_check_interval_ms: None,
            sdk_log_level: None,
            socks5: None,
        }) {
            Ok(_) => panic!("missing appName should fail"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("auth.appName is required"));
    }
}

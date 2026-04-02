use std::collections::{BTreeMap, HashMap};
use std::env;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::Arc;

use arrow::array::{
    Array, ArrayRef, BooleanArray, Date32Array, Float32Array, Float64Array, Int32Array, Int64Array,
    LargeStringArray, StringArray, TimestampMicrosecondArray, UInt32Array, UInt64Array,
};
use arrow::datatypes::DataType;
use arrow::record_batch::RecordBatch;
use arrow::util::display::array_value_to_string;
use chrono::{DateTime, NaiveDate, NaiveDateTime};
use rmcp::handler::server::tool::ToolRouter;
use rmcp::handler::server::wrapper::Parameters;
use rmcp::model::{CallToolResult, Implementation, ServerCapabilities, ServerInfo};
use rmcp::transport::stdio;
use rmcp::{tool, tool_handler, tool_router, ErrorData, ServerHandler, ServiceExt};
use schemars::JsonSchema;
use serde::Deserialize;
use serde_json::{json, Map, Number, Value};
use tokio::sync::OnceCell;
use xbbg_async::engine::{Engine, EngineConfig, ExtractorType, RequestParams, RetryPolicy};
use xbbg_async::services::{Operation, Service};
use xbbg_async::BlpAsyncError;
use xbbg_core::{AuthConfig, BlpError};

#[derive(Clone, Debug)]
struct ResultLimits {
    max_rows: usize,
    max_string_chars: usize,
}

#[derive(Clone, Copy, Debug, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
enum ReferenceFormat {
    Long,
    LongTyped,
    LongMetadata,
}

impl ReferenceFormat {
    fn as_str(self) -> &'static str {
        match self {
            Self::Long => "long",
            Self::LongTyped => "long_typed",
            Self::LongMetadata => "long_metadata",
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
enum HistoricalFormat {
    Long,
    LongTyped,
    LongMetadata,
    #[serde(alias = "semi_long")]
    Wide,
}

impl HistoricalFormat {
    fn as_str(self) -> &'static str {
        match self {
            Self::Long => "long",
            Self::LongTyped => "long_typed",
            Self::LongMetadata => "long_metadata",
            Self::Wide => "wide",
        }
    }
}

struct XbbgMcpServer {
    tool_router: ToolRouter<Self>,
    engine: OnceCell<Arc<Engine>>,
    engine_config: EngineConfig,
    result_limits: ResultLimits,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BdpArgs {
    tickers: Vec<String>,
    fields: Vec<String>,
    #[serde(default)]
    overrides: Option<BTreeMap<String, String>>,
    #[serde(default)]
    options: Option<BTreeMap<String, String>>,
    #[serde(default)]
    field_types: Option<BTreeMap<String, String>>,
    #[serde(default)]
    format: Option<ReferenceFormat>,
    #[serde(default)]
    include_security_errors: bool,
    #[serde(default)]
    validate_fields: Option<bool>,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BdhArgs {
    tickers: Vec<String>,
    fields: Vec<String>,
    start_date: String,
    end_date: String,
    #[serde(default)]
    overrides: Option<BTreeMap<String, String>>,
    #[serde(default)]
    options: Option<BTreeMap<String, String>>,
    #[serde(default)]
    field_types: Option<BTreeMap<String, String>>,
    #[serde(default)]
    format: Option<HistoricalFormat>,
    #[serde(default)]
    validate_fields: Option<bool>,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BdsArgs {
    tickers: Vec<String>,
    field: String,
    #[serde(default)]
    overrides: Option<BTreeMap<String, String>>,
    #[serde(default)]
    options: Option<BTreeMap<String, String>>,
    #[serde(default)]
    validate_fields: Option<bool>,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BdibArgs {
    ticker: String,
    start_datetime: String,
    end_datetime: String,
    interval: u32,
    #[serde(default)]
    event_type: Option<String>,
    #[serde(default)]
    request_tz: Option<String>,
    #[serde(default)]
    output_tz: Option<String>,
    #[serde(default)]
    options: Option<BTreeMap<String, String>>,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BqlArgs {
    expression: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BsrchArgs {
    domain: String,
    #[serde(default)]
    parameters: Option<BTreeMap<String, String>>,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct BfldsArgs {
    #[serde(default)]
    fields: Option<Vec<String>>,
    #[serde(default)]
    search_spec: Option<String>,
}

#[derive(Debug, Deserialize, JsonSchema)]
struct RequestArgs {
    service: String,
    #[serde(default)]
    operation: Option<String>,
    #[serde(default)]
    request_operation: Option<String>,
    #[serde(default)]
    request_id: Option<String>,
    #[serde(default)]
    extractor: Option<String>,
    #[serde(default)]
    securities: Option<Vec<String>>,
    #[serde(default)]
    security: Option<String>,
    #[serde(default)]
    fields: Option<Vec<String>>,
    #[serde(default)]
    overrides: Option<BTreeMap<String, String>>,
    #[serde(default)]
    elements: Option<BTreeMap<String, String>>,
    #[serde(default)]
    kwargs: Option<BTreeMap<String, String>>,
    #[serde(default)]
    start_date: Option<String>,
    #[serde(default)]
    end_date: Option<String>,
    #[serde(default)]
    start_datetime: Option<String>,
    #[serde(default)]
    end_datetime: Option<String>,
    #[serde(default)]
    request_tz: Option<String>,
    #[serde(default)]
    output_tz: Option<String>,
    #[serde(default)]
    event_type: Option<String>,
    #[serde(default)]
    event_types: Option<Vec<String>>,
    #[serde(default)]
    interval: Option<u32>,
    #[serde(default)]
    options: Option<BTreeMap<String, String>>,
    #[serde(default)]
    field_types: Option<BTreeMap<String, String>>,
    #[serde(default)]
    include_security_errors: Option<bool>,
    #[serde(default)]
    validate_fields: Option<bool>,
    #[serde(default)]
    search_spec: Option<String>,
    #[serde(default)]
    field_ids: Option<Vec<String>>,
    #[serde(default)]
    format: Option<HistoricalFormat>,
}

impl XbbgMcpServer {
    fn new_from_env() -> Result<Self, String> {
        let (engine_config, result_limits) = load_settings_from_env()?;
        Ok(Self {
            tool_router: Self::tool_router(),
            engine: OnceCell::new(),
            engine_config,
            result_limits,
        })
    }

    async fn engine(&self) -> Result<&Arc<Engine>, ErrorData> {
        self.engine
            .get_or_try_init(|| async {
                let config = self.engine_config.clone();
                tokio::task::spawn_blocking(move || {
                    Engine::start(config)
                        .map(Arc::new)
                        .map_err(map_request_error)
                })
                .await
                .map_err(|err| {
                    ErrorData::internal_error(format!("engine startup task failed: {err}"), None)
                })?
            })
            .await
    }

    async fn execute_request(&self, params: RequestParams) -> Result<CallToolResult, ErrorData> {
        let batch = self
            .engine()
            .await?
            .request(params)
            .await
            .map_err(map_request_error)?;
        let payload = record_batch_to_json(&batch, &self.result_limits)?;
        Ok(CallToolResult::structured(payload))
    }
}

#[tool_router]
impl XbbgMcpServer {
    #[tool(
        description = "Bloomberg reference data request (bdp). Returns structured JSON with schema metadata and bounded rows."
    )]
    async fn bdp(
        &self,
        Parameters(args): Parameters<BdpArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let tickers = normalize_nonempty_list("tickers", args.tickers)?;
        let fields = normalize_nonempty_list("fields", args.fields)?;

        self.execute_request(RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::ReferenceData.to_string(),
            extractor: ExtractorType::RefData,
            extractor_set: true,
            securities: Some(tickers),
            fields: Some(fields),
            overrides: map_to_pairs(args.overrides),
            options: map_to_pairs(args.options),
            field_types: map_to_hash_map(args.field_types),
            include_security_errors: args.include_security_errors,
            validate_fields: args.validate_fields,
            format: args.format.map(|format| format.as_str().to_string()),
            ..Default::default()
        })
        .await
    }

    #[tool(
        description = "Bloomberg historical data request (bdh). Dates must be YYYYMMDD or YYYY-MM-DD."
    )]
    async fn bdh(
        &self,
        Parameters(args): Parameters<BdhArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let tickers = normalize_nonempty_list("tickers", args.tickers)?;
        let fields = normalize_nonempty_list("fields", args.fields)?;
        let start_date = normalize_bloomberg_date("start_date", args.start_date)?;
        let end_date = normalize_bloomberg_date("end_date", args.end_date)?;

        self.execute_request(RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::HistoricalData.to_string(),
            extractor: ExtractorType::HistData,
            extractor_set: true,
            securities: Some(tickers),
            fields: Some(fields),
            start_date: Some(start_date),
            end_date: Some(end_date),
            overrides: map_to_pairs(args.overrides),
            options: map_to_pairs(args.options),
            field_types: map_to_hash_map(args.field_types),
            validate_fields: args.validate_fields,
            format: args.format.map(|format| format.as_str().to_string()),
            ..Default::default()
        })
        .await
    }

    #[tool(
        description = "Bloomberg bulk data request (bds). Uses the bulk extractor and requires exactly one bulk field."
    )]
    async fn bds(
        &self,
        Parameters(args): Parameters<BdsArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let tickers = normalize_nonempty_list("tickers", args.tickers)?;
        let field = normalize_required_string("field", args.field)?;

        self.execute_request(RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::ReferenceData.to_string(),
            extractor: ExtractorType::BulkData,
            extractor_set: true,
            securities: Some(tickers),
            fields: Some(vec![field]),
            overrides: map_to_pairs(args.overrides),
            options: map_to_pairs(args.options),
            validate_fields: args.validate_fields,
            ..Default::default()
        })
        .await
    }

    #[tool(
        description = "Bloomberg intraday bar request (bdib). Datetimes must be ISO-8601 strings and interval must be positive."
    )]
    async fn bdib(
        &self,
        Parameters(args): Parameters<BdibArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let ticker = normalize_required_string("ticker", args.ticker)?;
        let start_datetime = validate_datetime_string("start_datetime", args.start_datetime)?;
        let end_datetime = validate_datetime_string("end_datetime", args.end_datetime)?;
        if args.interval == 0 {
            return Err(ErrorData::invalid_params(
                "interval must be greater than zero",
                None,
            ));
        }

        self.execute_request(RequestParams {
            service: Service::RefData.to_string(),
            operation: Operation::IntradayBar.to_string(),
            extractor: ExtractorType::IntradayBar,
            extractor_set: true,
            security: Some(ticker),
            event_type: Some(trim_optional(args.event_type).unwrap_or_else(|| "TRADE".to_string())),
            interval: Some(args.interval),
            start_datetime: Some(start_datetime),
            end_datetime: Some(end_datetime),
            request_tz: trim_optional(args.request_tz),
            output_tz: trim_optional(args.output_tz),
            options: map_to_pairs(args.options),
            ..Default::default()
        })
        .await
    }

    #[tool(description = "Bloomberg Query Language request (bql).")]
    async fn bql(
        &self,
        Parameters(args): Parameters<BqlArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let expression = normalize_required_string("expression", args.expression)?;

        self.execute_request(RequestParams {
            service: Service::BqlSvc.to_string(),
            operation: Operation::BqlSendQuery.to_string(),
            extractor: ExtractorType::Bql,
            extractor_set: true,
            elements: Some(vec![("expression".to_string(), expression)]),
            ..Default::default()
        })
        .await
    }

    #[tool(
        description = "Bloomberg search request (bsrch). The domain selects the saved Bloomberg search, extra parameters are passed through as named request elements."
    )]
    async fn bsrch(
        &self,
        Parameters(args): Parameters<BsrchArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let domain = normalize_required_string("domain", args.domain)?;
        let mut elements = vec![("Domain".to_string(), domain)];
        if let Some(parameters) = map_to_pairs(args.parameters) {
            elements.extend(parameters);
        }

        self.execute_request(RequestParams {
            service: Service::ExrSvc.to_string(),
            operation: Operation::ExcelGetGrid.to_string(),
            extractor: ExtractorType::Bsrch,
            extractor_set: true,
            elements: Some(elements),
            ..Default::default()
        })
        .await
    }

    #[tool(
        description = "Bloomberg field metadata lookup (bflds). Supply either concrete field ids or a search_spec, but not both."
    )]
    async fn bflds(
        &self,
        Parameters(args): Parameters<BfldsArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let fields = args
            .fields
            .map(|values| normalize_nonempty_list("fields", values))
            .transpose()?;
        let search_spec = trim_optional(args.search_spec);

        match (fields, search_spec) {
            (Some(field_ids), None) => {
                self.execute_request(RequestParams {
                    service: Service::ApiFlds.to_string(),
                    operation: Operation::FieldInfo.to_string(),
                    extractor: ExtractorType::FieldInfo,
                    extractor_set: true,
                    field_ids: Some(field_ids),
                    ..Default::default()
                })
                .await
            }
            (None, Some(search_spec)) => {
                self.execute_request(RequestParams {
                    service: Service::ApiFlds.to_string(),
                    operation: Operation::FieldSearch.to_string(),
                    extractor: ExtractorType::Generic,
                    extractor_set: true,
                    search_spec: Some(search_spec),
                    ..Default::default()
                })
                .await
            }
            (Some(_), Some(_)) => Err(ErrorData::invalid_params(
                "bflds accepts either fields or search_spec, not both",
                None,
            )),
            (None, None) => Err(ErrorData::invalid_params(
                "bflds requires either fields or search_spec",
                None,
            )),
        }
    }

    #[tool(
        description = "Generic Bloomberg request. Supports raw/custom service and operation strings, including RawRequest via request_operation."
    )]
    async fn request(
        &self,
        Parameters(args): Parameters<RequestArgs>,
    ) -> Result<CallToolResult, ErrorData> {
        let service = normalize_required_string("service", args.service)?;
        let request_operation = trim_optional(args.request_operation);
        let operation = match trim_optional(args.operation) {
            Some(operation) => operation,
            None if request_operation.is_some() => Operation::RawRequest.to_string(),
            None => {
                return Err(ErrorData::invalid_params(
                    "operation is required unless request_operation is used for RawRequest",
                    None,
                ))
            }
        };

        let operation_kind = match Operation::from_str(&operation) {
            Ok(kind) => kind,
            Err(never) => match never {},
        };
        let mut fields = args
            .fields
            .map(|values| normalize_nonempty_list("fields", values))
            .transpose()?;
        let mut field_ids = args
            .field_ids
            .map(|values| normalize_nonempty_list("field_ids", values))
            .transpose()?;
        let mut search_spec = trim_optional(args.search_spec);

        match operation_kind {
            Operation::FieldInfo => {
                if fields.is_some() && field_ids.is_some() {
                    return Err(ErrorData::invalid_params(
                        "FieldInfoRequest accepts either fields or field_ids, not both",
                        None,
                    ));
                }
                if field_ids.is_none() {
                    field_ids = fields.take();
                }
            }
            Operation::FieldSearch => {
                if fields.is_some() && search_spec.is_some() {
                    return Err(ErrorData::invalid_params(
                        "FieldSearchRequest accepts either fields or search_spec, not both",
                        None,
                    ));
                }
                if search_spec.is_none() {
                    if let Some(mut field_values) = fields.take() {
                        if field_values.len() != 1 {
                            return Err(ErrorData::invalid_params(
                                "FieldSearchRequest requires exactly one field value when fields is used as a search alias",
                                None,
                            ));
                        }
                        search_spec = field_values.pop();
                    }
                }
            }
            _ => {}
        }

        let format = match (args.format, &operation_kind) {
            (Some(HistoricalFormat::Wide), Operation::ReferenceData) => {
                return Err(ErrorData::invalid_params(
                    "ReferenceDataRequest does not support format=wide",
                    None,
                ));
            }
            (Some(format), Operation::ReferenceData | Operation::HistoricalData) => {
                Some(format.as_str().to_string())
            }
            (Some(_), _) => {
                return Err(ErrorData::invalid_params(
                    "format is only supported for ReferenceDataRequest and HistoricalDataRequest",
                    None,
                ));
            }
            (None, _) => None,
        };

        let extractor_set = args.extractor.is_some();
        let extractor = match args.extractor.as_deref() {
            Some(extractor) => parse_extractor(extractor)?,
            None => ExtractorType::default(),
        };

        self.execute_request(RequestParams {
            service,
            operation,
            request_operation,
            request_id: trim_optional(args.request_id),
            extractor,
            extractor_set,
            securities: args
                .securities
                .map(|values| normalize_nonempty_list("securities", values))
                .transpose()?,
            security: args
                .security
                .map(|value| normalize_required_string("security", value))
                .transpose()?,
            fields,
            overrides: map_to_pairs(args.overrides),
            elements: map_to_pairs(args.elements),
            kwargs: map_to_hash_map(args.kwargs),
            // The generic tool intentionally preserves caller-supplied request strings instead of
            // normalizing them to one wrapper opinion; power users may rely on raw/custom semantics.
            start_date: trim_optional(args.start_date),
            end_date: trim_optional(args.end_date),
            start_datetime: trim_optional(args.start_datetime),
            end_datetime: trim_optional(args.end_datetime),
            request_tz: trim_optional(args.request_tz),
            output_tz: trim_optional(args.output_tz),
            event_type: trim_optional(args.event_type),
            event_types: args
                .event_types
                .map(|values| normalize_nonempty_list("event_types", values))
                .transpose()?,
            interval: args.interval,
            options: map_to_pairs(args.options),
            field_types: map_to_hash_map(args.field_types),
            include_security_errors: args.include_security_errors.unwrap_or(false),
            validate_fields: args.validate_fields,
            search_spec,
            field_ids,
            format,
        })
        .await
    }
}

#[tool_handler]
impl ServerHandler for XbbgMcpServer {
    fn get_info(&self) -> ServerInfo {
        // The server only advertises tools for now; request execution stays lazy so stdio startup
        // does not require a live Bloomberg session before the client can initialize.
        ServerInfo::new(ServerCapabilities::builder().enable_tools().build())
            .with_server_info(
                Implementation::new(env!("CARGO_PKG_NAME"), env!("CARGO_PKG_VERSION"))
                    .with_title("xbbg MCP")
                    .with_description(
                        "Request/response Bloomberg tools backed directly by xbbg-async. Current env configuration supports single-host connectivity, core auth modes, and request-pool tuning.",
                    ),
            )
            .with_instructions(
                "Use bdp, bdh, bds, bdib, bql, bsrch, bflds, or request. Results are JSON with schema metadata and bounded rows. This MCP server currently exposes host/port, selected auth env vars, and core pool settings rather than the full EngineConfig surface.",
            )
    }
}

fn load_settings_from_env() -> Result<(EngineConfig, ResultLimits), String> {
    // Keep the initial env surface intentionally narrow: expose the subset we can document and
    // support honestly for MCP deployment, rather than implying full parity with every EngineConfig knob.
    let mut config = EngineConfig::default();

    config.server_host = env_string(&[
        "XBBG_MCP_HOST",
        "XBBG_MCP_SERVER_HOST",
        "XBBG_HOST",
        "XBBG_SERVER_HOST",
        "XBBG_SERVER",
    ])
    .unwrap_or(config.server_host);
    config.server_port = env_u16(&[
        "XBBG_MCP_PORT",
        "XBBG_MCP_SERVER_PORT",
        "XBBG_PORT",
        "XBBG_SERVER_PORT",
    ])?
    .unwrap_or(config.server_port);
    config.request_pool_size =
        env_usize(&["XBBG_MCP_REQUEST_POOL_SIZE", "XBBG_REQUEST_POOL_SIZE"])?
            .unwrap_or(config.request_pool_size);
    config.validation_mode = env_parsed(
        &["XBBG_MCP_VALIDATION_MODE", "XBBG_VALIDATION_MODE"],
        "validation_mode",
    )?
    .unwrap_or(config.validation_mode);
    config.field_cache_path = env_string(&["XBBG_MCP_FIELD_CACHE_PATH", "XBBG_FIELD_CACHE_PATH"])
        .map(PathBuf::from)
        .or_else(|| config.field_cache_path.clone());
    if let Some(warmup_services) = env_csv(&["XBBG_MCP_WARMUP_SERVICES", "XBBG_WARMUP_SERVICES"]) {
        config.warmup_services = warmup_services;
    }
    config.sdk_log_level = env_parsed(
        &["XBBG_MCP_SDK_LOG_LEVEL", "XBBG_SDK_LOG_LEVEL"],
        "sdk_log_level",
    )?
    .unwrap_or(config.sdk_log_level);
    config.num_start_attempts = env_usize(&[
        "XBBG_MCP_NUM_START_ATTEMPTS",
        "XBBG_NUM_START_ATTEMPTS",
        "XBBG_MAX_ATTEMPT",
    ])?
    .unwrap_or(config.num_start_attempts);
    config.auto_restart_on_disconnection = env_bool(&[
        "XBBG_MCP_AUTO_RESTART_ON_DISCONNECTION",
        "XBBG_AUTO_RESTART_ON_DISCONNECTION",
        "XBBG_AUTO_RESTART",
    ])?
    .unwrap_or(config.auto_restart_on_disconnection);
    config.retry_policy = RetryPolicy {
        max_retries: env_u32(&["XBBG_MCP_RETRY_MAX_RETRIES", "XBBG_RETRY_MAX_RETRIES"])?
            .unwrap_or(config.retry_policy.max_retries),
        initial_delay_ms: env_u64(&[
            "XBBG_MCP_RETRY_INITIAL_DELAY_MS",
            "XBBG_RETRY_INITIAL_DELAY_MS",
        ])?
        .unwrap_or(config.retry_policy.initial_delay_ms),
        backoff_factor: env_f64(&["XBBG_MCP_RETRY_BACKOFF_FACTOR", "XBBG_RETRY_BACKOFF_FACTOR"])?
            .unwrap_or(config.retry_policy.backoff_factor),
        max_delay_ms: env_u64(&["XBBG_MCP_RETRY_MAX_DELAY_MS", "XBBG_RETRY_MAX_DELAY_MS"])?
            .unwrap_or(config.retry_policy.max_delay_ms),
    };
    config.overflow_policy = env_parsed(
        &["XBBG_MCP_OVERFLOW_POLICY", "XBBG_OVERFLOW_POLICY"],
        "overflow_policy",
    )?
    .unwrap_or(config.overflow_policy);
    config.auth = build_auth_from_env()?;

    let result_limits = ResultLimits {
        max_rows: env_usize(&["XBBG_MCP_MAX_ROWS"])?.unwrap_or(500).max(1),
        max_string_chars: env_usize(&["XBBG_MCP_MAX_STRING_CHARS"])?
            .unwrap_or(2_048)
            .max(16),
    };

    Ok((config, result_limits))
}

fn build_auth_from_env() -> Result<Option<AuthConfig>, String> {
    let auth_method = env_string(&["XBBG_MCP_AUTH_METHOD", "XBBG_AUTH_METHOD"]);
    let app_name = env_string(&["XBBG_MCP_APP_NAME", "XBBG_APP_NAME"]);
    let dir_property = env_string(&["XBBG_MCP_DIR_PROPERTY", "XBBG_DIR_PROPERTY"]);
    let user_id = env_string(&["XBBG_MCP_USER_ID", "XBBG_USER_ID"]);
    let ip_address = env_string(&["XBBG_MCP_IP_ADDRESS", "XBBG_IP_ADDRESS"]);
    let token = env_string(&["XBBG_MCP_TOKEN", "XBBG_TOKEN"]);

    let Some(method) = auth_method.map(|value| value.to_ascii_lowercase()) else {
        if app_name.is_some()
            || dir_property.is_some()
            || user_id.is_some()
            || ip_address.is_some()
            || token.is_some()
        {
            return Err(
                "auth_method is required when auth-specific environment variables are set"
                    .to_string(),
            );
        }
        return Ok(None);
    };

    let auth = match method.as_str() {
        "" | "none" => None,
        "user" => Some(AuthConfig::User),
        "app" => Some(AuthConfig::App {
            app_name: required_env_value(&app_name, "app_name", &method)?,
        }),
        "userapp" => Some(AuthConfig::UserApp {
            app_name: required_env_value(&app_name, "app_name", &method)?,
        }),
        "dir" | "directory" => Some(AuthConfig::Directory {
            property_name: required_env_value(&dir_property, "dir_property", &method)?,
        }),
        "manual" => Some(AuthConfig::Manual {
            app_name: required_env_value(&app_name, "app_name", &method)?,
            user_id: required_env_value(&user_id, "user_id", &method)?,
            ip_address: required_env_value(&ip_address, "ip_address", &method)?,
        }),
        "token" => Some(AuthConfig::Token {
            token: required_env_value(&token, "token", &method)?,
        }),
        other => {
            return Err(format!(
                "invalid auth_method '{other}' (expected none, user, app, userapp, dir, manual, or token)"
            ));
        }
    };

    Ok(auth)
}

fn required_env_value(value: &Option<String>, field: &str, method: &str) -> Result<String, String> {
    value
        .clone()
        .ok_or_else(|| format!("{field} is required for auth_method={method}"))
}

fn env_string(keys: &[&str]) -> Option<String> {
    keys.iter().find_map(|key| {
        env::var(key)
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
    })
}

fn env_csv(keys: &[&str]) -> Option<Vec<String>> {
    keys.iter().find_map(|key| {
        env::var(key).ok().map(|value| {
            value
                .split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(ToOwned::to_owned)
                .collect::<Vec<_>>()
        })
    })
}

fn env_usize(keys: &[&str]) -> Result<Option<usize>, String> {
    env_parse(keys, "usize", str::parse)
}

fn env_u16(keys: &[&str]) -> Result<Option<u16>, String> {
    env_parse(keys, "u16", str::parse)
}

fn env_u32(keys: &[&str]) -> Result<Option<u32>, String> {
    env_parse(keys, "u32", str::parse)
}

fn env_u64(keys: &[&str]) -> Result<Option<u64>, String> {
    env_parse(keys, "u64", str::parse)
}

fn env_f64(keys: &[&str]) -> Result<Option<f64>, String> {
    env_parse(keys, "f64", str::parse)
}

fn env_bool(keys: &[&str]) -> Result<Option<bool>, String> {
    env_parse(keys, "bool", parse_bool)
}

fn env_parsed<T>(keys: &[&str], label: &str) -> Result<Option<T>, String>
where
    T: std::str::FromStr,
    T::Err: std::fmt::Display,
{
    env_parse(keys, label, str::parse)
}

fn env_parse<T, E, F>(keys: &[&str], label: &str, parser: F) -> Result<Option<T>, String>
where
    F: Fn(&str) -> Result<T, E>,
    E: std::fmt::Display,
{
    for key in keys {
        if let Ok(raw) = env::var(key) {
            let value = raw.trim();
            if value.is_empty() {
                continue;
            }
            return parser(value)
                .map(Some)
                .map_err(|err| format!("invalid {label} in {key}: {err}"));
        }
    }
    Ok(None)
}

fn parse_bool(value: &str) -> Result<bool, String> {
    match value.to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Ok(true),
        "0" | "false" | "no" | "off" => Ok(false),
        _ => Err(format!("expected true/false style boolean, got '{value}'")),
    }
}

fn normalize_required_string(field: &str, value: String) -> Result<String, ErrorData> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(ErrorData::invalid_params(
            format!("{field} must be a non-empty string"),
            None,
        ));
    }
    Ok(trimmed.to_string())
}

fn normalize_nonempty_list(field: &str, values: Vec<String>) -> Result<Vec<String>, ErrorData> {
    let normalized = values
        .into_iter()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .collect::<Vec<_>>();
    if normalized.is_empty() {
        return Err(ErrorData::invalid_params(
            format!("{field} must contain at least one non-empty value"),
            None,
        ));
    }
    Ok(normalized)
}

fn trim_optional(value: Option<String>) -> Option<String> {
    value
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn normalize_bloomberg_date(field: &str, value: String) -> Result<String, ErrorData> {
    let trimmed = normalize_required_string(field, value)?;
    let parsed = NaiveDate::parse_from_str(&trimmed, "%Y%m%d")
        .or_else(|_| NaiveDate::parse_from_str(&trimmed, "%Y-%m-%d"))
        .map_err(|_| {
            ErrorData::invalid_params(format!("{field} must be YYYYMMDD or YYYY-MM-DD"), None)
        })?;
    Ok(parsed.format("%Y%m%d").to_string())
}

fn validate_datetime_string(field: &str, value: String) -> Result<String, ErrorData> {
    let trimmed = normalize_required_string(field, value)?;
    let valid = DateTime::parse_from_rfc3339(&trimmed).is_ok()
        || NaiveDateTime::parse_from_str(&trimmed, "%Y-%m-%dT%H:%M:%S").is_ok()
        || NaiveDateTime::parse_from_str(&trimmed, "%Y-%m-%d %H:%M:%S").is_ok()
        || NaiveDateTime::parse_from_str(&trimmed, "%Y-%m-%dT%H:%M:%S%.f").is_ok()
        || NaiveDateTime::parse_from_str(&trimmed, "%Y-%m-%d %H:%M:%S%.f").is_ok();

    if !valid {
        return Err(ErrorData::invalid_params(
            format!("{field} must be an ISO-8601 datetime string"),
            None,
        ));
    }

    Ok(trimmed)
}

fn parse_extractor(value: &str) -> Result<ExtractorType, ErrorData> {
    ExtractorType::parse(value.trim()).ok_or_else(|| {
        ErrorData::invalid_params(
            format!("unknown extractor '{value}'"),
            Some(json!({
                "expected": [
                    "bql",
                    "bsrch",
                    "bulk",
                    "fieldinfo",
                    "generic",
                    "histdata",
                    "intraday_bar",
                    "intraday_tick",
                    "refdata"
                ]
            })),
        )
    })
}

fn map_to_pairs(map: Option<BTreeMap<String, String>>) -> Option<Vec<(String, String)>> {
    match map {
        Some(entries) if !entries.is_empty() => Some(entries.into_iter().collect::<Vec<_>>()),
        _ => None,
    }
}

fn map_to_hash_map(map: Option<BTreeMap<String, String>>) -> Option<HashMap<String, String>> {
    match map {
        Some(entries) if !entries.is_empty() => {
            Some(entries.into_iter().collect::<HashMap<_, _>>())
        }
        _ => None,
    }
}

fn map_request_error(error: BlpAsyncError) -> ErrorData {
    match error {
        BlpAsyncError::ConfigError { detail } => ErrorData::invalid_params(detail, None),
        BlpAsyncError::Blp(blp_error) | BlpAsyncError::BlpError(blp_error) => {
            map_blp_error(blp_error)
        }
        other => ErrorData::internal_error(other.to_string(), None),
    }
}

fn map_blp_error(error: BlpError) -> ErrorData {
    match error {
        BlpError::InvalidArgument { detail } => ErrorData::invalid_params(detail, None),
        BlpError::SchemaOperationNotFound { service, operation } => ErrorData::invalid_params(
            format!("unknown Bloomberg operation '{operation}' for service '{service}'"),
            None,
        ),
        BlpError::SchemaElementNotFound { parent, name } => ErrorData::invalid_params(
            format!("unknown Bloomberg request element '{name}' under '{parent}'"),
            None,
        ),
        BlpError::SchemaTypeMismatch {
            element,
            expected,
            found,
        } => ErrorData::invalid_params(
            format!("type mismatch at '{element}': expected {expected}, found {found}"),
            None,
        ),
        BlpError::SchemaUnsupported { element, detail } => ErrorData::invalid_params(
            format!("unsupported schema construct at '{element}': {detail}"),
            None,
        ),
        BlpError::Validation { message, errors } => {
            let details = errors
                .iter()
                .map(|error| match &error.suggestion {
                    Some(suggestion) => {
                        format!(
                            "{}: {} (did you mean '{suggestion}'?)",
                            error.path, error.message
                        )
                    }
                    None => format!("{}: {}", error.path, error.message),
                })
                .collect::<Vec<_>>();
            let detail = if details.is_empty() {
                message
            } else {
                format!("{message}: {}", details.join("; "))
            };
            ErrorData::invalid_params(detail, None)
        }
        other => ErrorData::internal_error(other.to_string(), None),
    }
}

fn record_batch_to_json(batch: &RecordBatch, limits: &ResultLimits) -> Result<Value, ErrorData> {
    let schema = batch.schema();
    let schema_json = schema
        .fields()
        .iter()
        .map(|field| {
            json!({
                "name": field.name(),
                "data_type": field.data_type().to_string(),
                "nullable": field.is_nullable(),
            })
        })
        .collect::<Vec<_>>();

    let total_rows = batch.num_rows();
    let returned_rows = total_rows.min(limits.max_rows);
    let mut value_truncated = false;
    let mut rows = Vec::with_capacity(returned_rows);

    // MCP clients need structured JSON, not opaque Arrow IPC. We keep the Arrow schema in-band and
    // bound row/string sizes so a single large Bloomberg response cannot overwhelm a stdio client.
    for row_index in 0..returned_rows {
        let mut row = Map::with_capacity(schema.fields().len());
        for (field, column) in schema.fields().iter().zip(batch.columns()) {
            let value = array_cell_to_json(
                column,
                field.data_type(),
                row_index,
                limits.max_string_chars,
                &mut value_truncated,
            )?;
            row.insert(field.name().to_string(), value);
        }
        rows.push(Value::Object(row));
    }

    Ok(json!({
        "schema": schema_json,
        "row_count": total_rows,
        "returned_rows": returned_rows,
        "truncated": {
            "rows": total_rows > returned_rows,
            "values": value_truncated,
        },
        "rows": rows,
    }))
}

fn array_cell_to_json(
    column: &ArrayRef,
    data_type: &DataType,
    row_index: usize,
    max_string_chars: usize,
    value_truncated: &mut bool,
) -> Result<Value, ErrorData> {
    if column.is_null(row_index) {
        return Ok(Value::Null);
    }

    let value = match data_type {
        DataType::Utf8 => {
            json_string_from_array(column, row_index, max_string_chars, value_truncated)?
        }
        DataType::LargeUtf8 => {
            json_large_string_from_array(column, row_index, max_string_chars, value_truncated)?
        }
        DataType::Boolean => {
            Value::Bool(downcast::<BooleanArray>(column, "Boolean")?.value(row_index))
        }
        DataType::Int32 => Value::Number(Number::from(
            downcast::<Int32Array>(column, "Int32")?.value(row_index),
        )),
        DataType::Int64 => int64_to_json(downcast::<Int64Array>(column, "Int64")?.value(row_index)),
        DataType::UInt32 => Value::Number(Number::from(
            downcast::<UInt32Array>(column, "UInt32")?.value(row_index),
        )),
        DataType::UInt64 => {
            uint64_to_json(downcast::<UInt64Array>(column, "UInt64")?.value(row_index))
        }
        DataType::Float32 => float_to_json(
            downcast::<Float32Array>(column, "Float32")?.value(row_index) as f64,
            column.as_ref(),
            row_index,
        )?,
        DataType::Float64 => float_to_json(
            downcast::<Float64Array>(column, "Float64")?.value(row_index),
            column.as_ref(),
            row_index,
        )?,
        DataType::Date32 => {
            let array = downcast::<Date32Array>(column, "Date32")?;
            truncate_json_string(
                array_value_to_string(array, row_index).map_err(display_error)?,
                max_string_chars,
                value_truncated,
            )
        }
        DataType::Timestamp(_, _) => {
            let array = downcast::<TimestampMicrosecondArray>(column, "TimestampMicrosecond")?;
            truncate_json_string(
                array_value_to_string(array, row_index).map_err(display_error)?,
                max_string_chars,
                value_truncated,
            )
        }
        _ => truncate_json_string(
            array_value_to_string(column.as_ref(), row_index).map_err(display_error)?,
            max_string_chars,
            value_truncated,
        ),
    };

    Ok(value)
}

fn int64_to_json(value: i64) -> Value {
    const JS_SAFE_INTEGER_MIN: i64 = -9_007_199_254_740_991;
    const JS_SAFE_INTEGER_MAX: i64 = 9_007_199_254_740_991;

    if (JS_SAFE_INTEGER_MIN..=JS_SAFE_INTEGER_MAX).contains(&value) {
        Value::Number(Number::from(value))
    } else {
        Value::String(value.to_string())
    }
}

fn uint64_to_json(value: u64) -> Value {
    const JS_SAFE_INTEGER_MAX: u64 = 9_007_199_254_740_991;

    if value <= JS_SAFE_INTEGER_MAX {
        Value::Number(Number::from(value))
    } else {
        Value::String(value.to_string())
    }
}

fn float_to_json(value: f64, column: &dyn Array, row_index: usize) -> Result<Value, ErrorData> {
    match Number::from_f64(value) {
        Some(number) => Ok(Value::Number(number)),
        None => Ok(Value::String(
            array_value_to_string(column, row_index).map_err(display_error)?,
        )),
    }
}

fn json_string_from_array(
    column: &ArrayRef,
    row_index: usize,
    max_string_chars: usize,
    value_truncated: &mut bool,
) -> Result<Value, ErrorData> {
    let array = downcast::<StringArray>(column, "Utf8")?;
    Ok(truncate_json_string(
        array.value(row_index).to_string(),
        max_string_chars,
        value_truncated,
    ))
}

fn json_large_string_from_array(
    column: &ArrayRef,
    row_index: usize,
    max_string_chars: usize,
    value_truncated: &mut bool,
) -> Result<Value, ErrorData> {
    let array = downcast::<LargeStringArray>(column, "LargeUtf8")?;
    Ok(truncate_json_string(
        array.value(row_index).to_string(),
        max_string_chars,
        value_truncated,
    ))
}

fn truncate_json_string(value: String, max_chars: usize, value_truncated: &mut bool) -> Value {
    if value.chars().count() <= max_chars {
        return Value::String(value);
    }

    *value_truncated = true;
    let truncated = value.chars().take(max_chars).collect::<String>();
    Value::String(format!("{truncated}…"))
}

fn downcast<'a, T: 'static>(column: &'a ArrayRef, label: &str) -> Result<&'a T, ErrorData> {
    column.as_any().downcast_ref::<T>().ok_or_else(|| {
        ErrorData::internal_error(format!("failed to downcast Arrow column as {label}"), None)
    })
}

fn display_error(error: arrow::error::ArrowError) -> ErrorData {
    ErrorData::internal_error(format!("failed to format Arrow value: {error}"), None)
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let server = XbbgMcpServer::new_from_env()?;
    server.serve(stdio()).await?.waiting().await?;
    Ok(())
}

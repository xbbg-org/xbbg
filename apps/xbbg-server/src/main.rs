use arrow::record_batch::RecordBatch;
use arrow_json::ArrayWriter;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Json};
use axum::routing::{get, post};
use axum::{serve, Router};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::str::FromStr;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tokio::net::TcpListener;
use tokio::sync::{broadcast, RwLock};
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use xbbg_async::engine::{Engine, EngineConfig, ExtractorType, OverflowPolicy, RequestParams};
use xbbg_async::{BlpAsyncError, ValidationMode};
use xbbg_core::BlpError;

#[derive(Clone)]
struct AppState {
    engine: Arc<Engine>,
    request_store: Arc<RwLock<HashMap<String, RequestRecord>>>,
    request_seq: Arc<AtomicU64>,
    request_events: broadcast::Sender<RequestEventEnvelope>,
    subscription_seq: Arc<AtomicU64>,
    config: BridgeConfig,
}

#[derive(Clone)]
struct BridgeConfig {
    listen_addr: SocketAddr,
    session_host: String,
    session_port: u16,
}

impl BridgeConfig {
    fn from_env() -> Result<Self, String> {
        let listen_addr = env::var("XBBG_BRIDGE_LISTEN")
            .unwrap_or_else(|_| "127.0.0.1:7878".to_string())
            .parse()
            .map_err(|e| format!("invalid XBBG_BRIDGE_LISTEN: {e}"))?;

        let session_host = env::var("XBBG_HOST")
            .or_else(|_| env::var("XBBG_BRIDGE_SESSION_HOST"))
            .unwrap_or_else(|_| "127.0.0.1".to_string());

        let session_port = env::var("XBBG_PORT")
            .or_else(|_| env::var("XBBG_BRIDGE_SESSION_PORT"))
            .ok()
            .and_then(|value| value.parse::<u16>().ok())
            .unwrap_or(8194);

        Ok(Self {
            listen_addr,
            session_host,
            session_port,
        })
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum RequestState {
    Queued,
    Running,
    Done,
    Failed,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RequestRecord {
    request_id: String,
    state: RequestState,
    submitted_at: String,
    started_at: Option<String>,
    completed_at: Option<String>,
    result: Option<Value>,
    error: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RequestAccepted {
    request_id: String,
    state: RequestState,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RequestEventEnvelope {
    event: String,
    request: RequestRecord,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BridgeHealth {
    ok: bool,
    listen_addr: String,
    session_host: String,
    session_port: u16,
    pending_requests: usize,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct StringPair {
    key: String,
    value: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RequestSubmission {
    request_id: Option<String>,
    service: String,
    operation: String,
    request_operation: Option<String>,
    extractor: Option<String>,
    securities: Option<Vec<String>>,
    security: Option<String>,
    fields: Option<Vec<String>>,
    overrides: Option<Vec<StringPair>>,
    elements: Option<Vec<StringPair>>,
    kwargs: Option<Vec<StringPair>>,
    start_date: Option<String>,
    end_date: Option<String>,
    start_datetime: Option<String>,
    end_datetime: Option<String>,
    event_type: Option<String>,
    event_types: Option<Vec<String>>,
    interval: Option<u32>,
    options: Option<Vec<StringPair>>,
    field_types: Option<Vec<StringPair>>,
    include_security_errors: Option<bool>,
    validate_fields: Option<bool>,
    search_spec: Option<String>,
    field_ids: Option<Vec<String>>,
    format: Option<String>,
}

impl TryFrom<RequestSubmission> for RequestParams {
    type Error = String;

    fn try_from(input: RequestSubmission) -> Result<Self, Self::Error> {
        let mut extractor = ExtractorType::default();
        let mut extractor_set = false;
        if let Some(name) = input.extractor.as_deref() {
            extractor = ExtractorType::parse(name)
                .ok_or_else(|| format!("invalid extractor type: {name}"))?;
            extractor_set = true;
        }

        Ok(RequestParams {
            service: input.service,
            operation: input.operation,
            request_operation: input.request_operation,
            extractor,
            extractor_set,
            securities: input.securities,
            security: input.security,
            fields: input.fields,
            overrides: pairs_to_tuples(input.overrides),
            elements: pairs_to_tuples(input.elements),
            kwargs: pairs_to_map(input.kwargs),
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
            validate_fields: input.validate_fields,
            search_spec: input.search_spec,
            field_ids: input.field_ids,
            format: input.format,
        })
    }
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum SubscriptionClientMessage {
    Subscribe {
        subscription_id: Option<String>,
        service: Option<String>,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Option<Vec<String>>,
        stream_capacity: Option<usize>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<String>,
    },
    Unsubscribe,
    Ping,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum SubscriptionServerMessage {
    Subscribed {
        subscription_id: String,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
    },
    Tick {
        subscription_id: String,
        rows: Value,
    },
    Error {
        subscription_id: Option<String>,
        message: String,
    },
    Unsubscribed {
        subscription_id: String,
    },
    Pong,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = BridgeConfig::from_env()?;

    xbbg_log::set_level(xbbg_log::Level::INFO);

    let engine = Arc::new(Engine::start(EngineConfig {
        server_host: config.session_host.clone(),
        server_port: config.session_port,
        validation_mode: ValidationMode::Disabled,
        ..Default::default()
    })?);

    let (request_events, _) = broadcast::channel(512);
    let state = AppState {
        engine,
        request_store: Arc::new(RwLock::new(HashMap::new())),
        request_seq: Arc::new(AtomicU64::new(1)),
        request_events,
        subscription_seq: Arc::new(AtomicU64::new(1)),
        config: config.clone(),
    };

    let runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()?;

    runtime.block_on(async move {
        let app = Router::new()
            .route("/health", get(health_handler))
            .route("/requests", post(submit_request_handler))
            .route("/requests/{request_id}", get(get_request_handler))
            .route(
                "/requests/{request_id}/result",
                get(get_request_result_handler),
            )
            .route("/ws/requests", get(request_events_ws_handler))
            .route("/ws/subscriptions", get(subscription_ws_handler))
            .layer(
                CorsLayer::new()
                    .allow_origin(Any)
                    .allow_methods(Any)
                    .allow_headers(Any),
            )
            .layer(TraceLayer::new_for_http())
            .with_state(state);

        let listener = TcpListener::bind(config.listen_addr).await?;
        println!(
            "xbbg-bridge listening on http://{} (Bloomberg target {}:{})",
            config.listen_addr, config.session_host, config.session_port
        );
        serve(listener, app).await?;
        Ok::<(), Box<dyn std::error::Error>>(())
    })?;
    Ok(())
}

async fn health_handler(State(state): State<AppState>) -> Json<BridgeHealth> {
    Json(BridgeHealth {
        ok: true,
        listen_addr: state.config.listen_addr.to_string(),
        session_host: state.config.session_host.clone(),
        session_port: state.config.session_port,
        pending_requests: state.request_store.read().await.len(),
    })
}

async fn submit_request_handler(
    State(state): State<AppState>,
    Json(payload): Json<RequestSubmission>,
) -> Result<(StatusCode, Json<RequestAccepted>), (StatusCode, Json<Value>)> {
    let request_id = payload
        .request_id
        .clone()
        .unwrap_or_else(|| format!("req_{}", state.request_seq.fetch_add(1, Ordering::Relaxed)));

    let submitted_at = now_iso();
    let record = RequestRecord {
        request_id: request_id.clone(),
        state: RequestState::Queued,
        submitted_at: submitted_at.clone(),
        started_at: None,
        completed_at: None,
        result: None,
        error: None,
    };

    state
        .request_store
        .write()
        .await
        .insert(request_id.clone(), record.clone());
    publish_request_event(&state, "request.accepted", &record);

    let engine = state.engine.clone();
    let request_store = state.request_store.clone();
    let request_events = state.request_events.clone();
    let request_id_for_task = request_id.clone();
    tokio::spawn(async move {
        update_request_state(
            &request_store,
            &request_id_for_task,
            RequestState::Running,
            Some(now_iso()),
            None,
            None,
            None,
            &request_events,
            "request.started",
        )
        .await;

        match RequestParams::try_from(payload) {
            Ok(params) => match engine.request(params).await {
                Ok(batch) => match record_batch_to_json(&batch) {
                    Ok(result) => {
                        update_request_state(
                            &request_store,
                            &request_id_for_task,
                            RequestState::Done,
                            None,
                            Some(now_iso()),
                            Some(result),
                            None,
                            &request_events,
                            "request.completed",
                        )
                        .await;
                    }
                    Err(error) => {
                        update_request_state(
                            &request_store,
                            &request_id_for_task,
                            RequestState::Failed,
                            None,
                            Some(now_iso()),
                            None,
                            Some(error),
                            &request_events,
                            "request.failed",
                        )
                        .await;
                    }
                },
                Err(error) => {
                    update_request_state(
                        &request_store,
                        &request_id_for_task,
                        RequestState::Failed,
                        None,
                        Some(now_iso()),
                        None,
                        Some(async_error_to_string(error)),
                        &request_events,
                        "request.failed",
                    )
                    .await;
                }
            },
            Err(error) => {
                update_request_state(
                    &request_store,
                    &request_id_for_task,
                    RequestState::Failed,
                    None,
                    Some(now_iso()),
                    None,
                    Some(error),
                    &request_events,
                    "request.failed",
                )
                .await;
            }
        }
    });

    Ok((
        StatusCode::ACCEPTED,
        Json(RequestAccepted {
            request_id,
            state: RequestState::Queued,
        }),
    ))
}

async fn get_request_handler(
    State(state): State<AppState>,
    Path(request_id): Path<String>,
) -> Result<Json<RequestRecord>, (StatusCode, Json<Value>)> {
    let store = state.request_store.read().await;
    match store.get(&request_id) {
        Some(record) => Ok(Json(record.clone())),
        None => Err(not_found(format!("unknown request id: {request_id}"))),
    }
}

async fn get_request_result_handler(
    State(state): State<AppState>,
    Path(request_id): Path<String>,
) -> Result<(StatusCode, Json<Value>), (StatusCode, Json<Value>)> {
    let store = state.request_store.read().await;
    let Some(record) = store.get(&request_id) else {
        return Err(not_found(format!("unknown request id: {request_id}")));
    };

    match record.state {
        RequestState::Done => Ok((
            StatusCode::OK,
            Json(json!({
                "requestId": record.request_id,
                "state": record.state,
                "result": record.result,
            })),
        )),
        RequestState::Failed => Ok((
            StatusCode::OK,
            Json(json!({
                "requestId": record.request_id,
                "state": record.state,
                "error": record.error,
            })),
        )),
        _ => Ok((
            StatusCode::ACCEPTED,
            Json(json!({
                "requestId": record.request_id,
                "state": record.state,
            })),
        )),
    }
}

async fn request_events_ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_request_events_socket(socket, state))
}

async fn handle_request_events_socket(mut socket: WebSocket, state: AppState) {
    let mut rx = state.request_events.subscribe();
    while let Ok(event) = rx.recv().await {
        let message = match serde_json::to_string(&event) {
            Ok(message) => message,
            Err(_) => continue,
        };
        if socket.send(Message::Text(message.into())).await.is_err() {
            break;
        }
    }
}

async fn subscription_ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_subscription_socket(socket, state))
}

async fn handle_subscription_socket(mut socket: WebSocket, state: AppState) {
    let initial_message = match socket.recv().await {
        Some(Ok(Message::Text(text))) => text,
        Some(Ok(Message::Binary(bytes))) => match String::from_utf8(bytes.to_vec()) {
            Ok(text) => text.into(),
            Err(_) => {
                let _ = send_subscription_message(
                    &mut socket,
                    &SubscriptionServerMessage::Error {
                        subscription_id: None,
                        message: "subscription socket expects JSON text".to_string(),
                    },
                )
                .await;
                return;
            }
        },
        _ => return,
    };

    let command: SubscriptionClientMessage = match serde_json::from_str(&initial_message) {
        Ok(command) => command,
        Err(error) => {
            let _ = send_subscription_message(
                &mut socket,
                &SubscriptionServerMessage::Error {
                    subscription_id: None,
                    message: format!("invalid subscription message: {error}"),
                },
            )
            .await;
            return;
        }
    };

    let SubscriptionClientMessage::Subscribe {
        subscription_id,
        service,
        topics,
        fields,
        options,
        stream_capacity,
        flush_threshold,
        overflow_policy,
    } = command
    else {
        let _ = send_subscription_message(
            &mut socket,
            &SubscriptionServerMessage::Error {
                subscription_id: None,
                message: "first websocket message must be type=subscribe".to_string(),
            },
        )
        .await;
        return;
    };

    let subscription_id = subscription_id.unwrap_or_else(|| {
        format!(
            "sub_{}",
            state.subscription_seq.fetch_add(1, Ordering::Relaxed)
        )
    });
    let service = service.unwrap_or_else(|| "//blp/mktdata".to_string());
    let options = options.unwrap_or_default();
    let overflow_policy = match overflow_policy {
        Some(policy) => match OverflowPolicy::from_str(&policy) {
            Ok(policy) => Some(policy),
            Err(error) => {
                let _ = send_subscription_message(
                    &mut socket,
                    &SubscriptionServerMessage::Error {
                        subscription_id: Some(subscription_id.clone()),
                        message: error,
                    },
                )
                .await;
                return;
            }
        },
        None => None,
    };

    let mut stream = match state
        .engine
        .subscribe_with_options(
            service.clone(),
            topics.clone(),
            fields.clone(),
            options,
            stream_capacity,
            flush_threshold,
            overflow_policy,
            None,
        )
        .await
    {
        Ok(stream) => stream,
        Err(error) => {
            let _ = send_subscription_message(
                &mut socket,
                &SubscriptionServerMessage::Error {
                    subscription_id: Some(subscription_id.clone()),
                    message: async_error_to_string(error),
                },
            )
            .await;
            return;
        }
    };

    if send_subscription_message(
        &mut socket,
        &SubscriptionServerMessage::Subscribed {
            subscription_id: subscription_id.clone(),
            service: service.clone(),
            topics,
            fields,
        },
    )
    .await
    .is_err()
    {
        let _ = stream.unsubscribe(false).await;
        return;
    }

    loop {
        tokio::select! {
            inbound = socket.recv() => {
                match inbound {
                    Some(Ok(Message::Text(text))) => {
                        match serde_json::from_str::<SubscriptionClientMessage>(&text) {
                            Ok(SubscriptionClientMessage::Ping) => {
                                let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Pong).await;
                            }
                            Ok(SubscriptionClientMessage::Unsubscribe) => {
                                let _ = stream.unsubscribe(false).await;
                                let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Unsubscribed { subscription_id: subscription_id.clone() }).await;
                                break;
                            }
                            Ok(SubscriptionClientMessage::Subscribe { .. }) => {
                                let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Error {
                                    subscription_id: Some(subscription_id.clone()),
                                    message: "this websocket currently supports one active subscription session; open another socket for another stream".to_string(),
                                }).await;
                            }
                            Err(error) => {
                                let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Error {
                                    subscription_id: Some(subscription_id.clone()),
                                    message: format!("invalid subscription command: {error}"),
                                }).await;
                            }
                        }
                    }
                    Some(Ok(Message::Ping(payload))) => {
                        let _ = socket.send(Message::Pong(payload)).await;
                    }
                    Some(Ok(Message::Close(_))) | None => {
                        let _ = stream.unsubscribe(false).await;
                        break;
                    }
                    Some(Err(_)) => {
                        let _ = stream.unsubscribe(false).await;
                        break;
                    }
                    _ => {}
                }
            }
            maybe_batch = stream.next() => {
                match maybe_batch {
                    Some(Ok(batch)) => {
                        match record_batch_to_json(&batch) {
                            Ok(rows) => {
                                if send_subscription_message(&mut socket, &SubscriptionServerMessage::Tick {
                                    subscription_id: subscription_id.clone(),
                                    rows,
                                }).await.is_err() {
                                    let _ = stream.unsubscribe(false).await;
                                    break;
                                }
                            }
                            Err(error) => {
                                let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Error {
                                    subscription_id: Some(subscription_id.clone()),
                                    message: error,
                                }).await;
                            }
                        }
                    }
                    Some(Err(error)) => {
                        let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Error {
                            subscription_id: Some(subscription_id.clone()),
                            message: core_error_to_string(error),
                        }).await;
                    }
                    None => {
                        let _ = send_subscription_message(&mut socket, &SubscriptionServerMessage::Unsubscribed {
                            subscription_id: subscription_id.clone(),
                        }).await;
                        break;
                    }
                }
            }
        }
    }
}

async fn send_subscription_message(
    socket: &mut WebSocket,
    message: &SubscriptionServerMessage,
) -> Result<(), axum::Error> {
    let payload = serde_json::to_string(message)
        .map_err(|error| axum::Error::new(std::io::Error::other(error)))?;
    socket.send(Message::Text(payload.into())).await
}

async fn update_request_state(
    store: &Arc<RwLock<HashMap<String, RequestRecord>>>,
    request_id: &str,
    state: RequestState,
    started_at: Option<String>,
    completed_at: Option<String>,
    result: Option<Value>,
    error: Option<String>,
    request_events: &broadcast::Sender<RequestEventEnvelope>,
    event_name: &str,
) {
    let mut guard = store.write().await;
    if let Some(record) = guard.get_mut(request_id) {
        record.state = state;
        if let Some(started_at) = started_at {
            record.started_at = Some(started_at);
        }
        if let Some(completed_at) = completed_at {
            record.completed_at = Some(completed_at);
        }
        if let Some(result) = result {
            record.result = Some(result);
        }
        if let Some(error) = error {
            record.error = Some(error);
        }
        let _ = request_events.send(RequestEventEnvelope {
            event: event_name.to_string(),
            request: record.clone(),
        });
    }
}

fn publish_request_event(state: &AppState, event_name: &str, record: &RequestRecord) {
    let _ = state.request_events.send(RequestEventEnvelope {
        event: event_name.to_string(),
        request: record.clone(),
    });
}

fn now_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true)
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

fn not_found(message: String) -> (StatusCode, Json<Value>) {
    (StatusCode::NOT_FOUND, Json(json!({ "error": message })))
}

fn record_batch_to_json(batch: &RecordBatch) -> Result<Value, String> {
    let mut buffer = Vec::new();
    let mut writer = ArrayWriter::new(&mut buffer);
    writer
        .write(batch)
        .map_err(|error| format!("failed to serialize Arrow batch to JSON: {error}"))?;
    writer
        .finish()
        .map_err(|error| format!("failed to finish Arrow JSON writer: {error}"))?;
    serde_json::from_slice(&buffer)
        .map_err(|error| format!("failed to decode Arrow JSON buffer: {error}"))
}

fn async_error_to_string(error: BlpAsyncError) -> String {
    error.to_string()
}

fn core_error_to_string(error: BlpError) -> String {
    error.to_string()
}
use chrono::{SecondsFormat, Utc};

//! Unified request worker for all Bloomberg request types.
//!
//! This worker handles all request/response patterns:
//! - Reference data (bdp)
//! - Historical data (bdh)
//! - Bulk data (bds)
//! - Intraday bars (bdib)
//! - Intraday ticks (bdtick)
//! - Field info queries
//!
//! Workers are pre-warmed with an active Bloomberg session and commonly
//! used services pre-opened for low-latency request handling.

use std::collections::HashMap;
use std::sync::Arc;
use std::thread::{self, JoinHandle};

use arrow::record_batch::RecordBatch;
use slab::Slab;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::schema::SerializedSchema;
use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, RequestBuilder, Service, SessionOptions};

use super::state::{
    BulkDataState, FieldInfoState, GenericState, HistDataState, HistDataStreamState,
    IntradayBarState, IntradayBarStreamState, IntradayTickState, IntradayTickStreamState, LongMode,
    OutputFormat, RawJsonState, RefDataState,
};
use super::{EngineConfig, ExtractorType, RequestParams};

/// Commands sent to a request worker.
pub enum WorkerCommand {
    /// Execute a request and send result via oneshot channel.
    Request {
        params: RequestParams,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Execute a streaming request and send batches via mpsc channel.
    RequestStream {
        params: RequestParams,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    },
    /// Introspect a service schema.
    SchemaIntrospect {
        service: String,
        reply: oneshot::Sender<Result<SerializedSchema, BlpError>>,
    },
    /// Shutdown the worker gracefully.
    Shutdown,
}

/// Unified request state combining all request types.
#[allow(clippy::large_enum_variant)]
pub enum UnifiedRequestState {
    // Bulk request types (from Lane B)
    RefData(RefDataState),
    HistData(HistDataState),
    BulkData(BulkDataState),
    HistDataStream(HistDataStreamState),
    Generic(GenericState),
    RawJson(RawJsonState),
    FieldInfo(FieldInfoState),
    // Intraday request types (from Lane C)
    IntradayBar(IntradayBarState),
    IntradayTick(IntradayTickState),
    IntradayBarStream(IntradayBarStreamState),
    IntradayTickStream(IntradayTickStreamState),
}

impl UnifiedRequestState {
    /// Process a PARTIAL_RESPONSE message (append to builders).
    pub fn on_partial(&mut self, msg: &xbbg_core::MessageRef) {
        match self {
            // Bulk types
            UnifiedRequestState::RefData(s) => s.on_partial(msg),
            UnifiedRequestState::HistData(s) => s.on_partial(msg),
            UnifiedRequestState::BulkData(s) => s.on_partial(msg),
            UnifiedRequestState::HistDataStream(s) => s.on_partial(msg),
            UnifiedRequestState::Generic(s) => s.on_partial(msg),
            UnifiedRequestState::RawJson(s) => s.on_partial(msg),
            UnifiedRequestState::FieldInfo(s) => s.on_partial(msg),
            // Intraday types
            UnifiedRequestState::IntradayBar(s) => s.on_partial(msg),
            UnifiedRequestState::IntradayTick(s) => s.on_partial(msg),
            UnifiedRequestState::IntradayBarStream(s) => s.on_partial(msg),
            UnifiedRequestState::IntradayTickStream(s) => s.on_partial(msg),
        }
    }

    /// Process the final RESPONSE message, build the result, and send reply.
    pub fn finish_and_reply(self, msg: &xbbg_core::MessageRef) {
        match self {
            // Bulk types
            UnifiedRequestState::RefData(s) => s.finish(msg),
            UnifiedRequestState::HistData(s) => s.finish(msg),
            UnifiedRequestState::BulkData(s) => s.finish(msg),
            UnifiedRequestState::HistDataStream(s) => s.finish(msg),
            UnifiedRequestState::Generic(s) => s.finish(msg),
            UnifiedRequestState::RawJson(s) => s.finish(msg),
            UnifiedRequestState::FieldInfo(s) => s.finish(msg),
            // Intraday types
            UnifiedRequestState::IntradayBar(s) => s.finish(msg),
            UnifiedRequestState::IntradayTick(s) => s.finish(msg),
            UnifiedRequestState::IntradayBarStream(s) => s.finish(msg),
            UnifiedRequestState::IntradayTickStream(s) => s.finish(msg),
        }
    }

    /// Handle a request failure/error.
    pub fn fail(self, error: BlpError) {
        match self {
            // Bulk types
            UnifiedRequestState::RefData(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::HistData(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::BulkData(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::HistDataStream(s) => s.fail(error),
            UnifiedRequestState::Generic(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::RawJson(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::FieldInfo(s) => {
                let _ = s.reply.send(Err(error));
            }
            // Intraday types
            UnifiedRequestState::IntradayBar(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::IntradayTick(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::IntradayBarStream(s) => s.fail(error),
            UnifiedRequestState::IntradayTickStream(s) => s.fail(error),
        }
    }
}

/// A pre-warmed request worker with a Bloomberg session.
struct RequestWorker {
    /// Worker ID for debugging/metrics.
    id: usize,
    /// The Bloomberg session (started, services pre-opened).
    session: Session,
    /// Slab for O(1) correlation dispatch.
    requests: Slab<UnifiedRequestState>,
    /// Command receiver for this worker.
    cmd_rx: mpsc::Receiver<WorkerCommand>,
    /// Cached services.
    services: HashMap<String, Service>,
    /// Configuration.
    config: Arc<EngineConfig>,
    /// Send times for round-trip measurement.
    send_times: HashMap<usize, std::time::Instant>,
}

impl RequestWorker {
    /// Create a new worker with a pre-warmed session.
    fn new(
        id: usize,
        config: Arc<EngineConfig>,
        cmd_rx: mpsc::Receiver<WorkerCommand>,
    ) -> Result<Self, BlpError> {
        let mut opts = SessionOptions::new()?;
        opts.set_server_host(&config.server_host)?;
        opts.set_server_port(config.server_port);
        opts.set_max_event_queue_size(config.max_event_queue_size);
        let _ = opts.set_bandwidth_save_mode_disabled(true);

        let session = Session::new(&opts)?;
        session.start()?;

        let mut worker = Self {
            id,
            session,
            requests: Slab::new(),
            cmd_rx,
            services: HashMap::new(),
            config,
            send_times: HashMap::new(),
        };

        // Pre-warm commonly used services
        worker.warmup()?;

        Ok(worker)
    }

    /// Pre-warm the session by opening commonly used services.
    fn warmup(&mut self) -> Result<(), BlpError> {
        // Clone service names to avoid borrow conflict with self.ensure_service()
        let services_to_warm: Vec<String> = self.config.warmup_services.clone();
        for service_name in &services_to_warm {
            if let Err(e) = self.ensure_service(service_name) {
                tracing::warn!(
                    worker_id = self.id,
                    service = %service_name,
                    error = %e,
                    "failed to pre-warm service"
                );
            }
        }
        tracing::info!(
            worker_id = self.id,
            services = ?self.services.keys().collect::<Vec<_>>(),
            "worker pre-warmed"
        );
        Ok(())
    }

    /// Main pump loop.
    fn run(&mut self) -> Result<(), BlpError> {
        tracing::info!(worker_id = self.id, "RequestWorker started");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(WorkerCommand::Shutdown) => {
                        tracing::info!(worker_id = self.id, "RequestWorker shutting down");
                        return Ok(());
                    }
                    Ok(WorkerCommand::Request { params, reply }) => {
                        if let Err(e) = self.send_request(params, reply) {
                            tracing::error!(worker_id = self.id, error = %e, "request error");
                        }
                    }
                    Ok(WorkerCommand::RequestStream { params, stream }) => {
                        if let Err(e) = self.send_request_stream(params, stream) {
                            tracing::error!(worker_id = self.id, error = %e, "stream request error");
                        }
                    }
                    Ok(WorkerCommand::SchemaIntrospect { service, reply }) => {
                        let result = self.introspect_schema(&service);
                        let _ = reply.send(result);
                    }
                    Err(mpsc::error::TryRecvError::Empty) => break,
                    Err(mpsc::error::TryRecvError::Disconnected) => {
                        tracing::info!(worker_id = self.id, "command channel closed");
                        return Ok(());
                    }
                }
            }

            // 2. Poll Bloomberg (short timeout for responsiveness)
            match self.session.next_event(Some(10)) {
                Ok(ev) => self.dispatch_event(ev),
                Err(_) => continue,
            }
        }
    }

    fn ensure_service(&mut self, name: &str) -> Result<(), BlpError> {
        if !self.services.contains_key(name) {
            self.session.open_service(name)?;
            let svc = self.session.get_service(name)?;

            // Cache schema on first service open (for validation)
            let cache = crate::schema_cache::global_schema_cache();
            if cache.get(name).is_none() {
                tracing::info!(
                    worker_id = self.id,
                    service = name,
                    "caching service schema"
                );
                let schema = SerializedSchema::from_service(&svc);
                if let Err(e) = cache.put(&schema) {
                    tracing::warn!(error = %e, "failed to cache schema");
                }
            }

            self.services.insert(name.to_string(), svc);
        }
        Ok(())
    }

    /// Introspect a service schema and return serialized form.
    fn introspect_schema(&mut self, service_name: &str) -> Result<SerializedSchema, BlpError> {
        self.ensure_service(service_name)?;
        let service = self.services.get(service_name).unwrap();
        tracing::info!(
            worker_id = self.id,
            service = service_name,
            "introspecting service schema"
        );
        Ok(SerializedSchema::from_service(service))
    }

    /// Unified request handler - routes to correct state based on extractor type.
    fn send_request(
        &mut self,
        params: RequestParams,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        let t0 = std::time::Instant::now();
        self.ensure_service(&params.service)?;
        tracing::debug!(
            worker_id = self.id,
            elapsed_us = t0.elapsed().as_micros(),
            "ensure_service"
        );

        // Create state based on extractor type
        let state = self.create_request_state(&params, reply)?;

        let key = self.requests.insert(state);
        let cid = CorrelationId::U64(key as u64);

        // Build request from params
        let service = self.services.get(&params.service).unwrap();
        let request = self.build_request_from_params(service, &params)?;

        let t_send = std::time::Instant::now();
        self.session.send_request(&request, None, Some(&cid))?;
        self.send_times.insert(key, t_send);

        tracing::debug!(
            worker_id = self.id,
            key = key,
            service = %params.service,
            operation = %params.operation,
            "request sent"
        );
        Ok(())
    }

    /// Create the appropriate request state based on extractor type.
    fn create_request_state(
        &self,
        params: &RequestParams,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<UnifiedRequestState, BlpError> {
        let fields = params.fields.clone().unwrap_or_default();
        let field_types = params.field_types.clone();

        let state = match params.extractor {
            ExtractorType::RefData => {
                let long_mode = params
                    .format
                    .as_deref()
                    .map(|s| match s {
                        "long_typed" | "typed" => LongMode::Typed,
                        "long_metadata" | "metadata" | "with_metadata" => LongMode::WithMetadata,
                        _ => LongMode::String,
                    })
                    .unwrap_or(LongMode::String);
                UnifiedRequestState::RefData(RefDataState::with_format(
                    fields,
                    OutputFormat::Long,
                    long_mode,
                    field_types,
                    reply,
                ))
            }
            ExtractorType::HistData => {
                UnifiedRequestState::HistData(HistDataState::with_types(fields, field_types, reply))
            }
            ExtractorType::BulkData => {
                let field = fields.first().cloned().unwrap_or_default();
                UnifiedRequestState::BulkData(BulkDataState::new(field, reply))
            }
            ExtractorType::Generic => UnifiedRequestState::Generic(GenericState::new(reply)),
            ExtractorType::RawJson => UnifiedRequestState::RawJson(RawJsonState::new(reply)),
            ExtractorType::FieldInfo => UnifiedRequestState::FieldInfo(FieldInfoState::new(reply)),
            ExtractorType::IntradayBar => {
                let ticker = params.security.clone().unwrap_or_default();
                let event_type = params
                    .event_type
                    .clone()
                    .unwrap_or_else(|| "TRADE".to_string());
                let interval = params.interval.unwrap_or(1);
                UnifiedRequestState::IntradayBar(IntradayBarState::new(
                    ticker, event_type, interval, reply,
                ))
            }
            ExtractorType::IntradayTick => {
                let ticker = params.security.clone().unwrap_or_default();
                UnifiedRequestState::IntradayTick(IntradayTickState::new(ticker, reply))
            }
        };

        Ok(state)
    }

    /// Unified streaming request handler.
    fn send_request_stream(
        &mut self,
        params: RequestParams,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service(&params.service)?;

        let fields = params.fields.clone().unwrap_or_default();
        let ticker = params.security.clone().unwrap_or_default();

        let state = match params.extractor {
            ExtractorType::HistData => {
                UnifiedRequestState::HistDataStream(HistDataStreamState::new(fields, stream))
            }
            ExtractorType::IntradayBar => {
                UnifiedRequestState::IntradayBarStream(IntradayBarStreamState::new(ticker, stream))
            }
            ExtractorType::IntradayTick => UnifiedRequestState::IntradayTickStream(
                IntradayTickStreamState::new(ticker, stream),
            ),
            _ => {
                return Err(BlpError::InvalidArgument {
                    detail: format!(
                        "Streaming not supported for extractor: {:?}",
                        params.extractor
                    ),
                });
            }
        };

        let key = self.requests.insert(state);
        let cid = CorrelationId::U64(key as u64);

        let service = self.services.get(&params.service).unwrap();
        let request = self.build_request_from_params(service, &params)?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(
            worker_id = self.id,
            key = key,
            service = %params.service,
            operation = %params.operation,
            "stream request sent"
        );
        Ok(())
    }

    /// Build a Bloomberg request from generic RequestParams.
    fn build_request_from_params(
        &self,
        service: &Service,
        params: &RequestParams,
    ) -> Result<xbbg_core::Request, BlpError> {
        let mut builder = RequestBuilder::new();

        // Set securities (multi or single)
        if let Some(ref securities) = params.securities {
            builder = builder.securities(securities.clone());
        }
        if let Some(ref security) = params.security {
            // For intraday requests, use single security method
            if matches!(
                params.extractor,
                ExtractorType::IntradayBar | ExtractorType::IntradayTick
            ) {
                builder = builder.security(security);
            } else {
                builder = builder.securities(vec![security.clone()]);
            }
        }

        // Set fields
        if let Some(ref fields) = params.fields {
            builder = builder.fields(fields.clone());
        }

        // Set date range (for historical)
        if let Some(ref start) = params.start_date {
            builder = builder.start_date(start);
        }
        if let Some(ref end) = params.end_date {
            builder = builder.end_date(end);
        }

        // Set datetime range (for intraday)
        if let Some(ref start) = params.start_datetime {
            builder = builder.start_datetime(start);
        }
        if let Some(ref end) = params.end_datetime {
            builder = builder.end_datetime(end);
        }

        // Set event type and interval (for intraday bars)
        if let Some(ref event_type) = params.event_type {
            builder = builder.event_type(event_type);
        }
        if let Some(interval) = params.interval {
            builder = builder.interval(interval);
        }

        // Set overrides (Bloomberg field override format)
        if let Some(ref overrides) = params.overrides {
            for (name, value) in overrides {
                builder = builder.r#override(name, value.clone());
            }
        }

        // Set generic elements (for BQL, bsrch, etc.)
        if let Some(ref elements) = params.elements {
            for (name, value) in elements {
                builder = builder.element(name, value.clone());
            }
        }

        // Set JSON elements (for complex nested structures like tasvc)
        if let Some(ref json) = params.json_elements {
            builder = builder.json_elements(json);
        }

        // Set apiflds parameters
        if let Some(ref search_spec) = params.search_spec {
            builder = builder.search_spec(search_spec);
        }
        if let Some(ref field_ids) = params.field_ids {
            builder = builder.field_ids(field_ids.clone());
        }

        builder.build(service, &params.operation)
    }

    fn dispatch_event(&mut self, ev: xbbg_core::Event) {
        let et = ev.event_type();

        // CRITICAL: iterate ALL messages, never break early
        for msg in ev.iter() {
            match et {
                EventType::PartialResponse => {
                    self.handle_partial_response(&msg);
                }
                EventType::Response => {
                    self.handle_response(&msg);
                }
                EventType::RequestStatus => {
                    self.handle_request_status(&msg);
                }
                EventType::SessionStatus => {
                    self.handle_session_status(&msg);
                }
                EventType::ServiceStatus => {
                    self.handle_service_status(&msg);
                }
                _ => {}
            }
        }
    }

    fn handle_partial_response(&mut self, msg: &xbbg_core::MessageRef) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                if let Some(state) = self.requests.get_mut(key as usize) {
                    state.on_partial(msg);
                    tracing::trace!(worker_id = self.id, key = key, "partial response");
                }
            }
        }
    }

    fn handle_response(&mut self, msg: &xbbg_core::MessageRef) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                if self.requests.contains(key as usize) {
                    // Log round-trip time
                    if let Some(t_send) = self.send_times.remove(&(key as usize)) {
                        let rtt_ms = t_send.elapsed().as_micros() as f64 / 1000.0;
                        tracing::info!(
                            worker_id = self.id,
                            rtt_ms = rtt_ms,
                            key = key,
                            "bloomberg_roundtrip"
                        );
                    }
                    let state = self.requests.remove(key as usize);
                    state.finish_and_reply(msg);
                    tracing::debug!(worker_id = self.id, key = key, "response completed");
                }
            }
        }
    }

    fn handle_request_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        let n = msg.num_correlation_ids();

        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                if msg_type == "RequestFailure" {
                    tracing::error!(worker_id = self.id, key = key, "request failed");
                    if self.requests.contains(key as usize) {
                        let state = self.requests.remove(key as usize);
                        state.fail(BlpError::Internal {
                            detail: "RequestFailure".into(),
                        });
                    }
                }
            }
        }
    }

    fn handle_session_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        match msg_type {
            "SessionStarted" => {
                tracing::info!(worker_id = self.id, "session started");
            }
            "SessionTerminated" | "SessionConnectionDown" => {
                tracing::error!(worker_id = self.id, "session terminated/down");
            }
            _ => {
                tracing::debug!(worker_id = self.id, msg_type = msg_type, "session status");
            }
        }
    }

    fn handle_service_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        tracing::debug!(worker_id = self.id, msg_type = msg_type, "service status");
    }
}

/// Handle to communicate with a running worker.
pub struct WorkerHandle {
    /// Worker ID.
    pub id: usize,
    /// Command channel to send requests.
    pub cmd_tx: mpsc::Sender<WorkerCommand>,
    /// Thread handle (for shutdown).
    thread: Option<JoinHandle<()>>,
}

impl WorkerHandle {
    /// Spawn a new worker on a dedicated thread.
    pub fn spawn(id: usize, config: Arc<EngineConfig>) -> Result<Self, BlpError> {
        let (cmd_tx, cmd_rx) = mpsc::channel(config.command_queue_size);

        let config_clone = config.clone();
        let thread = thread::Builder::new()
            .name(format!("xbbg-worker-{}", id))
            .spawn(move || match RequestWorker::new(id, config_clone, cmd_rx) {
                Ok(mut worker) => {
                    if let Err(e) = worker.run() {
                        tracing::error!(worker_id = id, error = %e, "worker error");
                    }
                }
                Err(e) => {
                    tracing::error!(worker_id = id, error = %e, "worker creation failed");
                }
            })
            .map_err(|e| BlpError::Internal {
                detail: format!("failed to spawn worker thread: {}", e),
            })?;

        Ok(Self {
            id,
            cmd_tx,
            thread: Some(thread),
        })
    }

    /// Send a shutdown command and wait for the thread to finish.
    pub fn shutdown(&mut self) {
        let _ = self.cmd_tx.try_send(WorkerCommand::Shutdown);
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

impl Drop for WorkerHandle {
    fn drop(&mut self) {
        self.shutdown();
    }
}

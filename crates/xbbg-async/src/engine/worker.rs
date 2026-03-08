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

use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, Service, SessionOptions};

use super::state::{
    BqlState, BsrchState, BulkDataState, FieldInfoState, GenericState, HistDataState,
    HistDataStreamState, IntradayBarState, IntradayBarStreamState, IntradayTickState,
    IntradayTickStreamState, LongMode, OutputFormat, RefDataState,
};
use super::{EngineConfig, ExtractorType, RequestParams};

fn iter_named_request_parameters(
    params: &RequestParams,
) -> impl Iterator<Item = (&str, &str)> + '_ {
    params
        .elements
        .iter()
        .flat_map(|pairs| pairs.iter())
        .chain(params.options.iter().flat_map(|pairs| pairs.iter()))
        .map(|(name, value)| (name.as_str(), value.as_str()))
}

fn apply_named_request_parameter(
    request: &mut xbbg_core::Request,
    name: &str,
    value: &str,
) -> Result<(), BlpError> {
    if name.contains('.') {
        if let Ok(int_val) = value.parse::<i32>() {
            request.set_nested_int(name, int_val)?;
        } else {
            request.set_nested_str(name, value)?;
        }
    } else if request.set_str(name, value).is_err() {
        request.append_str(name, value)?;
    }

    Ok(())
}

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
    /// Introspect a service's schema.
    IntrospectSchema {
        service: String,
        reply: oneshot::Sender<Result<crate::schema::ServiceSchema, BlpError>>,
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
    Bql(BqlState),
    Bsrch(BsrchState),
    FieldInfo(FieldInfoState),
    // Intraday request types (from Lane C)
    IntradayBar(IntradayBarState),
    IntradayTick(IntradayTickState),
    IntradayBarStream(IntradayBarStreamState),
    IntradayTickStream(IntradayTickStreamState),
}

impl UnifiedRequestState {
    /// Process a PARTIAL_RESPONSE message (append to builders).
    pub fn on_partial(&mut self, msg: &xbbg_core::Message) {
        match self {
            // Bulk types
            UnifiedRequestState::RefData(s) => s.on_partial(msg),
            UnifiedRequestState::HistData(s) => s.on_partial(msg),
            UnifiedRequestState::BulkData(s) => s.on_partial(msg),
            UnifiedRequestState::HistDataStream(s) => s.on_partial(msg),
            UnifiedRequestState::Generic(s) => s.on_partial(msg),
            UnifiedRequestState::Bql(s) => s.on_partial(msg),
            UnifiedRequestState::Bsrch(s) => s.on_partial(msg),
            UnifiedRequestState::FieldInfo(s) => s.on_partial(msg),
            // Intraday types
            UnifiedRequestState::IntradayBar(s) => s.on_partial(msg),
            UnifiedRequestState::IntradayTick(s) => s.on_partial(msg),
            UnifiedRequestState::IntradayBarStream(s) => s.on_partial(msg),
            UnifiedRequestState::IntradayTickStream(s) => s.on_partial(msg),
        }
    }

    /// Process the final RESPONSE message, build the result, and send reply.
    pub fn finish_and_reply(self, msg: &xbbg_core::Message) {
        match self {
            // Bulk types
            UnifiedRequestState::RefData(s) => s.finish(msg),
            UnifiedRequestState::HistData(s) => s.finish(msg),
            UnifiedRequestState::BulkData(s) => s.finish(msg),
            UnifiedRequestState::HistDataStream(s) => s.finish(msg),
            UnifiedRequestState::Generic(s) => s.finish(msg),
            UnifiedRequestState::Bql(s) => s.finish(msg),
            UnifiedRequestState::Bsrch(s) => s.finish(msg),
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
            UnifiedRequestState::Bql(s) => {
                let _ = s.reply.send(Err(error));
            }
            UnifiedRequestState::Bsrch(s) => {
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

/// Threshold for warning about slow Bloomberg responses (30 seconds).
const SLOW_REQUEST_WARN_THRESHOLD: std::time::Duration = std::time::Duration::from_secs(30);

/// How often to check for slow requests (every 1000 poll iterations ≈ 10 seconds).
const SLOW_REQUEST_CHECK_INTERVAL: u32 = 1000;

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
    /// Track which requests we've already warned about (to avoid log spam).
    warned_requests: std::collections::HashSet<usize>,
    /// Counter for slow request check interval.
    poll_counter: u32,
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
            warned_requests: std::collections::HashSet::new(),
            poll_counter: 0,
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
                xbbg_log::warn!(
                    worker_id = self.id,
                    service = %service_name,
                    error = %e,
                    "failed to pre-warm service"
                );
            }
        }
        xbbg_log::info!(
            worker_id = self.id,
            services = ?self.services.keys().collect::<Vec<_>>(),
            "worker pre-warmed"
        );
        Ok(())
    }

    /// Main pump loop.
    fn run(&mut self) -> Result<(), BlpError> {
        xbbg_log::info!(worker_id = self.id, "RequestWorker started");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(WorkerCommand::Shutdown) => {
                        xbbg_log::info!(worker_id = self.id, "RequestWorker shutting down");
                        return Ok(());
                    }
                    Ok(WorkerCommand::Request { params, reply }) => {
                        if let Err(e) = self.send_request(params, reply) {
                            xbbg_log::error!(worker_id = self.id, error = %e, "request error");
                        }
                    }
                    Ok(WorkerCommand::RequestStream { params, stream }) => {
                        if let Err(e) = self.send_request_stream(params, stream) {
                            xbbg_log::error!(worker_id = self.id, error = %e, "stream request error");
                        }
                    }
                    Ok(WorkerCommand::IntrospectSchema { service, reply }) => {
                        let result = self.introspect_schema(&service);
                        let _ = reply.send(result);
                    }
                    Err(mpsc::error::TryRecvError::Empty) => break,
                    Err(mpsc::error::TryRecvError::Disconnected) => {
                        xbbg_log::info!(worker_id = self.id, "command channel closed");
                        return Ok(());
                    }
                }
            }

            // 2. Poll Bloomberg (short timeout for responsiveness)
            if let Ok(ev) = self.session.next_event(Some(10)) {
                self.dispatch_event(ev);
            }

            // 3. Periodically check for slow requests and warn
            self.poll_counter += 1;
            if self.poll_counter >= SLOW_REQUEST_CHECK_INTERVAL {
                self.poll_counter = 0;
                self.check_slow_requests();
            }
        }
    }

    /// Check for requests that have been waiting too long and emit warnings.
    fn check_slow_requests(&mut self) {
        let now = std::time::Instant::now();
        for (&key, &send_time) in &self.send_times {
            let elapsed = now.duration_since(send_time);
            if elapsed > SLOW_REQUEST_WARN_THRESHOLD && !self.warned_requests.contains(&key) {
                xbbg_log::warn!(
                    worker_id = self.id,
                    request_key = key,
                    elapsed_secs = elapsed.as_secs(),
                    "request waiting for Bloomberg response longer than expected"
                );
                self.warned_requests.insert(key);
            }
        }
    }

    fn ensure_service(&mut self, name: &str) -> Result<(), BlpError> {
        if !self.services.contains_key(name) {
            self.session.open_service(name)?;
            let svc = self.session.get_service(name)?;
            self.services.insert(name.to_string(), svc);
        }
        Ok(())
    }

    /// Introspect a service's schema.
    fn introspect_schema(
        &mut self,
        service_uri: &str,
    ) -> Result<crate::schema::ServiceSchema, BlpError> {
        xbbg_log::debug!(worker_id = self.id, service = %service_uri, "introspecting schema");

        self.ensure_service(service_uri)?;

        let service = self
            .services
            .get(service_uri)
            .ok_or_else(|| BlpError::Internal {
                detail: format!("Service {} not found after ensure_service", service_uri),
            })?;

        let schema = crate::schema::introspect_service(service, service_uri);

        xbbg_log::debug!(
            worker_id = self.id,
            service = %service_uri,
            operations = schema.operations.len(),
            "schema introspection complete"
        );

        Ok(schema)
    }

    /// Unified request handler - routes to correct state based on extractor type.
    fn send_request(
        &mut self,
        params: RequestParams,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        let t0 = std::time::Instant::now();
        self.ensure_service(&params.service)?;
        xbbg_log::debug!(
            worker_id = self.id,
            elapsed_us = t0.elapsed().as_micros(),
            "ensure_service"
        );

        // Create state based on extractor type
        xbbg_log::debug!(
            worker_id = self.id,
            extractor = ?params.extractor,
            fields = ?params.fields,
            "creating request state"
        );
        let state = self.create_request_state(&params, reply)?;
        xbbg_log::debug!(worker_id = self.id, "request state created");

        let key = self.requests.insert(state);
        let cid = CorrelationId::Int(key as i64);

        // Build request from params
        let service = self
            .services
            .get(&params.service)
            .ok_or_else(|| BlpError::Internal {
                detail: format!(
                    "service '{}' missing from worker cache after ensure_service",
                    params.service
                ),
            })?;
        xbbg_log::debug!(
            worker_id = self.id,
            operation = %params.effective_operation(),
            securities = ?params.securities,
            start_date = ?params.start_date,
            end_date = ?params.end_date,
            "building request"
        );
        let request = self.build_request_from_params(service, &params)?;
        xbbg_log::debug!(worker_id = self.id, "request built");

        let t_send = std::time::Instant::now();
        self.session.send_request(&request, None, Some(&cid))?;
        self.send_times.insert(key, t_send);

        xbbg_log::debug!(
            worker_id = self.id,
            key = key,
            service = %params.service,
            operation = %params.effective_operation(),
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
                    params.include_security_errors,
                    reply,
                ))
            }
            ExtractorType::HistData => {
                // Parse format parameter for long/wide mode
                let (output_format, long_mode) = params
                    .format
                    .as_deref()
                    .map(|s| match s {
                        "wide" => (OutputFormat::Wide, LongMode::String),
                        "long_typed" | "typed" => (OutputFormat::Long, LongMode::Typed),
                        "long_metadata" | "metadata" | "with_metadata" => {
                            (OutputFormat::Long, LongMode::WithMetadata)
                        }
                        _ => (OutputFormat::Long, LongMode::String),
                    })
                    .unwrap_or((OutputFormat::Long, LongMode::String));
                UnifiedRequestState::HistData(HistDataState::with_format(
                    fields,
                    output_format,
                    long_mode,
                    field_types,
                    reply,
                ))
            }
            ExtractorType::BulkData => {
                let field = fields.first().cloned().unwrap_or_default();
                UnifiedRequestState::BulkData(BulkDataState::new(field, reply))
            }
            ExtractorType::Generic => UnifiedRequestState::Generic(GenericState::new(reply)),
            ExtractorType::Bql => UnifiedRequestState::Bql(BqlState::new(reply)),
            ExtractorType::Bsrch => UnifiedRequestState::Bsrch(BsrchState::new(reply)),
            ExtractorType::FieldInfo => UnifiedRequestState::FieldInfo(FieldInfoState::new(reply)),
            ExtractorType::IntradayBar => {
                // If user specified extra elements, use GENERIC extractor
                if params.elements.as_ref().is_some_and(|e| !e.is_empty()) {
                    UnifiedRequestState::Generic(GenericState::new(reply))
                } else {
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
            }
            ExtractorType::IntradayTick => {
                // If user specified extra elements (e.g., includeConditionCodes=true),
                // use GENERIC extractor for dynamic column discovery
                if params.elements.as_ref().is_some_and(|e| !e.is_empty()) {
                    UnifiedRequestState::Generic(GenericState::new(reply))
                } else {
                    let ticker = params.security.clone().unwrap_or_default();
                    UnifiedRequestState::IntradayTick(IntradayTickState::new(ticker, reply))
                }
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
        let cid = CorrelationId::Int(key as i64);

        let service = self
            .services
            .get(&params.service)
            .ok_or_else(|| BlpError::Internal {
                detail: format!(
                    "service '{}' missing from worker cache after ensure_service",
                    params.service
                ),
            })?;
        let request = self.build_request_from_params(service, &params)?;

        self.session.send_request(&request, None, Some(&cid))?;
        xbbg_log::debug!(
            worker_id = self.id,
            key = key,
            service = %params.service,
            operation = %params.effective_operation(),
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
        let operation = params.effective_operation();
        xbbg_log::trace!(operation = %operation, "creating request");
        let mut request = service.create_request(operation)?;
        xbbg_log::trace!("request created");

        // Set securities (multi or single)
        if let Some(ref securities) = params.securities {
            for sec in securities {
                xbbg_log::trace!(element = "securities", value = %sec, "appending");
                request.append_str("securities", sec)?;
            }
        }
        if let Some(ref security) = params.security {
            // For intraday requests, "security" is a scalar element (use set_str)
            // For other requests, add to "securities" array (use append_str)
            if matches!(
                params.extractor,
                ExtractorType::IntradayBar | ExtractorType::IntradayTick
            ) {
                xbbg_log::trace!(element = "security", value = %security, "setting scalar");
                request.set_str("security", security)?;
            } else {
                xbbg_log::trace!(element = "securities", value = %security, "appending");
                request.append_str("securities", security)?;
            }
        }

        // Set fields
        if let Some(ref fields) = params.fields {
            for field in fields {
                xbbg_log::trace!(element = "fields", value = %field, "appending");
                request.append_str("fields", field)?;
            }
        }

        // Set date range (for historical) - scalar elements use set_str
        if let Some(ref start) = params.start_date {
            xbbg_log::trace!(element = "startDate", value = %start, "setting");
            request.set_str("startDate", start)?;
        }
        if let Some(ref end) = params.end_date {
            xbbg_log::trace!(element = "endDate", value = %end, "setting");
            request.set_str("endDate", end)?;
        }

        // Set datetime range (for intraday) - use proper datetime type
        if let Some(ref start) = params.start_datetime {
            xbbg_log::trace!(element = "startDateTime", value = %start, "setting datetime");
            request.set_datetime("startDateTime", start)?;
        }
        if let Some(ref end) = params.end_datetime {
            xbbg_log::trace!(element = "endDateTime", value = %end, "setting datetime");
            request.set_datetime("endDateTime", end)?;
        }

        // Set event type (singular, for intraday bars)
        if let Some(ref event_type) = params.event_type {
            request.set_str("eventType", event_type)?;
        }
        // Set event types (array, for intraday ticks)
        if let Some(ref event_types) = params.event_types {
            for et in event_types {
                xbbg_log::trace!(element = "eventTypes", value = %et, "appending event type");
                request.append_str("eventTypes", et)?;
            }
        }
        // Set interval (for intraday bars)
        if let Some(interval) = params.interval {
            request.set_int("interval", interval as i32)?;
        }

        // Apply generic request parameters from both `elements` and request-level `options`.
        // - Dotted paths (e.g., "priceSource.securityName") use nested setters
        // - Non-dotted names try scalar set first, fall back to append for arrays
        for (name, value) in iter_named_request_parameters(params) {
            apply_named_request_parameter(&mut request, name, value)?;
        }

        // Set apiflds field IDs
        if let Some(ref field_ids) = params.field_ids {
            for id in field_ids {
                request.append_str("id", id)?;
            }
        }

        // Set overrides (fieldId/value pairs on the "overrides" sequence element)
        if let Some(ref overrides) = params.overrides {
            if !overrides.is_empty() {
                let overrides_ptr = request.get_or_create_element("overrides")?;
                for (field_id, value) in overrides {
                    // SAFETY: overrides_ptr is a valid element obtained from
                    // get_or_create_element above; entry_ptr is valid from append_element.
                    let entry_ptr = unsafe { request.append_element(overrides_ptr)? };
                    unsafe { request.set_element_string(entry_ptr, "fieldId", field_id)? };
                    unsafe { request.set_element_string(entry_ptr, "value", value)? };
                }
                xbbg_log::debug!(
                    worker_id = self.id,
                    count = overrides.len(),
                    "overrides applied"
                );
            }
        }

        // Set search spec (for FieldSearchRequest)
        if let Some(ref search_spec) = params.search_spec {
            request.set_str("searchSpec", search_spec)?;
        }

        Ok(request)
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

    fn handle_partial_response(&mut self, msg: &xbbg_core::Message<'_>) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::Int(key)) = msg.correlation_id(i) {
                if let Some(state) = self.requests.get_mut(key as usize) {
                    state.on_partial(msg);
                    xbbg_log::trace!(worker_id = self.id, key = key, "partial response");
                }
            }
        }
    }

    fn handle_response(&mut self, msg: &xbbg_core::Message<'_>) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::Int(key)) = msg.correlation_id(i) {
                if self.requests.contains(key as usize) {
                    // Log round-trip time and clean up tracking
                    if let Some(t_send) = self.send_times.remove(&(key as usize)) {
                        let rtt_ms = t_send.elapsed().as_micros() as f64 / 1000.0;
                        xbbg_log::info!(
                            worker_id = self.id,
                            rtt_ms = rtt_ms,
                            key = key,
                            "bloomberg_roundtrip"
                        );
                    }
                    self.warned_requests.remove(&(key as usize));
                    let state = self.requests.remove(key as usize);
                    state.finish_and_reply(msg);
                    xbbg_log::debug!(worker_id = self.id, key = key, "response completed");
                }
            }
        }
    }

    fn handle_request_status(&mut self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        let n = msg.num_correlation_ids();

        for i in 0..n {
            if let Some(CorrelationId::Int(key)) = msg.correlation_id(i) {
                if msg_type == "RequestFailure" {
                    xbbg_log::error!(worker_id = self.id, key = key, "request failed");
                    if self.requests.contains(key as usize) {
                        // Clean up tracking
                        self.send_times.remove(&(key as usize));
                        self.warned_requests.remove(&(key as usize));
                        let state = self.requests.remove(key as usize);
                        state.fail(BlpError::Internal {
                            detail: "RequestFailure".into(),
                        });
                    }
                }
            }
        }
    }

    fn handle_session_status(&mut self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        match msg_type {
            "SessionStarted" => {
                xbbg_log::info!(worker_id = self.id, "session started");
            }
            "SessionTerminated" | "SessionConnectionDown" => {
                let in_flight = self.requests.len();
                xbbg_log::error!(
                    worker_id = self.id,
                    in_flight_requests = in_flight,
                    "session terminated/down"
                );
                if in_flight > 0 {
                    xbbg_log::warn!(
                        worker_id = self.id,
                        count = in_flight,
                        "in-flight requests will not receive Bloomberg responses"
                    );
                }
            }
            _ => {
                xbbg_log::debug!(worker_id = self.id, msg_type = msg_type, "session status");
            }
        }
    }

    fn handle_service_status(&mut self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        xbbg_log::debug!(worker_id = self.id, msg_type = msg_type, "service status");
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
                        xbbg_log::error!(worker_id = id, error = %e, "worker error");
                    }
                }
                Err(e) => {
                    xbbg_log::error!(worker_id = id, error = %e, "worker creation failed");
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

    /// Signal shutdown without waiting (non-blocking).
    ///
    /// Used by Drop to avoid blocking during interpreter shutdown.
    pub fn signal_shutdown(&self) {
        let _ = self.cmd_tx.try_send(WorkerCommand::Shutdown);
    }

    /// Send a shutdown command and wait for the thread to finish (blocking).
    ///
    /// Use this for clean shutdown when you can afford to wait.
    /// GIL should be released before calling this from Python.
    pub fn shutdown_blocking(&mut self) {
        self.signal_shutdown();
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

impl Drop for WorkerHandle {
    fn drop(&mut self) {
        // Non-blocking: just signal, don't wait
        // Thread will terminate when it sees Shutdown or when process exits
        self.signal_shutdown();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::RequestParams;

    #[test]
    fn iter_named_request_parameters_includes_options_after_elements() {
        let params = RequestParams {
            elements: Some(vec![(
                "periodicitySelection".to_string(),
                "DAILY".to_string(),
            )]),
            options: Some(vec![
                ("adjustmentSplit".to_string(), "true".to_string()),
                ("adjustmentNormal".to_string(), "true".to_string()),
            ]),
            ..Default::default()
        };

        let collected: Vec<(&str, &str)> = iter_named_request_parameters(&params).collect();

        assert_eq!(
            collected,
            vec![
                ("periodicitySelection", "DAILY"),
                ("adjustmentSplit", "true"),
                ("adjustmentNormal", "true"),
            ]
        );
    }
}

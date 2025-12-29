//! Lane B: Slow session pump for bulk requests (bdp/bdh/bds).
//!
//! This pump handles:
//! - PARTIAL_RESPONSE (streaming chunks)
//! - RESPONSE (final chunk)
//! - REQUEST_STATUS (errors)
//! - SESSION_STATUS / SERVICE_STATUS (admin)

use std::collections::HashMap;

use slab::Slab;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, RequestBuilder, Service, SessionOptions};

use super::state::{
    BulkDataState, HistDataState, HistDataStreamState, OutputFormat, RefDataState, RequestState,
};
use super::{Command, EngineConfig, ExtractorType, RequestParams};

/// Lane B pump state.
struct PumpB {
    session: Session,
    requests: Slab<RequestState>,
    cmd_rx: mpsc::Receiver<Command>,
    #[allow(dead_code)]
    config: EngineConfig,
    /// Cached services
    services: HashMap<String, Service>,
}

impl PumpB {
    fn new(config: EngineConfig, cmd_rx: mpsc::Receiver<Command>) -> Result<Self, BlpError> {
        let mut opts = SessionOptions::new()?;
        opts.set_server_host(&config.server_host)?;
        opts.set_server_port(config.server_port);

        // Apply performance tuning options
        opts.set_max_event_queue_size(config.max_event_queue_size);
        // Disable bandwidth save mode for lower latency (only if available)
        let _ = opts.set_bandwidth_save_mode_disabled(true);

        let session = Session::new(&opts)?;
        session.start()?;

        Ok(Self {
            session,
            requests: Slab::new(),
            cmd_rx,
            config,
            services: HashMap::new(),
        })
    }

    fn run(&mut self) -> Result<(), BlpError> {
        tracing::info!("PumpB started (Lane B: bulk requests)");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(Command::Shutdown) => {
                        tracing::info!("PumpB shutting down");
                        return Ok(());
                    }
                    Ok(cmd) => {
                        if let Err(e) = self.handle_command(cmd) {
                            tracing::error!(error = %e, "PumpB command error");
                        }
                    }
                    Err(mpsc::error::TryRecvError::Empty) => break,
                    Err(mpsc::error::TryRecvError::Disconnected) => {
                        tracing::info!("PumpB command channel closed");
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

    fn handle_command(&mut self, cmd: Command) -> Result<(), BlpError> {
        match cmd {
            Command::Request { params, reply } => {
                self.send_request(params, reply)?;
            }
            Command::RequestStream { params, stream } => {
                self.send_request_stream(params, stream)?;
            }
            _ => {
                // Lane A/C commands shouldn't arrive here
                tracing::warn!("PumpB received Lane A/C command");
            }
        }
        Ok(())
    }

    fn ensure_service(&mut self, name: &str) -> Result<(), BlpError> {
        if !self.services.contains_key(name) {
            self.session.open_service(name)?;
            let svc = self.session.get_service(name)?;
            self.services.insert(name.to_string(), svc);
        }
        Ok(())
    }

    /// Unified request handler - routes to correct state based on extractor type.
    fn send_request(
        &mut self,
        params: RequestParams,
        reply: oneshot::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service(&params.service)?;

        // Create state based on extractor type
        let fields = params.fields.clone().unwrap_or_default();
        let field_types = params.field_types.clone();
        let state = match params.extractor {
            ExtractorType::RefData => {
                RequestState::RefData(RefDataState::with_format(
                    fields.clone(),
                    OutputFormat::Long,
                    field_types,
                    reply,
                ))
            }
            ExtractorType::HistData => {
                RequestState::HistData(HistDataState::with_types(
                    fields.clone(),
                    field_types.clone(),
                    reply,
                ))
            }
            ExtractorType::BulkData => {
                let field = fields.first().cloned().unwrap_or_default();
                RequestState::BulkData(BulkDataState::new(field, reply))
            }
            _ => {
                // TODO: Add Generic and RawJson extractors
                return Err(BlpError::InvalidArgument {
                    detail: format!("Unsupported extractor type for Lane B: {:?}", params.extractor),
                });
            }
        };

        let key = self.requests.insert(state);
        let cid = CorrelationId::U64(key as u64);

        // Build request from params
        let service = self.services.get(&params.service).unwrap();
        let request = self.build_request_from_params(service, &params)?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(
            key = key,
            service = %params.service,
            operation = %params.operation,
            "request sent"
        );
        Ok(())
    }

    /// Unified streaming request handler.
    fn send_request_stream(
        &mut self,
        params: RequestParams,
        stream: mpsc::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service(&params.service)?;

        // Create streaming state based on extractor type
        let fields = params.fields.clone().unwrap_or_default();
        let state = match params.extractor {
            ExtractorType::HistData => {
                RequestState::HistDataStream(HistDataStreamState::new(fields.clone(), stream))
            }
            _ => {
                return Err(BlpError::InvalidArgument {
                    detail: format!("Streaming not supported for extractor: {:?}", params.extractor),
                });
            }
        };

        let key = self.requests.insert(state);
        let cid = CorrelationId::U64(key as u64);

        // Build request from params
        let service = self.services.get(&params.service).unwrap();
        let request = self.build_request_from_params(service, &params)?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(
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
            builder = builder.securities(vec![security.clone()]);
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

        // Set overrides
        if let Some(ref overrides) = params.overrides {
            for (name, value) in overrides {
                builder = builder.r#override(name, value.clone());
            }
        }

        // Build with the operation name
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
        // Multi-correlator aware
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                if let Some(state) = self.requests.get_mut(key as usize) {
                    state.on_partial(msg);
                    tracing::trace!(key = key, "partial response processed");
                }
            }
        }
    }

    fn handle_response(&mut self, msg: &xbbg_core::MessageRef) {
        // Multi-correlator aware
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                if self.requests.contains(key as usize) {
                    let state = self.requests.remove(key as usize);
                    state.finish_and_reply(msg);
                    tracing::debug!(key = key, "response completed");
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
                    tracing::error!(key = key, "request failed");
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
                tracing::info!("PumpB: session started");
            }
            "SessionTerminated" | "SessionConnectionDown" => {
                tracing::error!("PumpB: session terminated/down");
            }
            _ => {
                tracing::debug!(msg_type = msg_type, "PumpB: session status");
            }
        }
    }

    fn handle_service_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        tracing::debug!(msg_type = msg_type, "PumpB: service status");
    }
}

/// Run the Lane B pump thread.
pub fn run(config: EngineConfig, cmd_rx: mpsc::Receiver<Command>) -> Result<(), BlpError> {
    let mut pump = PumpB::new(config, cmd_rx)?;
    pump.run()
}

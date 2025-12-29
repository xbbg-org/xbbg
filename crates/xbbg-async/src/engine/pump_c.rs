//! Lane C: Slow session pump for intraday bar/tick requests.
//!
//! This pump handles:
//! - PARTIAL_RESPONSE (streaming chunks)
//! - RESPONSE (final chunk)
//! - REQUEST_STATUS (errors)
//! - SESSION_STATUS / SERVICE_STATUS (admin)
//!
//! Lane C is separate from Lane B to prevent large intraday requests
//! from starving smaller bdp/bdh/bds requests.

use std::collections::HashMap;

use slab::Slab;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, RequestBuilder, Service, SessionOptions};

use super::state::{
    IntradayBarState, IntradayBarStreamState, IntradayRequestState, IntradayTickState,
    IntradayTickStreamState,
};
use super::{Command, EngineConfig, ExtractorType, RequestParams};

/// Lane C pump state.
struct PumpC {
    session: Session,
    requests: Slab<IntradayRequestState>,
    cmd_rx: mpsc::Receiver<Command>,
    #[allow(dead_code)]
    config: EngineConfig,
    /// Cached services
    services: HashMap<String, Service>,
}

impl PumpC {
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
        tracing::info!("PumpC started (Lane C: intraday requests)");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(Command::Shutdown) => {
                        tracing::info!("PumpC shutting down");
                        return Ok(());
                    }
                    Ok(cmd) => {
                        if let Err(e) = self.handle_command(cmd) {
                            tracing::error!(error = %e, "PumpC command error");
                        }
                    }
                    Err(mpsc::error::TryRecvError::Empty) => break,
                    Err(mpsc::error::TryRecvError::Disconnected) => {
                        tracing::info!("PumpC command channel closed");
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
                // Lane A/B commands shouldn't arrive here
                tracing::warn!("PumpC received Lane A/B command");
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

        // Get ticker from security field
        let ticker = params.security.clone().unwrap_or_default();
        let event_type = params
            .event_type
            .clone()
            .unwrap_or_else(|| "TRADE".to_string());
        let interval = params.interval.unwrap_or(1);

        // Create state based on extractor type
        let state = match params.extractor {
            ExtractorType::IntradayBar => IntradayRequestState::Bar(IntradayBarState::new(
                ticker.clone(),
                event_type.clone(),
                interval,
                reply,
            )),
            ExtractorType::IntradayTick => {
                IntradayRequestState::Tick(IntradayTickState::new(ticker.clone(), reply))
            }
            _ => {
                return Err(BlpError::InvalidArgument {
                    detail: format!(
                        "Unsupported extractor type for Lane C: {:?}",
                        params.extractor
                    ),
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
            ticker = %ticker,
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

        // Get ticker from security field
        let ticker = params.security.clone().unwrap_or_default();

        // Create streaming state based on extractor type
        let state = match params.extractor {
            ExtractorType::IntradayBar => {
                IntradayRequestState::BarStream(IntradayBarStreamState::new(ticker.clone(), stream))
            }
            ExtractorType::IntradayTick => IntradayRequestState::TickStream(
                IntradayTickStreamState::new(ticker.clone(), stream),
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

        // Build request from params
        let service = self.services.get(&params.service).unwrap();
        let request = self.build_request_from_params(service, &params)?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(
            key = key,
            service = %params.service,
            operation = %params.operation,
            ticker = %ticker,
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

        // Set security (single for intraday)
        if let Some(ref security) = params.security {
            builder = builder.security(security);
        }

        // Set datetime range
        if let Some(ref start) = params.start_datetime {
            builder = builder.start_datetime(start);
        }
        if let Some(ref end) = params.end_datetime {
            builder = builder.end_datetime(end);
        }

        // Set event type and interval (for bars)
        if let Some(ref event_type) = params.event_type {
            builder = builder.event_type(event_type);
        }
        if let Some(interval) = params.interval {
            builder = builder.interval(interval);
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
                tracing::info!("PumpC: session started");
            }
            "SessionTerminated" | "SessionConnectionDown" => {
                tracing::error!("PumpC: session terminated/down");
            }
            _ => {
                tracing::debug!(msg_type = msg_type, "PumpC: session status");
            }
        }
    }

    fn handle_service_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        tracing::debug!(msg_type = msg_type, "PumpC: service status");
    }
}

/// Run the Lane C pump thread.
pub fn run(config: EngineConfig, cmd_rx: mpsc::Receiver<Command>) -> Result<(), BlpError> {
    let mut pump = PumpC::new(config, cmd_rx)?;
    pump.run()
}

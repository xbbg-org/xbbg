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
use super::{Command, EngineConfig};

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
            Command::Bdib {
                ticker,
                event_type,
                interval,
                start_datetime,
                end_datetime,
                reply,
            } => {
                self.send_bdib(
                    ticker,
                    event_type,
                    interval,
                    start_datetime,
                    end_datetime,
                    reply,
                )?;
            }
            Command::Bdtick {
                ticker,
                start_datetime,
                end_datetime,
                reply,
            } => {
                self.send_bdtick(ticker, start_datetime, end_datetime, reply)?;
            }
            Command::BdibStream {
                ticker,
                event_type,
                interval,
                start_datetime,
                end_datetime,
                stream,
            } => {
                self.send_bdib_stream(
                    ticker,
                    event_type,
                    interval,
                    start_datetime,
                    end_datetime,
                    stream,
                )?;
            }
            Command::BdtickStream {
                ticker,
                start_datetime,
                end_datetime,
                stream,
            } => {
                self.send_bdtick_stream(ticker, start_datetime, end_datetime, stream)?;
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

    fn send_bdib(
        &mut self,
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
        reply: oneshot::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate state
        let state = IntradayBarState::new(ticker.clone(), event_type.clone(), interval, reply);
        let key = self.requests.insert(IntradayRequestState::Bar(state));
        let cid = CorrelationId::U64(key as u64);

        // Build request
        let service = self.services.get("//blp/refdata").unwrap();
        let request = RequestBuilder::new()
            .security(&ticker)
            .event_type(&event_type)
            .interval(interval)
            .start_datetime(&start_datetime)
            .end_datetime(&end_datetime)
            .build(service, "IntradayBarRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, ticker = %ticker, event_type = %event_type, interval = interval, "bdib request sent");
        Ok(())
    }

    fn send_bdtick(
        &mut self,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
        reply: oneshot::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate state
        let state = IntradayTickState::new(ticker.clone(), reply);
        let key = self.requests.insert(IntradayRequestState::Tick(state));
        let cid = CorrelationId::U64(key as u64);

        // Build request
        let service = self.services.get("//blp/refdata").unwrap();
        let request = RequestBuilder::new()
            .security(&ticker)
            .start_datetime(&start_datetime)
            .end_datetime(&end_datetime)
            .build(service, "IntradayTickRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, ticker = %ticker, "bdtick request sent");
        Ok(())
    }

    fn send_bdib_stream(
        &mut self,
        ticker: String,
        event_type: String,
        interval: u32,
        start_datetime: String,
        end_datetime: String,
        stream: tokio::sync::mpsc::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate streaming state
        let state = IntradayBarStreamState::new(ticker.clone(), stream);
        let key = self.requests.insert(IntradayRequestState::BarStream(state));
        let cid = CorrelationId::U64(key as u64);

        // Build request
        let service = self.services.get("//blp/refdata").unwrap();
        let request = RequestBuilder::new()
            .security(&ticker)
            .event_type(&event_type)
            .interval(interval)
            .start_datetime(&start_datetime)
            .end_datetime(&end_datetime)
            .build(service, "IntradayBarRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, ticker = %ticker, "bdib_stream request sent");
        Ok(())
    }

    fn send_bdtick_stream(
        &mut self,
        ticker: String,
        start_datetime: String,
        end_datetime: String,
        stream: tokio::sync::mpsc::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate streaming state
        let state = IntradayTickStreamState::new(ticker.clone(), stream);
        let key = self
            .requests
            .insert(IntradayRequestState::TickStream(state));
        let cid = CorrelationId::U64(key as u64);

        // Build request
        let service = self.services.get("//blp/refdata").unwrap();
        let request = RequestBuilder::new()
            .security(&ticker)
            .start_datetime(&start_datetime)
            .end_datetime(&end_datetime)
            .build(service, "IntradayTickRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, ticker = %ticker, "bdtick_stream request sent");
        Ok(())
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

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
use super::{Command, EngineConfig};

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
            Command::Bdp {
                tickers,
                fields,
                overrides,
                format,
                reply,
            } => {
                self.send_bdp(tickers, fields, overrides, format, reply)?;
            }
            Command::Bdh {
                tickers,
                fields,
                start_date,
                end_date,
                options,
                reply,
            } => {
                self.send_bdh(tickers, fields, start_date, end_date, options, reply)?;
            }
            Command::Bds {
                ticker,
                field,
                overrides,
                reply,
            } => {
                self.send_bds(ticker, field, overrides, reply)?;
            }
            Command::BdhStream {
                tickers,
                fields,
                start_date,
                end_date,
                options,
                stream,
            } => {
                self.send_bdh_stream(tickers, fields, start_date, end_date, options, stream)?;
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

    fn send_bdp(
        &mut self,
        tickers: Vec<String>,
        fields: Vec<String>,
        overrides: Vec<(String, String)>,
        format: OutputFormat,
        reply: oneshot::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate state with specified format
        let state = RefDataState::with_format(fields.clone(), format, reply);
        let key = self.requests.insert(RequestState::RefData(state));
        let cid = CorrelationId::U64(key as u64);

        // Build request using builder pattern
        let service = self.services.get("//blp/refdata").unwrap();
        let mut builder = RequestBuilder::new()
            .securities(tickers.clone())
            .fields(fields);
        for (name, value) in overrides {
            builder = builder.r#override(&name, value);
        }
        let request = builder.build(service, "ReferenceDataRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, tickers = ?tickers, "bdp request sent");
        Ok(())
    }

    fn send_bdh(
        &mut self,
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        _options: Vec<(String, String)>,
        reply: oneshot::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate state
        let state = HistDataState::new(fields.clone(), reply);
        let key = self.requests.insert(RequestState::HistData(state));
        let cid = CorrelationId::U64(key as u64);

        let service = self.services.get("//blp/refdata").unwrap();
        let request = RequestBuilder::new()
            .securities(tickers.clone())
            .fields(fields)
            .start_date(&start_date)
            .end_date(&end_date)
            .build(service, "HistoricalDataRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, tickers = ?tickers, "bdh request sent");
        Ok(())
    }

    fn send_bdh_stream(
        &mut self,
        tickers: Vec<String>,
        fields: Vec<String>,
        start_date: String,
        end_date: String,
        _options: Vec<(String, String)>,
        stream: tokio::sync::mpsc::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate streaming state
        let state = HistDataStreamState::new(fields.clone(), stream);
        let key = self.requests.insert(RequestState::HistDataStream(state));
        let cid = CorrelationId::U64(key as u64);

        let service = self.services.get("//blp/refdata").unwrap();
        let request = RequestBuilder::new()
            .securities(tickers.clone())
            .fields(fields)
            .start_date(&start_date)
            .end_date(&end_date)
            .build(service, "HistoricalDataRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, tickers = ?tickers, "bdh_stream request sent");
        Ok(())
    }

    fn send_bds(
        &mut self,
        ticker: String,
        field: String,
        overrides: Vec<(String, String)>,
        reply: oneshot::Sender<Result<arrow::record_batch::RecordBatch, BlpError>>,
    ) -> Result<(), BlpError> {
        self.ensure_service("//blp/refdata")?;

        // Allocate state
        let state = BulkDataState::new(field.clone(), reply);
        let key = self.requests.insert(RequestState::BulkData(state));
        let cid = CorrelationId::U64(key as u64);

        // Build request
        let service = self.services.get("//blp/refdata").unwrap();
        let mut builder = RequestBuilder::new()
            .securities(vec![ticker.clone()])
            .fields(vec![field.clone()]);
        for (name, value) in overrides {
            builder = builder.r#override(&name, value);
        }
        let request = builder.build(service, "ReferenceDataRequest")?;

        self.session.send_request(&request, None, Some(&cid))?;
        tracing::debug!(key = key, ticker = %ticker, field = %field, "bds request sent");
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
            if let Some(cid) = msg.correlation_id(i as usize) {
                if let CorrelationId::U64(key) = cid {
                    if let Some(state) = self.requests.get_mut(key as usize) {
                        state.on_partial(msg);
                        tracing::trace!(key = key, "partial response processed");
                    }
                }
            }
        }
    }

    fn handle_response(&mut self, msg: &xbbg_core::MessageRef) {
        // Multi-correlator aware
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(cid) = msg.correlation_id(i as usize) {
                if let CorrelationId::U64(key) = cid {
                    if self.requests.contains(key as usize) {
                        let state = self.requests.remove(key as usize);
                        state.finish_and_reply(msg);
                        tracing::debug!(key = key, "response completed");
                    }
                }
            }
        }
    }

    fn handle_request_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        let n = msg.num_correlation_ids();

        for i in 0..n {
            if let Some(cid) = msg.correlation_id(i as usize) {
                if let CorrelationId::U64(key) = cid {
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

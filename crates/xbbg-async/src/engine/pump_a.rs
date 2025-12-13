//! Lane A: Fast session pump for real-time subscriptions.
//!
//! This pump handles:
//! - SUBSCRIPTION_DATA (market data events)
//! - SUBSCRIPTION_STATUS (lifecycle + DATALOSS)
//! - SESSION_STATUS / SERVICE_STATUS (admin)

use slab::Slab;
use tokio::sync::mpsc;

use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, SessionOptions, SubscriptionList};

use super::state::SubscriptionState;
use super::{Command, EngineConfig, SlabKey};

/// Lane A pump state.
struct PumpA {
    session: Session,
    subs: Slab<SubscriptionState>,
    cmd_rx: mpsc::Receiver<Command>,
    config: EngineConfig,
    service_opened: bool,
}

impl PumpA {
    fn new(config: EngineConfig, cmd_rx: mpsc::Receiver<Command>) -> Result<Self, BlpError> {
        let mut opts = SessionOptions::new()?;
        opts.set_server_host(&config.server_host)?;
        opts.set_server_port(config.server_port);

        let session = Session::new(&opts)?;
        session.start()?;

        Ok(Self {
            session,
            subs: Slab::new(),
            cmd_rx,
            config,
            service_opened: false,
        })
    }

    fn run(&mut self) -> Result<(), BlpError> {
        tracing::info!("PumpA started (Lane A: subscriptions)");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(Command::Shutdown) => {
                        tracing::info!("PumpA shutting down");
                        return Ok(());
                    }
                    Ok(cmd) => self.handle_command(cmd)?,
                    Err(mpsc::error::TryRecvError::Empty) => break,
                    Err(mpsc::error::TryRecvError::Disconnected) => {
                        tracing::info!("PumpA command channel closed");
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
            Command::Subscribe {
                topics,
                fields,
                stream,
            } => {
                self.subscribe(topics, fields, stream)?;
            }
            Command::Unsubscribe { keys } => {
                self.unsubscribe(keys);
            }
            _ => {
                // Lane B commands shouldn't arrive here
                tracing::warn!("PumpA received Lane B command");
            }
        }
        Ok(())
    }

    fn subscribe(
        &mut self,
        topics: Vec<String>,
        fields: Vec<String>,
        stream: tokio::sync::mpsc::Sender<arrow::record_batch::RecordBatch>,
    ) -> Result<(), BlpError> {
        // Ensure service is open
        if !self.service_opened {
            self.session.open_service("//blp/mktdata")?;
            self.service_opened = true;
        }

        let mut sub_list = SubscriptionList::new()?;
        let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();

        for topic in &topics {
            // Allocate slab entry with overflow policy from config
            let state = SubscriptionState::with_policy(
                topic.clone(),
                fields.clone(),
                stream.clone(),
                self.config.subscription_flush_threshold,
                self.config.overflow_policy,
            );
            let key = self.subs.insert(state);

            // Create correlation ID from slab key
            let cid = CorrelationId::U64(key as u64);
            sub_list.add(topic, &field_refs, Some(&cid))?;

            tracing::debug!(topic = %topic, key = key, "subscription added");
        }

        self.session.subscribe(&sub_list, None)?;
        Ok(())
    }

    fn unsubscribe(&mut self, keys: Vec<SlabKey>) {
        for key in keys {
            if self.subs.contains(key) {
                self.subs.remove(key);
                tracing::debug!(key = key, "subscription removed");
            }
        }
    }

    fn dispatch_event(&mut self, ev: xbbg_core::Event) {
        let et = ev.event_type();

        // CRITICAL: iterate ALL messages, never break early
        for msg in ev.iter() {
            match et {
                EventType::SubscriptionData => {
                    self.handle_subscription_data(&msg);
                }
                EventType::SubscriptionStatus => {
                    self.handle_subscription_status(&msg);
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

    fn handle_subscription_data(&mut self, msg: &xbbg_core::MessageRef) {
        // Multi-correlator aware
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(cid) = msg.correlation_id(i as usize) {
                if let CorrelationId::U64(key) = cid {
                    if let Some(state) = self.subs.get_mut(key as usize) {
                        // Check for DATALOSS
                        let elem = msg.elements();
                        if let Some(event_type) = elem.get_element("MKTDATA_EVENT_TYPE") {
                            if let Some(val) = event_type.get_value_as_string(0) {
                                if val == "SUMMARY" {
                                    if let Some(subtype) = elem.get_element("MKTDATA_EVENT_SUBTYPE")
                                    {
                                        if let Some(sub_val) = subtype.get_value_as_string(0) {
                                            if sub_val == "DATALOSS" {
                                                state.on_dataloss();
                                                continue;
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Normal data
                        state.on_message(msg);
                    }
                }
            }
        }
    }

    fn handle_subscription_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        let n = msg.num_correlation_ids();

        for i in 0..n {
            if let Some(cid) = msg.correlation_id(i as usize) {
                if let CorrelationId::U64(key) = cid {
                    match msg_type {
                        "SubscriptionStarted" => {
                            tracing::debug!(key = key, "subscription started");
                        }
                        "SubscriptionFailure" => {
                            tracing::error!(key = key, "subscription failed");
                            if self.subs.contains(key as usize) {
                                self.subs.remove(key as usize);
                            }
                        }
                        "SubscriptionTerminated" => {
                            tracing::info!(key = key, "subscription terminated");
                            if self.subs.contains(key as usize) {
                                self.subs.remove(key as usize);
                            }
                        }
                        _ => {
                            tracing::trace!(key = key, msg_type = msg_type, "subscription status");
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
                tracing::info!("PumpA: session started");
            }
            "SessionTerminated" | "SessionConnectionDown" => {
                tracing::error!("PumpA: session terminated/down");
            }
            _ => {
                tracing::debug!(msg_type = msg_type, "PumpA: session status");
            }
        }
    }

    fn handle_service_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        tracing::debug!(msg_type = msg_type, "PumpA: service status");
    }
}

/// Run the Lane A pump thread.
pub fn run(config: EngineConfig, cmd_rx: mpsc::Receiver<Command>) -> Result<(), BlpError> {
    let mut pump = PumpA::new(config, cmd_rx)?;
    pump.run()
}

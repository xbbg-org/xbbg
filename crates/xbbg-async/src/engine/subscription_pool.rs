//! Subscription session pool with claim/release semantics.
//!
//! Each subscription claims a dedicated session for isolation.
//! Sessions are pre-warmed and returned to the pool when subscriptions end.
//! If the pool is exhausted, new sessions are created dynamically with a warning.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};

use arrow::record_batch::RecordBatch;
use parking_lot::Mutex;
use slab::Slab;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::session::Session;
use xbbg_core::{BlpError, EventType, SubscriptionList};

use super::dispatch::DispatchKey;
use super::state::{SubscriptionMetrics, SubscriptionState};
use super::{
    start_configured_session, BlpAsyncError, EngineConfig, OverflowPolicy, SessionLifecycleState,
    SharedSubscriptionStatus, SlabKey, SubscriptionEventLevel, SubscriptionFailureKind,
    SubscriptionRecoveryPolicy,
};

type SubscriptionReplyPayload = (Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>);
type SubscriptionReply = Result<SubscriptionReplyPayload, BlpError>;

/// Commands sent to a subscription worker.
pub enum SubscriptionCommand {
    /// Start a subscription.
    Subscribe {
        /// Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap")
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        /// Subscription options (e.g., ["VWAP_START_TIME=09:30"])
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        status: SharedSubscriptionStatus,
        /// Reply with slab keys for later unsubscribe.
        reply: oneshot::Sender<SubscriptionReply>,
    },
    /// Add topics to an existing subscription (uses same stream sender).
    AddTopics {
        /// Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap")
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        /// Subscription options
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        status: SharedSubscriptionStatus,
        /// Reply with new slab keys.
        reply: oneshot::Sender<SubscriptionReply>,
    },
    /// Stop subscriptions by key.
    Unsubscribe { keys: Vec<SlabKey> },
    /// Shutdown the worker.
    Shutdown,
}

/// A subscription worker managing a single session.
struct SubscriptionWorker {
    id: usize,
    session: Session,
    subs: Slab<SubscriptionState>,
    cmd_rx: mpsc::Receiver<SubscriptionCommand>,
    config: Arc<EngineConfig>,
    /// Services that have been opened on this session.
    open_services: std::collections::HashSet<String>,
    /// Keys pending Bloomberg's SubscriptionTerminated confirmation.
    ///
    /// When we explicitly unsubscribe, the slab entry stays alive until Bloomberg
    /// confirms via SubscriptionTerminated. This prevents a slab key reuse race
    /// where a new subscription reuses a freed slot and then gets hit by the
    /// stale termination event meant for the old subscription.
    pending_cancel: std::collections::HashSet<SlabKey>,
    /// Shared active/failed topic metadata for the currently claimed stream.
    status: Option<SharedSubscriptionStatus>,
    current_service: Option<String>,
    current_options: Vec<String>,
}

impl SubscriptionWorker {
    fn new(
        id: usize,
        config: Arc<EngineConfig>,
        cmd_rx: mpsc::Receiver<SubscriptionCommand>,
    ) -> Result<Self, BlpError> {
        let session = start_configured_session(&config, true)?;

        // Pre-open the mktdata service (most common)
        session.open_service(crate::services::Service::MktData.as_str())?;
        let mut open_services = std::collections::HashSet::new();
        open_services.insert(crate::services::Service::MktData.to_string());

        xbbg_log::info!(worker_id = id, "subscription worker pre-warmed");

        Ok(Self {
            id,
            session,
            subs: Slab::new(),
            cmd_rx,
            config,
            open_services,
            pending_cancel: std::collections::HashSet::new(),
            status: None,
            current_service: None,
            current_options: Vec::new(),
        })
    }

    fn record_failure(
        &mut self,
        key: SlabKey,
        reason: String,
        kind: SubscriptionFailureKind,
    ) -> Option<String> {
        self.status
            .as_ref()
            .and_then(|status| status.lock().record_failure(key, reason, kind))
    }

    fn clear_active_status(&mut self) {
        if let Some(status) = &self.status {
            status.lock().clear_active();
        }
    }

    /// Ensure a service is open, opening it on demand if needed.
    fn ensure_service(&mut self, service: &str) -> Result<(), BlpError> {
        if !self.open_services.contains(service) {
            xbbg_log::info!(
                worker_id = self.id,
                service = service,
                "opening service on demand"
            );
            self.session.open_service(service)?;
            self.open_services.insert(service.to_string());
            if let Some(status) = &self.status {
                status.lock().record_service_state(
                    service.to_string(),
                    true,
                    "ServiceOpened",
                    Some("service opened on demand".to_string()),
                );
            }
        }
        Ok(())
    }

    fn run(&mut self) -> Result<(), BlpError> {
        xbbg_log::info!(worker_id = self.id, "SubscriptionWorker started");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(SubscriptionCommand::Shutdown) => {
                        xbbg_log::info!(worker_id = self.id, "SubscriptionWorker shutting down");
                        return Ok(());
                    }
                    Ok(SubscriptionCommand::Subscribe {
                        service,
                        topics,
                        fields,
                        options,
                        flush_threshold,
                        overflow_policy,
                        stream,
                        status,
                        reply,
                    }) => {
                        self.status = Some(status);
                        self.current_service = Some(service.clone());
                        self.current_options = options.clone();
                        if let Some(status) = &self.status {
                            status.lock().record_service_state(
                                service.clone(),
                                true,
                                "ServiceReady",
                                Some("service available for subscription".to_string()),
                            );
                        }
                        // Ensure service is open
                        if let Err(e) = self.ensure_service(&service) {
                            xbbg_log::error!(worker_id = self.id, service = %service, error = %e, "failed to open service");
                            let _ = reply.send(Err(e));
                            continue;
                        }
                        let result = self.subscribe(
                            topics,
                            fields,
                            options,
                            flush_threshold,
                            overflow_policy,
                            stream,
                        );
                        let _ = reply.send(result);
                    }
                    Ok(SubscriptionCommand::AddTopics {
                        service,
                        topics,
                        fields,
                        options,
                        flush_threshold,
                        overflow_policy,
                        stream,
                        status,
                        reply,
                    }) => {
                        self.status = Some(status);
                        self.current_service = Some(service.clone());
                        self.current_options = options.clone();
                        if let Some(status) = &self.status {
                            status.lock().record_service_state(
                                service.clone(),
                                true,
                                "ServiceReady",
                                Some("service available for subscription".to_string()),
                            );
                        }
                        // Ensure service is open
                        if let Err(e) = self.ensure_service(&service) {
                            xbbg_log::error!(worker_id = self.id, service = %service, error = %e, "failed to open service");
                            let _ = reply.send(Err(e));
                            continue;
                        }
                        // AddTopics uses the same logic as Subscribe
                        let result = self.subscribe(
                            topics,
                            fields,
                            options,
                            flush_threshold,
                            overflow_policy,
                            stream,
                        );
                        let _ = reply.send(result);
                    }
                    Ok(SubscriptionCommand::Unsubscribe { keys }) => {
                        self.unsubscribe(keys);
                    }
                    Err(mpsc::error::TryRecvError::Empty) => break,
                    Err(mpsc::error::TryRecvError::Disconnected) => {
                        xbbg_log::info!(worker_id = self.id, "command channel closed");
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

    fn subscribe(
        &mut self,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpError> {
        let mut sub_list = SubscriptionList::new();

        let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();
        let options_str = options.join(",");
        let mut keys = Vec::with_capacity(topics.len());
        let mut metrics: Vec<Arc<SubscriptionMetrics>> = Vec::with_capacity(topics.len());
        let ft = flush_threshold.unwrap_or(self.config.subscription_flush_threshold);
        let op = overflow_policy.unwrap_or(self.config.overflow_policy);

        for topic in &topics {
            let state = SubscriptionState::with_policy(
                topic.clone(),
                fields.clone(),
                stream.clone(),
                ft,
                op,
            );
            let metrics_arc = state.metrics.clone();
            let key = self.subs.insert(state);

            let cid = DispatchKey::from_slab_key(key).to_correlation_id();
            if let Err(e) = sub_list.add(topic, &field_refs, &options_str, &cid) {
                xbbg_log::error!(worker_id = self.id, topic = %topic, error = %e, "failed to add topic");
                // Clean up phantom slab entry — sub_list.add failed so Bloomberg
                // will never send data for this correlation ID.
                self.subs.remove(key);
                continue;
            }

            keys.push(key);
            metrics.push(metrics_arc);
            xbbg_log::debug!(worker_id = self.id, topic = %topic, key = key, "subscription added");
        }

        if keys.is_empty() {
            return Err(BlpError::SubscriptionFailure {
                cid: None,
                label: Some("failed to build any subscription entries".to_string()),
            });
        }

        if let Err(e) = self.session.subscribe(&sub_list, None) {
            xbbg_log::error!(worker_id = self.id, error = %e, "subscribe failed");
            // Clean up all slab entries — session.subscribe failed so
            // Bloomberg will never send data for any of these.
            for &key in &keys {
                if self.subs.contains(key) {
                    self.subs.remove(key);
                }
            }
            return Err(e);
        }

        Ok((keys, metrics))
    }

    fn unsubscribe(&mut self, keys: Vec<SlabKey>) {
        // Build a SubscriptionList with correlation IDs so Bloomberg stops sending data.
        // Without this, the SDK continues delivering events for removed subscriptions,
        // wasting bandwidth and risking stale correlation ID reuse.
        let mut unsub_list = SubscriptionList::new();
        let mut unsub_count = 0usize;
        for &key in &keys {
            if self.subs.contains(key) {
                let state = &mut self.subs[key];
                state.mark_closing();
                let cid = DispatchKey::from_slab_key(key).to_correlation_id();
                // Topic and empty fields/options are sufficient for unsubscribe —
                // Bloomberg matches on correlation ID.
                if let Err(e) = unsub_list.add(&state.topic, &[], "", &cid) {
                    xbbg_log::error!(worker_id = self.id, key = key, error = %e, "failed to build unsub list entry");
                } else {
                    unsub_count += 1;
                }
            }
        }

        if unsub_count > 0 {
            if let Err(e) = self.session.unsubscribe(&unsub_list) {
                xbbg_log::error!(worker_id = self.id, error = %e, "session.unsubscribe failed");
            }
        }

        // Mark keys as pending cancellation — DON'T remove from slab yet.
        // Bloomberg will send a SubscriptionTerminated event for each key,
        // at which point we remove from slab. This prevents a slab key reuse
        // race: if we freed the slot now, a subsequent add_topics could reuse it,
        // and the stale SubscriptionTerminated would hit the wrong subscription.
        for &key in &keys {
            if self.subs.contains(key) {
                self.pending_cancel.insert(key);
                if let Some(status) = &self.status {
                    let mut status = status.lock();
                    let topic = status.mark_topic_unsubscribing(key);
                    status.record_subscription_event(
                        "SubscriptionPendingCancel",
                        topic,
                        None,
                        SubscriptionEventLevel::Info,
                    );
                }
                xbbg_log::debug!(
                    worker_id = self.id,
                    key = key,
                    "subscription pending cancel"
                );
            }
        }
    }

    fn dispatch_event(&mut self, ev: xbbg_core::Event) {
        let et = ev.event_type();

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
                EventType::Admin => {
                    self.handle_admin_event(&msg);
                }
                _ => {}
            }
        }
    }

    fn handle_subscription_data(&mut self, msg: &xbbg_core::Message<'_>) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(correlation_id) = msg.correlation_id(i) {
                let Some(dispatch_key) = DispatchKey::from_correlation_id(&correlation_id) else {
                    continue;
                };
                let key = dispatch_key.to_slab_key();
                // Skip in-flight data for subscriptions we've already cancelled.
                if self.pending_cancel.contains(&key) {
                    continue;
                }
                if let Some(state) = self.subs.get_mut(key) {
                    // Check for DATALOSS
                    let elem = msg.elements();
                    if let Some(event_type) = elem.get_by_str("MKTDATA_EVENT_TYPE") {
                        if let Some(val) = event_type.get_str(0) {
                            if val == "SUMMARY" {
                                if let Some(subtype) = elem.get_by_str("MKTDATA_EVENT_SUBTYPE") {
                                    if let Some(sub_val) = subtype.get_str(0) {
                                        if sub_val == "DATALOSS" {
                                            let topic = state.topic.to_string();
                                            let at_us = msg.time_received_us();
                                            state.on_dataloss(at_us);
                                            if let Some(status) = &self.status {
                                                status.lock().record_admin_data_loss(
                                                    Some(topic),
                                                    Some(
                                                        "subscription data reported DATALOSS"
                                                            .to_string(),
                                                    ),
                                                );
                                            }
                                            continue;
                                        }
                                    }
                                }
                            }
                        }
                    }

                    let first_message = state.on_message(msg);
                    if first_message {
                        let topic = if let Some(status) = &self.status {
                            let mut status = status.lock();
                            let topic = status.mark_topic_streaming(key);
                            status.record_subscription_event(
                                "SubscriptionStreaming",
                                topic.clone(),
                                None,
                                SubscriptionEventLevel::Info,
                            );
                            topic
                        } else {
                            None
                        };
                        xbbg_log::debug!(
                            worker_id = self.id,
                            key = key,
                            topic = ?topic,
                            "subscription entered streaming state"
                        );
                    }
                }
            }
        }
    }

    fn handle_subscription_status(&mut self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        let n = msg.num_correlation_ids();

        // Extract reason description from the message if available
        let reason = msg
            .elements()
            .get_by_str("reason")
            .and_then(|r| r.get_by_str("description"))
            .and_then(|d| d.get_str(0))
            .map(|s| s.to_string());

        for i in 0..n {
            if let Some(correlation_id) = msg.correlation_id(i) {
                let Some(dispatch_key) = DispatchKey::from_correlation_id(&correlation_id) else {
                    continue;
                };
                let key = dispatch_key.to_slab_key();
                match msg_type {
                    "SubscriptionStarted" => {
                        xbbg_log::debug!(worker_id = self.id, key = key, "subscription started");
                        if let Some(status) = &self.status {
                            let mut status = status.lock();
                            let topic = status.mark_topic_started(key);
                            status.record_subscription_event(
                                "SubscriptionStarted",
                                topic,
                                None,
                                SubscriptionEventLevel::Info,
                            );
                        }
                    }
                    "SubscriptionFailure" => {
                        if self.pending_cancel.remove(&key) {
                            // Bloomberg sends SubscriptionFailure (instead of SubscriptionTerminated)
                            // when a subscription is cancelled before it fully starts. Since this was
                            // explicitly requested via unsubscribe(), silently clean up.
                            if self.subs.contains(key) {
                                let mut state = self.subs.remove(key);
                                state.mark_closing();
                                if let Some(status) = &self.status {
                                    let mut status = status.lock();
                                    let topic = status.mark_topic_unsubscribed(key);
                                    status.record_subscription_event(
                                        "SubscriptionCancelled",
                                        topic,
                                        reason.clone(),
                                        SubscriptionEventLevel::Info,
                                    );
                                }
                            }
                            xbbg_log::debug!(
                                worker_id = self.id,
                                key = key,
                                "pending cancel confirmed via SubscriptionFailure"
                            );
                        } else {
                            let reason_text = reason
                                .clone()
                                .unwrap_or_else(|| "subscription failed".to_string());
                            if self.subs.contains(key) {
                                let mut state = self.subs.remove(key);
                                state.mark_closing();
                                let topic = self
                                    .record_failure(
                                        key,
                                        reason_text.clone(),
                                        SubscriptionFailureKind::Failure,
                                    )
                                    .unwrap_or_else(|| state.topic.to_string());
                                xbbg_log::warn!(
                                    worker_id = self.id,
                                    key = key,
                                    topic = %topic,
                                    reason = %reason_text,
                                    "subscription failed for topic"
                                );
                                if let Some(status) = &self.status {
                                    status.lock().record_subscription_event(
                                        "SubscriptionFailure",
                                        Some(topic.clone()),
                                        Some(reason_text.clone()),
                                        SubscriptionEventLevel::Warning,
                                    );
                                }
                                if self.subs.is_empty() && self.pending_cancel.is_empty() {
                                    state.fail(BlpError::SubscriptionFailure {
                                        cid: None,
                                        label: Some(format!(
                                            "All subscriptions failed; last failure: {} ({})",
                                            topic, reason_text,
                                        )),
                                    });
                                }
                            }
                        }
                    }
                    "SubscriptionTerminated" => {
                        if self.pending_cancel.remove(&key) {
                            // This termination was explicitly requested via unsubscribe().
                            // Silently clean up the slab entry — don't propagate an error.
                            if self.subs.contains(key) {
                                let mut state = self.subs.remove(key);
                                state.mark_closing();
                                if let Some(status) = &self.status {
                                    let mut status = status.lock();
                                    let topic = status.mark_topic_unsubscribed(key);
                                    status.record_subscription_event(
                                        "SubscriptionTerminated",
                                        topic,
                                        reason.clone(),
                                        SubscriptionEventLevel::Info,
                                    );
                                }
                            }
                            xbbg_log::debug!(
                                worker_id = self.id,
                                key = key,
                                "pending cancel confirmed by Bloomberg"
                            );
                        } else {
                            let reason_text = reason
                                .clone()
                                .unwrap_or_else(|| "subscription terminated".to_string());
                            if self.subs.contains(key) {
                                let mut state = self.subs.remove(key);
                                state.mark_closing();
                                let topic = self
                                    .record_failure(
                                        key,
                                        reason_text.clone(),
                                        SubscriptionFailureKind::Terminated,
                                    )
                                    .unwrap_or_else(|| state.topic.to_string());
                                xbbg_log::warn!(
                                    worker_id = self.id,
                                    key = key,
                                    topic = %topic,
                                    reason = %reason_text,
                                    "subscription terminated for topic"
                                );
                                if let Some(status) = &self.status {
                                    status.lock().record_subscription_event(
                                        "SubscriptionTerminated",
                                        Some(topic.clone()),
                                        Some(reason_text.clone()),
                                        SubscriptionEventLevel::Warning,
                                    );
                                }
                                if self.subs.is_empty() && self.pending_cancel.is_empty() {
                                    state.fail(BlpError::SubscriptionFailure {
                                        cid: None,
                                        label: Some(format!(
                                            "All subscriptions ended; last termination: {} ({})",
                                            topic, reason_text,
                                        )),
                                    });
                                }
                            }
                        }
                    }
                    _ => {
                        xbbg_log::trace!(
                            worker_id = self.id,
                            key = key,
                            msg_type = msg_type,
                            "subscription status"
                        );
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
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Up,
                        "SessionStarted",
                        None,
                    );
                }
            }
            "SessionConnectionDown" => {
                xbbg_log::error!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    "session connection down — SDK may attempt reconnect"
                );
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Down,
                        "SessionConnectionDown",
                        Some(format!(
                            "worker={} active_subscriptions={}",
                            self.id,
                            self.subs.len(),
                        )),
                    );
                }
            }
            "SessionTerminated" => {
                xbbg_log::error!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    "session terminated — all subscriptions lost"
                );
                // Session is dead. Send error to all consumers and remove all subs.
                let keys: Vec<usize> = self.subs.iter().map(|(k, _)| k).collect();
                for key in keys {
                    let mut state = self.subs.remove(key);
                    state.mark_closing();
                    state.fail(BlpError::Internal {
                        detail: format!(
                            "Bloomberg session terminated (worker={}). \
                             Subscription closed. Please resubscribe.",
                            self.id,
                        ),
                    });
                }
                self.clear_active_status();
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Terminated,
                        "SessionTerminated",
                        Some(format!("worker={}", self.id)),
                    );
                }
            }
            "SessionConnectionUp" => {
                xbbg_log::info!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    "session connection restored"
                );
                if let Some(status) = &self.status {
                    let mut status = status.lock();
                    let was_down = status.session().state == SessionLifecycleState::Down;
                    status.record_session_state(
                        SessionLifecycleState::Up,
                        "SessionConnectionUp",
                        Some(format!(
                            "worker={} active_subscriptions={}",
                            self.id,
                            self.subs.len(),
                        )),
                    );
                    let recovery_policy = status.session().recovery_policy;
                    drop(status);
                    if was_down && recovery_policy == SubscriptionRecoveryPolicy::Resubscribe {
                        self.recover_active_subscriptions();
                    }
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
        let service = msg
            .elements()
            .get_by_str("serviceName")
            .and_then(|value| value.get_str(0))
            .map(str::to_string);
        if let Some(status) = &self.status {
            let mut status = status.lock();
            match msg_type {
                "ServiceDown" => {
                    status.record_service_state(
                        service.unwrap_or_else(|| "unknown".to_string()),
                        false,
                        msg_type,
                        None,
                    );
                }
                "ServiceUp" | "ServiceOpened" => {
                    status.record_service_state(
                        service.unwrap_or_else(|| "unknown".to_string()),
                        true,
                        msg_type,
                        None,
                    );
                }
                _ => {}
            }
        }
        xbbg_log::debug!(worker_id = self.id, msg_type = msg_type, "service status");
    }

    fn handle_admin_event(&mut self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        match msg_type {
            "SlowConsumerWarning" => {
                if let Some(status) = &self.status {
                    status.lock().record_admin_warning(msg_type, None);
                }
                xbbg_log::warn!(worker_id = self.id, "slow consumer warning");
            }
            "SlowConsumerWarningCleared" => {
                for (_, state) in self.subs.iter_mut() {
                    state.clear_slow_consumer();
                }
                if let Some(status) = &self.status {
                    status.lock().record_admin_warning_cleared(msg_type, None);
                }
                xbbg_log::info!(worker_id = self.id, "slow consumer warning cleared");
            }
            "DataLoss" => {
                let timestamp_us = msg.time_received_us();
                let correlation_count = msg.num_correlation_ids();
                if correlation_count == 0 {
                    if let Some(status) = &self.status {
                        status.lock().record_admin_data_loss(None, None);
                    }
                }
                for index in 0..correlation_count {
                    if let Some(correlation_id) = msg.correlation_id(index) {
                        let Some(dispatch_key) = DispatchKey::from_correlation_id(&correlation_id)
                        else {
                            continue;
                        };
                        let key = dispatch_key.to_slab_key();
                        if let Some(state) = self.subs.get_mut(key) {
                            let topic = state.topic.to_string();
                            state.on_dataloss(timestamp_us);
                            if let Some(status) = &self.status {
                                status.lock().record_admin_data_loss(Some(topic), None);
                            }
                        }
                    }
                }
                xbbg_log::warn!(worker_id = self.id, "data loss event received");
            }
            _ => {
                if let Some(status) = &self.status {
                    status.lock().push_event(
                        super::SubscriptionEventCategory::Admin,
                        SubscriptionEventLevel::Info,
                        msg_type,
                        None,
                        None,
                    );
                }
                xbbg_log::debug!(worker_id = self.id, msg_type = msg_type, "admin event");
            }
        }
    }

    fn recover_active_subscriptions(&mut self) {
        if self.subs.is_empty() {
            return;
        }

        let Some(service) = self.current_service.clone() else {
            return;
        };

        let mut sub_list = SubscriptionList::new();
        for (key, state) in self.subs.iter() {
            let cid = DispatchKey::from_slab_key(key).to_correlation_id();
            let fields: Vec<&str> = state
                .field_strings
                .iter()
                .map(|field| field.as_str())
                .collect();
            let options = self.current_options.join(",");
            if let Err(error) = sub_list.add(&state.topic, &fields, &options, &cid) {
                if let Some(status) = &self.status {
                    let mut status = status.lock();
                    status.record_recovery_error(format!(
                        "failed to prepare recovery subscription for {}: {}",
                        state.topic, error,
                    ));
                }
                xbbg_log::warn!(
                    worker_id = self.id,
                    topic = %state.topic,
                    error = %error,
                    "failed to prepare reconnect recovery"
                );
                return;
            }
        }

        if let Some(status) = &self.status {
            status.lock().record_recovery_attempt(Some(format!(
                "service={} active_subscriptions={}",
                service,
                self.subs.len(),
            )));
        }

        match self.session.subscribe(&sub_list, Some("xbbg-recovery")) {
            Ok(()) => {
                if let Some(status) = &self.status {
                    status.lock().record_recovery_success(Some(format!(
                        "service={} active_subscriptions={}",
                        service,
                        self.subs.len(),
                    )));
                }
                xbbg_log::info!(
                    worker_id = self.id,
                    service = %service,
                    active_subs = self.subs.len(),
                    "recovery subscribe issued after reconnect"
                );
            }
            Err(error) => {
                if let Some(status) = &self.status {
                    status.lock().record_recovery_error(format!(
                        "service={} active_subscriptions={} error={}",
                        service,
                        self.subs.len(),
                        error,
                    ));
                }
                xbbg_log::warn!(
                    worker_id = self.id,
                    service = %service,
                    active_subs = self.subs.len(),
                    error = %error,
                    "recovery subscribe failed after reconnect"
                );
            }
        }
    }
}

/// Cloneable command path for a claimed subscription worker.
///
/// This handle can enqueue commands on the worker, but it does not own the
/// worker lease. Releasing the session back to the pool still requires the
/// single-owner [`SessionClaim`].
#[derive(Clone)]
pub struct SubscriptionCommandHandle {
    id: usize,
    cmd_tx: mpsc::Sender<SubscriptionCommand>,
}

impl SubscriptionCommandHandle {
    /// Start a new subscription on the claimed worker.
    #[allow(clippy::too_many_arguments)]
    pub async fn subscribe(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        status: SharedSubscriptionStatus,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpAsyncError> {
        let (reply_tx, reply_rx) = oneshot::channel();

        self.cmd_tx
            .send(SubscriptionCommand::Subscribe {
                service,
                topics,
                fields,
                options,
                flush_threshold,
                overflow_policy,
                stream,
                status,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?
            .map_err(BlpAsyncError::BlpError)
    }

    /// Add topics to an existing subscription.
    #[allow(clippy::too_many_arguments)]
    pub async fn add_topics(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        status: SharedSubscriptionStatus,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpAsyncError> {
        let (reply_tx, reply_rx) = oneshot::channel();

        self.cmd_tx
            .send(SubscriptionCommand::AddTopics {
                service,
                topics,
                fields,
                options,
                flush_threshold,
                overflow_policy,
                stream,
                status,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?
            .map_err(BlpAsyncError::BlpError)
    }

    /// Unsubscribe topics on the claimed worker.
    pub async fn unsubscribe(&self, keys: Vec<SlabKey>) -> Result<(), BlpAsyncError> {
        self.cmd_tx
            .send(SubscriptionCommand::Unsubscribe { keys })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        Ok(())
    }

    /// Get the worker ID behind this command path.
    pub fn worker_id(&self) -> usize {
        self.id
    }

    fn signal_shutdown(&self) {
        let _ = self.cmd_tx.try_send(SubscriptionCommand::Shutdown);
    }
}

/// Handle to a subscription worker.
pub struct SubscriptionWorkerHandle {
    command: SubscriptionCommandHandle,
    thread: Option<JoinHandle<()>>,
}

impl SubscriptionWorkerHandle {
    fn spawn(id: usize, config: Arc<EngineConfig>) -> Result<Self, BlpError> {
        let (cmd_tx, cmd_rx) = mpsc::channel(config.command_queue_size);
        let (startup_tx, startup_rx) = std::sync::mpsc::channel();

        let config_clone = config.clone();
        let thread = thread::Builder::new()
            .name(format!("xbbg-sub-{}", id))
            .spawn(move || {
                match SubscriptionWorker::new(id, config_clone, cmd_rx) {
                    Ok(mut worker) => {
                        let _ = startup_tx.send(Ok(()));
                        if let Err(e) = worker.run() {
                            xbbg_log::error!(worker_id = id, error = %e, "subscription worker error");
                        }
                    }
                    Err(e) => {
                        let detail = e.to_string();
                        let _ = startup_tx.send(Err(e));
                        xbbg_log::error!(worker_id = id, error = %detail, "subscription worker creation failed");
                    }
                }
            })
            .map_err(|e| BlpError::Internal {
                detail: format!("failed to spawn subscription worker: {}", e),
            })?;

        match startup_rx.recv() {
            Ok(Ok(())) => {}
            Ok(Err(err)) => return Err(err),
            Err(err) => {
                return Err(BlpError::Internal {
                    detail: format!(
                        "subscription worker startup channel closed unexpectedly: {err}"
                    ),
                });
            }
        }

        Ok(Self {
            command: SubscriptionCommandHandle { id, cmd_tx },
            thread: Some(thread),
        })
    }

    fn id(&self) -> usize {
        self.command.id
    }

    fn command_handle(&self) -> SubscriptionCommandHandle {
        self.command.clone()
    }

    /// Signal shutdown without waiting (non-blocking).
    fn signal_shutdown(&self) {
        self.command.signal_shutdown();
    }

    /// Shutdown and wait for thread to finish (blocking).
    fn shutdown_blocking(&mut self) {
        self.signal_shutdown();
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

impl Drop for SubscriptionWorkerHandle {
    fn drop(&mut self) {
        // Non-blocking: just signal, don't wait
        self.signal_shutdown();
    }
}

/// Pool of subscription workers with claim/release semantics.
pub struct SubscriptionSessionPool {
    /// Available workers (not currently claimed).
    available: Mutex<Vec<SubscriptionWorkerHandle>>,
    /// Next worker ID for dynamically created workers.
    next_id: AtomicUsize,
    /// Configuration.
    config: Arc<EngineConfig>,
    /// Initial pool size (for logging).
    initial_size: usize,
}

impl SubscriptionSessionPool {
    /// Create a new pool with the specified number of pre-warmed sessions.
    pub fn new(size: usize, config: Arc<EngineConfig>) -> Result<Self, BlpAsyncError> {
        xbbg_log::info!(pool_size = size, "creating subscription session pool");

        let mut available = Vec::with_capacity(size);
        for id in 0..size {
            let handle = SubscriptionWorkerHandle::spawn(id, config.clone()).map_err(|e| {
                BlpAsyncError::BlpError(BlpError::Internal {
                    detail: format!("failed to spawn subscription worker {}: {}", id, e),
                })
            })?;
            available.push(handle);
        }

        xbbg_log::info!(pool_size = size, "subscription session pool ready");

        Ok(Self {
            available: Mutex::new(available),
            next_id: AtomicUsize::new(size),
            config,
            initial_size: size,
        })
    }

    /// Claim a session from the pool.
    ///
    /// If the pool is exhausted, creates a new session dynamically with a warning.
    /// Returns a SessionClaim that releases the session back to the pool on drop.
    ///
    /// Takes `Arc<Self>` to allow `SessionClaim` to have a `'static` lifetime.
    pub fn claim(self: &Arc<Self>) -> Result<SessionClaim, BlpAsyncError> {
        let handle = {
            let mut available = self.available.lock();
            if let Some(handle) = available.pop() {
                xbbg_log::debug!(
                    worker_id = handle.id(),
                    remaining = available.len(),
                    "claimed session from pool"
                );
                handle
            } else {
                drop(available); // Release lock before creating new worker

                // Pool exhausted - create new session dynamically
                let new_id = self.next_id.fetch_add(1, Ordering::Relaxed);
                xbbg_log::warn!(
                    worker_id = new_id,
                    initial_size = self.initial_size,
                    "subscription pool exhausted, creating new session"
                );

                SubscriptionWorkerHandle::spawn(new_id, self.config.clone()).map_err(|e| {
                    BlpAsyncError::BlpError(BlpError::Internal {
                        detail: format!("failed to create dynamic subscription worker: {}", e),
                    })
                })?
            }
        };

        Ok(SessionClaim {
            handle: Some(handle),
            pool: Arc::clone(self),
        })
    }

    /// Release a session back to the pool.
    fn release(&self, handle: SubscriptionWorkerHandle) {
        let mut available = self.available.lock();
        xbbg_log::debug!(
            worker_id = handle.id(),
            pool_size = available.len() + 1,
            "session returned to pool"
        );
        available.push(handle);
    }

    /// Get the number of available sessions.
    pub fn available_count(&self) -> usize {
        self.available.lock().len()
    }

    /// Signal shutdown to all available workers (non-blocking).
    ///
    /// Note: Only signals workers currently in the pool. Claimed sessions
    /// will be signaled when they're returned to the pool and dropped.
    pub fn signal_shutdown(&self) {
        let available = self.available.lock();
        xbbg_log::info!(
            count = available.len(),
            "signaling subscription pool shutdown"
        );
        for handle in available.iter() {
            handle.signal_shutdown();
        }
    }

    /// Graceful shutdown - waits for all workers to finish (blocking).
    pub fn shutdown_blocking(&self) {
        let mut available = self.available.lock();
        xbbg_log::info!(
            count = available.len(),
            "shutting down subscription pool (blocking)"
        );
        for handle in available.iter_mut() {
            handle.shutdown_blocking();
        }
        available.clear();
    }
}

impl Drop for SubscriptionSessionPool {
    fn drop(&mut self) {
        // Non-blocking: just signal, don't wait
        self.signal_shutdown();
    }
}

/// Handle to a claimed session.
///
/// Releases the session back to the pool on drop.
pub struct SessionClaim {
    handle: Option<SubscriptionWorkerHandle>,
    pool: Arc<SubscriptionSessionPool>,
}

impl SessionClaim {
    /// Clone the command path for this claimed worker.
    ///
    /// The returned handle can be used outside short-lived metadata locks, while
    /// the [`SessionClaim`] continues to own the pool lease.
    pub fn command_handle(&self) -> Result<SubscriptionCommandHandle, BlpAsyncError> {
        self.handle
            .as_ref()
            .map(SubscriptionWorkerHandle::command_handle)
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "session already released".to_string(),
            })
    }

    /// Subscribe to topics on this session.
    ///
    /// # Arguments
    /// * `service` - Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap")
    /// * `topics` - Securities to subscribe to
    /// * `fields` - Fields to subscribe to
    /// * `options` - Subscription options (e.g., ["VWAP_START_TIME=09:30"])
    /// * `stream` - Channel to send data batches (or errors) to
    #[allow(clippy::too_many_arguments)]
    pub async fn subscribe(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        status: SharedSubscriptionStatus,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpAsyncError> {
        self.command_handle()?
            .subscribe(
                service,
                topics,
                fields,
                options,
                flush_threshold,
                overflow_policy,
                stream,
                status,
            )
            .await
    }

    /// Add topics to an existing subscription.
    #[allow(clippy::too_many_arguments)]
    pub async fn add_topics(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
        status: SharedSubscriptionStatus,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpAsyncError> {
        self.command_handle()?
            .add_topics(
                service,
                topics,
                fields,
                options,
                flush_threshold,
                overflow_policy,
                stream,
                status,
            )
            .await
    }

    /// Unsubscribe from topics on this session.
    pub async fn unsubscribe(&self, keys: Vec<SlabKey>) -> Result<(), BlpAsyncError> {
        self.command_handle()?.unsubscribe(keys).await
    }

    /// Get the worker ID.
    pub fn worker_id(&self) -> Option<usize> {
        self.handle.as_ref().map(SubscriptionWorkerHandle::id)
    }
}

impl Drop for SessionClaim {
    fn drop(&mut self) {
        if let Some(handle) = self.handle.take() {
            self.pool.release(handle);
        }
    }
}

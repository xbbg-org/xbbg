//! Subscription session pool with claim/release semantics.
//!
//! Each subscription claims a dedicated session for isolation.
//! Sessions are pre-warmed and returned to the pool when subscriptions end.
//! If the pool is exhausted, new sessions are created dynamically with a warning.

use std::sync::atomic::{AtomicU8, AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread::{self, JoinHandle};

use arrow::record_batch::RecordBatch;
use parking_lot::Mutex;
use slab::Slab;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, SubscriptionList};

/// High-bit tag for CorrelationIds we generate for async `open_service` calls.
/// Slab-key-derived subscription CIDs are small non-negative integers, so tagging
/// service-open CIDs with bit 62 set keeps them disjoint.
const SERVICE_OPEN_CID_TAG: i64 = 1_i64 << 62;

/// Max wall time for an async open_service reply before we give up.
const SERVICE_OPEN_TIMEOUT_MS: u64 = 10_000;

use super::dispatch::DispatchKey;
use super::state::{SubscriptionMetrics, SubscriptionState};
use super::{
    start_configured_session, BlpAsyncError, EngineConfig, OverflowPolicy, SessionLifecycleState,
    SharedSubscriptionStatus, SlabKey, SubscriptionEventLevel, SubscriptionFailureKind,
    WorkerHealth,
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
        all_fields: bool,
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
        all_fields: bool,
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
    /// Worker health, visible to the pool.  Goes to Dead on SessionTerminated
    /// so the pool can refuse to hand out a worker with a dead session ptr.
    health: Arc<AtomicU8>,
    /// Per-topic "last deactivated warning" timestamp so we don't spam the
    /// event stream if a topic stays in streams-inactive state for a while.
    last_streams_warn_us: std::collections::HashMap<SlabKey, i64>,
    /// Pending async `open_service` calls keyed by the CID we generated.
    /// Value is (service name, outcome). `None` means still waiting; `Some(Ok)`
    /// means ServiceOpened arrived; `Some(Err)` means ServiceOpenFailure arrived.
    /// Populated by `ensure_service`, consumed when `handle_service_status` sees
    /// a reply with a matching CID.
    pending_service_opens: std::collections::HashMap<i64, (String, Option<Result<(), BlpError>>)>,
    /// Counter for generating unique service-open CIDs.
    next_service_open_id: i64,
}

impl SubscriptionWorker {
    fn new(
        id: usize,
        config: Arc<EngineConfig>,
        cmd_rx: mpsc::Receiver<SubscriptionCommand>,
        health: Arc<AtomicU8>,
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
            health,
            last_streams_warn_us: std::collections::HashMap::new(),
            pending_service_opens: std::collections::HashMap::new(),
            next_service_open_id: 0,
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
    ///
    /// Uses `open_service_async` + a nested dispatch loop so that in-flight
    /// `SubscriptionData` and other events continue to flow to the normal
    /// dispatch path while we wait for `ServiceOpened` / `ServiceOpenFailure`.
    /// The synchronous `open_service` would stall delivery for the full open
    /// duration (measured at 200-300ms against a local Terminal).
    fn ensure_service(&mut self, service: &str) -> Result<(), BlpError> {
        if self.open_services.contains(service) {
            return Ok(());
        }
        xbbg_log::info!(
            worker_id = self.id,
            service = service,
            "opening service on demand (async)"
        );

        self.next_service_open_id = self.next_service_open_id.wrapping_add(1);
        let cid_int = SERVICE_OPEN_CID_TAG | self.next_service_open_id;
        let cid = CorrelationId::Int(cid_int);
        self.pending_service_opens
            .insert(cid_int, (service.to_string(), None));

        if let Err(e) = self.session.open_service_async(service, &cid) {
            self.pending_service_opens.remove(&cid_int);
            return Err(e);
        }

        // Nested dispatch loop: keep other events flowing while we wait.
        let deadline =
            std::time::Instant::now() + std::time::Duration::from_millis(SERVICE_OPEN_TIMEOUT_MS);
        loop {
            // Check outcome first in case dispatch already resolved it.
            let resolved = matches!(self.pending_service_opens.get(&cid_int), Some((_, Some(_))));
            if resolved {
                let (_, outcome) = self.pending_service_opens.remove(&cid_int).unwrap();
                return outcome.unwrap();
            }
            if !self.pending_service_opens.contains_key(&cid_int) {
                return Err(BlpError::Internal {
                    detail: format!("pending service open for {} vanished", service),
                });
            }
            let now = std::time::Instant::now();
            if now >= deadline {
                self.pending_service_opens.remove(&cid_int);
                return Err(BlpError::Timeout);
            }
            let poll_ms = deadline.saturating_duration_since(now).as_millis().min(200) as u32;
            if let Ok(ev) = self.session.next_event(Some(poll_ms.max(1))) {
                self.dispatch_event(ev);
            }
        }
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
                        all_fields,
                        options,
                        flush_threshold,
                        overflow_policy,
                        stream,
                        status,
                        reply,
                    }) => {
                        self.status = Some(status);
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
                            all_fields,
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
                        all_fields,
                        options,
                        flush_threshold,
                        overflow_policy,
                        stream,
                        status,
                        reply,
                    }) => {
                        self.status = Some(status);
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
                            all_fields,
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
            if let Ok(ev) = self.session.next_event(Some(10)) {
                self.dispatch_event(ev);
            }

            // 3. Periodically check for long-Deactivated subscriptions so callers
            //    see "quiet, not broken" warnings while the SDK recovers.
            //    Cheap: reads topic_states; skips entirely if no status is claimed.
            if self.status.is_some() && !self.subs.is_empty() {
                self.check_streams_deactivated();
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn subscribe(
        &mut self,
        topics: Vec<String>,
        fields: Vec<String>,
        all_fields: bool,
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
                all_fields,
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
                        xbbg_log::debug!(
                            worker_id = self.id,
                            key = key,
                            reason = %reason.as_deref().unwrap_or(""),
                            "subscription started"
                        );
                        if let Some(status) = &self.status {
                            let mut status = status.lock();
                            let topic = status.mark_topic_started(key);
                            // Bloomberg sometimes includes partial-permission details in the
                            // `reason` element of SubscriptionStarted (e.g. "only delayed data
                            // authorized"). Surface it via the status event so callers see it.
                            status.record_subscription_event(
                                "SubscriptionStarted",
                                topic,
                                reason.clone(),
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
                    "SubscriptionStreamsActivated" => {
                        // Bloomberg fires this on initial subscribe success and
                        // again whenever streams come back after a temporary
                        // disconnection (per BLPAPI ChangeLog v3.11.6). This is
                        // the authoritative "data is flowing" signal.
                        self.last_streams_warn_us.remove(&key);
                        if self.subs.contains(key) {
                            if let Some(status) = &self.status {
                                let mut status = status.lock();
                                if let Some(topic) =
                                    status.topic_for_key(key).map(|t| t.to_string())
                                {
                                    let prev = status.set_topic_streams_active(&topic, true);
                                    // Only emit a status event on a real transition
                                    // (avoids spamming on the initial activation which
                                    // already fires SubscriptionStarted right before).
                                    if prev == Some(false) {
                                        status.record_subscription_event(
                                            "SubscriptionStreamsActivated",
                                            Some(topic),
                                            reason.clone(),
                                            SubscriptionEventLevel::Info,
                                        );
                                    }
                                }
                            }
                        }
                        xbbg_log::debug!(
                            worker_id = self.id,
                            key = key,
                            "subscription streams activated"
                        );
                    }
                    "SubscriptionStreamsDeactivated" => {
                        // Streams for this subscription are temporarily unavailable.
                        // The SDK will auto-recover; we just surface the state so
                        // callers polling status can tell "quiet" from "dead".
                        if self.subs.contains(key) {
                            if let Some(status) = &self.status {
                                let mut status = status.lock();
                                if let Some(topic) =
                                    status.topic_for_key(key).map(|t| t.to_string())
                                {
                                    let prev = status.set_topic_streams_active(&topic, false);
                                    if prev != Some(false) {
                                        status.record_subscription_event(
                                            "SubscriptionStreamsDeactivated",
                                            Some(topic),
                                            reason.clone(),
                                            SubscriptionEventLevel::Warning,
                                        );
                                    }
                                }
                            }
                        }
                        xbbg_log::warn!(
                            worker_id = self.id,
                            key = key,
                            reason = %reason.as_deref().unwrap_or(""),
                            "subscription streams deactivated"
                        );
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
                // Bloomberg SDK contract: SessionConnectionDown is informational.
                // The SDK's auto_restart_on_disconnection machinery handles reconnection
                // and will auto-recover active subscriptions (see BLPAPI ChangeLog v3.11.6).
                // We just record state for diagnostics; do NOT drain subscriptions and
                // do NOT resubscribe on the subsequent Up.
                let reason = extract_reason_description(msg);
                xbbg_log::warn!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    reason = %reason.as_deref().unwrap_or(""),
                    "SessionConnectionDown — informational; SDK will auto-reconnect"
                );
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Down,
                        "SessionConnectionDown",
                        reason.or_else(|| {
                            Some(format!(
                                "worker={} active_subscriptions={}",
                                self.id,
                                self.subs.len(),
                            ))
                        }),
                    );
                }
            }
            "AuthorizationRevoked" => {
                // Session identity was revoked mid-session (e.g. token expired,
                // entitlement change). Any authorized request/subscribe will now
                // fail. Treat this as terminal for the worker: we have no
                // re-auth flow, so drain subs, mark Dead, and let the pool spawn
                // a fresh worker that re-auths during startup.
                let reason = extract_reason_description(msg);
                xbbg_log::error!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    reason = %reason.as_deref().unwrap_or(""),
                    "AuthorizationRevoked — identity gone; closing subscriptions"
                );
                let keys: Vec<usize> = self.subs.iter().map(|(k, _)| k).collect();
                for key in keys {
                    let mut state = self.subs.remove(key);
                    state.mark_closing();
                    state.fail(BlpError::Internal {
                        detail: format!(
                            "Bloomberg session identity revoked (worker={}){}. \
                             Subscription closed. Please re-authenticate and resubscribe.",
                            self.id,
                            reason
                                .as_deref()
                                .map(|r| format!(": {}", r))
                                .unwrap_or_default(),
                        ),
                    });
                }
                self.clear_active_status();
                self.health
                    .store(WorkerHealth::Dead as u8, Ordering::Release);
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Terminated,
                        "AuthorizationRevoked",
                        reason.or_else(|| Some(format!("worker={}", self.id))),
                    );
                }
            }
            "SessionTerminated" => {
                let reason = extract_reason_description(msg);
                xbbg_log::error!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    reason = %reason.as_deref().unwrap_or(""),
                    "SessionTerminated — SDK gave up reconnecting; closing subscriptions"
                );
                // Session is dead. Send error to all consumers and remove all subs.
                let keys: Vec<usize> = self.subs.iter().map(|(k, _)| k).collect();
                for key in keys {
                    let mut state = self.subs.remove(key);
                    state.mark_closing();
                    state.fail(BlpError::Internal {
                        detail: format!(
                            "Bloomberg session terminated (worker={}){}. \
                             Subscription closed. Please resubscribe.",
                            self.id,
                            reason
                                .as_deref()
                                .map(|r| format!(": {}", r))
                                .unwrap_or_default(),
                        ),
                    });
                }
                self.clear_active_status();
                // Mark the worker Dead so the pool refuses to hand it out to
                // new claims — the session ptr is terminated and can't be restarted.
                self.health
                    .store(WorkerHealth::Dead as u8, Ordering::Release);
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Terminated,
                        "SessionTerminated",
                        reason.or_else(|| Some(format!("worker={}", self.id))),
                    );
                }
            }
            "SessionConnectionUp" => {
                // Informational. The SDK has re-established the TCP connection and
                // will automatically re-activate our subscriptions (per BLPAPI
                // ChangeLog v3.11.6: Subscription Streams{Activated,Deactivated}
                // events track per-subscription availability).
                let reason = extract_reason_description(msg);
                xbbg_log::info!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    reason = %reason.as_deref().unwrap_or(""),
                    "SessionConnectionUp — informational; SDK re-established the connection"
                );
                if let Some(status) = &self.status {
                    status.lock().record_session_state(
                        SessionLifecycleState::Up,
                        "SessionConnectionUp",
                        reason.or_else(|| {
                            Some(format!(
                                "worker={} active_subscriptions={}",
                                self.id,
                                self.subs.len(),
                            ))
                        }),
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

        // First: is this message a reply to one of our async open_service calls?
        if matches!(msg_type, "ServiceOpened" | "ServiceOpenFailure") {
            if let Some(CorrelationId::Int(cid_int)) = msg.correlation_id(0) {
                if self.pending_service_opens.contains_key(&cid_int) {
                    let service_name = self
                        .pending_service_opens
                        .get(&cid_int)
                        .map(|(s, _)| s.clone())
                        .unwrap_or_default();
                    match msg_type {
                        "ServiceOpened" => {
                            self.open_services.insert(service_name.clone());
                            if let Some(entry) = self.pending_service_opens.get_mut(&cid_int) {
                                entry.1 = Some(Ok(()));
                            }
                            if let Some(status) = &self.status {
                                status.lock().record_service_state(
                                    service_name,
                                    true,
                                    "ServiceOpened",
                                    Some("service opened on demand".to_string()),
                                );
                            }
                        }
                        "ServiceOpenFailure" => {
                            let reason = extract_reason_description(msg);
                            if let Some(entry) = self.pending_service_opens.get_mut(&cid_int) {
                                entry.1 = Some(Err(BlpError::OpenService {
                                    service: service_name.clone(),
                                    source: None,
                                    label: reason.clone(),
                                }));
                            }
                            if let Some(status) = &self.status {
                                status.lock().record_service_state(
                                    service_name,
                                    false,
                                    "ServiceOpenFailure",
                                    reason,
                                );
                            }
                        }
                        _ => {}
                    }
                    return;
                }
            }
        }

        let service = msg
            .elements()
            .get_by_str("serviceName")
            .and_then(|value| value.get_str(0))
            .map(str::to_string);
        if let Some(status) = &self.status {
            let mut status = status.lock();
            match msg_type {
                "ServiceDown" => {
                    let service_name = service.clone().unwrap_or_else(|| "unknown".to_string());
                    status.record_service_state(service_name.clone(), false, msg_type, None);
                    // Emit a subscription-category warning if we have active subs so
                    // callers polling subscription status (not just service status) see
                    // that their streams may be affected. The SDK will auto-recover
                    // via Streams* events; this is a loud "heads up".
                    if !self.subs.is_empty() {
                        status.record_subscription_event(
                            "ServiceDownAffectsActiveSubscriptions",
                            None,
                            Some(format!(
                                "service={} active_subscriptions={}",
                                service_name,
                                self.subs.len(),
                            )),
                            SubscriptionEventLevel::Warning,
                        );
                        xbbg_log::warn!(
                            worker_id = self.id,
                            service = %service_name,
                            active_subs = self.subs.len(),
                            "ServiceDown — active subscriptions may be silently quieted"
                        );
                    }
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

    /// Check if any topics are in streams-deactivated state longer than the configured
    /// warn threshold and emit a one-shot Warning event so callers polling status
    /// see "your data is quiet, not broken — SDK is still trying to recover".
    fn check_streams_deactivated(&mut self) {
        let warn_ms = self.config.streams_deactivated_warn_ms;
        if warn_ms == 0 {
            return;
        }
        let Some(status_arc) = self.status.clone() else {
            return;
        };

        let now = super::timestamp_now_us();
        let warn_us = (warn_ms as i64) * 1_000;

        // Collect keys to warn about without holding the status lock across the warn emission.
        let mut to_warn: Vec<(SlabKey, String, i64)> = Vec::new();
        {
            let status = status_arc.lock();
            for (topic, info) in status.topic_statuses().iter() {
                if info.streams_active {
                    continue;
                }
                // Only warn for topics that have actually been deactivated (not pre-streaming).
                if info.streams_changed_us == 0 {
                    continue;
                }
                let elapsed = now - info.streams_changed_us;
                if elapsed < warn_us {
                    continue;
                }
                // Map back to slab key for debouncing.
                if let Some(&key) = status.topic_to_key().get(topic) {
                    let last_warn = self.last_streams_warn_us.get(&key).copied().unwrap_or(0);
                    if now - last_warn >= warn_us {
                        to_warn.push((key, topic.clone(), elapsed));
                    }
                }
            }
        }

        if to_warn.is_empty() {
            return;
        }

        let mut status = status_arc.lock();
        for (key, topic, elapsed_us) in to_warn {
            self.last_streams_warn_us.insert(key, now);
            let detail = format!(
                "topic has been streams-inactive for {}ms; SDK is still trying to recover",
                elapsed_us / 1_000
            );
            xbbg_log::warn!(
                worker_id = self.id,
                topic = %topic,
                elapsed_ms = elapsed_us / 1_000,
                "subscription streams still deactivated"
            );
            status.record_subscription_event(
                "SubscriptionStreamsDeactivatedPersisting",
                Some(topic),
                Some(detail),
                SubscriptionEventLevel::Warning,
            );
        }
    }
}

fn extract_reason_description(msg: &xbbg_core::Message<'_>) -> Option<String> {
    let reason = msg.elements().get_by_str("reason")?;
    for key in ["description", "category", "message"] {
        if let Some(s) = reason.get_by_str(key).and_then(|e| e.get_str(0)) {
            return Some(s.to_string());
        }
    }
    None
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
        all_fields: bool,
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
                all_fields,
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
        all_fields: bool,
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
                all_fields,
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

    /// Best-effort unsubscribe for non-async drop paths.
    fn try_unsubscribe(
        &self,
        keys: Vec<SlabKey>,
    ) -> Result<(), mpsc::error::TrySendError<SubscriptionCommand>> {
        self.cmd_tx
            .try_send(SubscriptionCommand::Unsubscribe { keys })
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
    health: Arc<AtomicU8>,
}

impl SubscriptionWorkerHandle {
    fn spawn(id: usize, config: Arc<EngineConfig>) -> Result<Self, BlpError> {
        let (cmd_tx, cmd_rx) = mpsc::channel(config.command_queue_size);
        let (startup_tx, startup_rx) = std::sync::mpsc::channel();
        let health = Arc::new(AtomicU8::new(WorkerHealth::Healthy as u8));

        let config_clone = config.clone();
        let worker_health = health.clone();
        let thread = thread::Builder::new()
            .name(format!("xbbg-sub-{}", id))
            .spawn(move || {
                match SubscriptionWorker::new(id, config_clone, cmd_rx, worker_health) {
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
            health,
        })
    }

    pub fn health(&self) -> WorkerHealth {
        match self.health.load(Ordering::Acquire) {
            0 => WorkerHealth::Healthy,
            1 => WorkerHealth::Degraded,
            2 => WorkerHealth::Dead,
            _ => WorkerHealth::Dead,
        }
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
    /// Skips workers whose session has gone terminal (SessionTerminated → Dead).
    /// Spawns a fresh replacement if the pool is exhausted or every available
    /// handle is Dead. Dead handles are dropped on the way out.
    ///
    /// Takes `Arc<Self>` to allow `SessionClaim` to have a `'static` lifetime.
    pub fn claim(self: &Arc<Self>) -> Result<SessionClaim, BlpAsyncError> {
        let handle = {
            let mut available = self.available.lock();
            // Find a live handle, dropping Dead ones along the way so the pool
            // doesn't accumulate corpses.
            let mut chosen: Option<SubscriptionWorkerHandle> = None;
            while let Some(candidate) = available.pop() {
                if candidate.health() == WorkerHealth::Dead {
                    xbbg_log::warn!(
                        worker_id = candidate.id(),
                        "discarding dead subscription worker (SessionTerminated)"
                    );
                    // Drop discards the handle; its thread exits via mpsc disconnect.
                    drop(candidate);
                    continue;
                }
                chosen = Some(candidate);
                break;
            }
            if let Some(handle) = chosen {
                xbbg_log::debug!(
                    worker_id = handle.id(),
                    remaining = available.len(),
                    "claimed session from pool"
                );
                handle
            } else {
                drop(available); // Release lock before creating new worker

                let new_id = self.next_id.fetch_add(1, Ordering::Relaxed);
                xbbg_log::warn!(
                    worker_id = new_id,
                    initial_size = self.initial_size,
                    "subscription pool exhausted or all dead, creating new session"
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
            cleanup_status: None,
        })
    }

    /// Release a session back to the pool. Dead handles are dropped instead of
    /// being returned so subsequent claims can't land on them.
    fn release(&self, handle: SubscriptionWorkerHandle) {
        if handle.health() == WorkerHealth::Dead {
            xbbg_log::warn!(
                worker_id = handle.id(),
                "discarding dead subscription worker on release (SessionTerminated)"
            );
            drop(handle);
            return;
        }
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
    cleanup_status: Option<SharedSubscriptionStatus>,
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
        all_fields: bool,
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
                all_fields,
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
        all_fields: bool,
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
                all_fields,
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

    /// Attach active-topic status so dropping a raw claim can clean up safely.
    pub fn set_cleanup_status(&mut self, status: SharedSubscriptionStatus) {
        self.cleanup_status = Some(status);
    }

    /// Best-effort cleanup for non-async stream drop/close paths.
    ///
    /// Because Drop cannot await Bloomberg's termination confirmations, a claim
    /// released through this path must not return its worker to the reusable pool.
    pub fn close_without_reuse(mut self, keys: Vec<SlabKey>) {
        if let Some(handle) = self.handle.take() {
            if !keys.is_empty() {
                match handle.command.try_unsubscribe(keys) {
                    Ok(()) => {}
                    Err(mpsc::error::TrySendError::Full(_)) => {
                        xbbg_log::warn!(
                            worker_id = handle.id(),
                            "subscription cleanup command queue full; discarding worker"
                        );
                    }
                    Err(mpsc::error::TrySendError::Closed(_)) => {}
                }
            }
            handle.signal_shutdown();
            drop(handle);
        }
    }

    /// Get the worker ID.
    pub fn worker_id(&self) -> Option<usize> {
        self.handle.as_ref().map(SubscriptionWorkerHandle::id)
    }
}

impl Drop for SessionClaim {
    fn drop(&mut self) {
        let Some(handle) = self.handle.take() else {
            return;
        };

        let active_keys = self
            .cleanup_status
            .as_ref()
            .map(|status| status.lock().keys().to_vec())
            .unwrap_or_default();

        if active_keys.is_empty() {
            self.pool.release(handle);
            return;
        }

        match handle.command.try_unsubscribe(active_keys) {
            Ok(()) => {}
            Err(mpsc::error::TrySendError::Full(_)) => {
                xbbg_log::warn!(
                    worker_id = handle.id(),
                    "subscription cleanup command queue full; discarding worker"
                );
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {}
        }
        if let Some(status) = &self.cleanup_status {
            status.lock().clear_active();
        }
        handle.signal_shutdown();
        drop(handle);
    }
}

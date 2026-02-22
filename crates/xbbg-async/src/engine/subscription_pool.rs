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
use tokio::sync::mpsc;

use xbbg_core::session::Session;
use xbbg_core::{BlpError, CorrelationId, EventType, SessionOptions, SubscriptionList};

use super::state::{SubscriptionMetrics, SubscriptionState};
use super::{BlpAsyncError, EngineConfig, OverflowPolicy, SlabKey};

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
        /// Reply with slab keys for later unsubscribe.
        reply: tokio::sync::oneshot::Sender<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>)>,
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
        /// Reply with new slab keys.
        reply: tokio::sync::oneshot::Sender<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>)>,
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
}

impl SubscriptionWorker {
    fn new(
        id: usize,
        config: Arc<EngineConfig>,
        cmd_rx: mpsc::Receiver<SubscriptionCommand>,
    ) -> Result<Self, BlpError> {
        let mut opts = SessionOptions::new()?;
        opts.set_server_host(&config.server_host)?;
        opts.set_server_port(config.server_port);
        opts.set_max_event_queue_size(config.max_event_queue_size);
        let _ = opts.set_bandwidth_save_mode_disabled(true);
        opts.set_record_subscription_receive_times(true);
        opts.set_auto_restart_on_disconnection(true);

        let session = Session::new(&opts)?;
        session.start()?;

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
        })
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
                        reply,
                    }) => {
                        // Ensure service is open
                        if let Err(e) = self.ensure_service(&service) {
                            xbbg_log::error!(worker_id = self.id, service = %service, error = %e, "failed to open service");
                            let _ = reply.send((vec![], vec![]));
                            continue;
                        }
                        let (keys, metrics) = self.subscribe(
                            topics,
                            fields,
                            options,
                            flush_threshold,
                            overflow_policy,
                            stream,
                        );
                        let _ = reply.send((keys, metrics));
                    }
                    Ok(SubscriptionCommand::AddTopics {
                        service,
                        topics,
                        fields,
                        options,
                        flush_threshold,
                        overflow_policy,
                        stream,
                        reply,
                    }) => {
                        // Ensure service is open
                        if let Err(e) = self.ensure_service(&service) {
                            xbbg_log::error!(worker_id = self.id, service = %service, error = %e, "failed to open service");
                            let _ = reply.send((vec![], vec![]));
                            continue;
                        }
                        // AddTopics uses the same logic as Subscribe
                        let (keys, metrics) = self.subscribe(
                            topics,
                            fields,
                            options,
                            flush_threshold,
                            overflow_policy,
                            stream,
                        );
                        let _ = reply.send((keys, metrics));
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
    ) -> (Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>) {
        let mut sub_list = SubscriptionList::new();

        let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();
        let options_str = options.join(",");
        let mut keys = Vec::with_capacity(topics.len());
        let mut metrics: Vec<Arc<SubscriptionMetrics>> = Vec::with_capacity(topics.len());
        let ft = flush_threshold.unwrap_or(self.config.subscription_flush_threshold);
        let op = overflow_policy.unwrap_or(self.config.overflow_policy);

        for topic in &topics {
            let state = SubscriptionState::with_policy(topic.clone(), fields.clone(), stream.clone(), ft, op);
            let metrics_arc = state.metrics.clone();
            let key = self.subs.insert(state);

            let cid = CorrelationId::Int(key as i64);
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
            return (keys, metrics);
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
            return (vec![], vec![]);
        }

        (keys, metrics)
    }

    fn unsubscribe(&mut self, keys: Vec<SlabKey>) {
        // Build a SubscriptionList with correlation IDs so Bloomberg stops sending data.
        // Without this, the SDK continues delivering events for removed subscriptions,
        // wasting bandwidth and risking stale correlation ID reuse.
        let mut unsub_list = SubscriptionList::new();
        let mut unsub_count = 0usize;
        for &key in &keys {
            if self.subs.contains(key) {
                let state = &self.subs[key];
                let cid = CorrelationId::Int(key as i64);
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
                _ => {}
            }
        }
    }

    fn handle_subscription_data(&mut self, msg: &xbbg_core::Message<'_>) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::Int(key)) = msg.correlation_id(i) {
                // Skip in-flight data for subscriptions we've already cancelled.
                if self.pending_cancel.contains(&(key as usize)) {
                    continue;
                }
                if let Some(state) = self.subs.get_mut(key as usize) {
                    // Check for DATALOSS
                    let elem = msg.elements();
                    if let Some(event_type) = elem.get_by_str("MKTDATA_EVENT_TYPE") {
                        if let Some(val) = event_type.get_str(0) {
                            if val == "SUMMARY" {
                                if let Some(subtype) = elem.get_by_str("MKTDATA_EVENT_SUBTYPE") {
                                    if let Some(sub_val) = subtype.get_str(0) {
                                        if sub_val == "DATALOSS" {
                                            state.on_dataloss();
                                            continue;
                                        }
                                    }
                                }
                            }
                        }
                    }

                    state.on_message(msg);
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
            if let Some(CorrelationId::Int(key)) = msg.correlation_id(i) {
                match msg_type {
                    "SubscriptionStarted" => {
                        xbbg_log::debug!(worker_id = self.id, key = key, "subscription started");
                    }
                    "SubscriptionFailure" => {
                        if self.pending_cancel.remove(&(key as usize)) {
                            // Bloomberg sends SubscriptionFailure (instead of SubscriptionTerminated)
                            // when a subscription is cancelled before it fully starts. Since this was
                            // explicitly requested via unsubscribe(), silently clean up.
                            if self.subs.contains(key as usize) {
                                self.subs.remove(key as usize);
                            }
                            xbbg_log::debug!(
                                worker_id = self.id,
                                key = key,
                                "pending cancel confirmed via SubscriptionFailure"
                            );
                        } else {
                            // Genuine subscription failure — propagate as an error.
                            xbbg_log::error!(worker_id = self.id, key = key, reason = ?reason, "subscription failed");
                            if self.subs.contains(key as usize) {
                                let state = self.subs.remove(key as usize);
                                state.fail(BlpError::SubscriptionFailure {
                                    cid: Some(xbbg_core::errors::CorrelationContext::U64(
                                        key as u64,
                                    )),
                                    label: reason.clone(),
                                });
                            }
                        }
                    }
                    "SubscriptionTerminated" => {
                        if self.pending_cancel.remove(&(key as usize)) {
                            // This termination was explicitly requested via unsubscribe().
                            // Silently clean up the slab entry — don't propagate an error.
                            if self.subs.contains(key as usize) {
                                self.subs.remove(key as usize);
                            }
                            xbbg_log::debug!(
                                worker_id = self.id,
                                key = key,
                                "pending cancel confirmed by Bloomberg"
                            );
                        } else {
                            // Unexpected termination — propagate as an error.
                            xbbg_log::info!(worker_id = self.id, key = key, reason = ?reason, "subscription terminated unexpectedly");
                            if self.subs.contains(key as usize) {
                                let state = self.subs.remove(key as usize);
                                state.fail(BlpError::SubscriptionFailure {
                                    cid: Some(xbbg_core::errors::CorrelationContext::U64(
                                        key as u64,
                                    )),
                                    label: reason
                                        .clone()
                                        .or_else(|| Some("subscription terminated".to_string())),
                                });
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
            }
            "SessionConnectionDown" => {
                xbbg_log::error!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    "session connection down — SDK may attempt reconnect"
                );
                // Don't remove subs yet — SDK may auto-reconnect.
                // But notify all consumers that the connection dropped.
                for (key, state) in &self.subs {
                    state.fail(BlpError::Internal {
                        detail: format!(
                            "Bloomberg session connection lost (worker={}, sub={}). \
                             Data may be stale until reconnection.",
                            self.id, key,
                        ),
                    });
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
                    let state = self.subs.remove(key);
                    state.fail(BlpError::Internal {
                        detail: format!(
                            "Bloomberg session terminated (worker={}). \
                             Subscription closed. Please resubscribe.",
                            self.id,
                        ),
                    });
                }
            }
            "SessionConnectionUp" => {
                xbbg_log::info!(
                    worker_id = self.id,
                    active_subs = self.subs.len(),
                    "session connection restored"
                );
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

/// Handle to a subscription worker.
pub struct SubscriptionWorkerHandle {
    pub id: usize,
    pub cmd_tx: mpsc::Sender<SubscriptionCommand>,
    thread: Option<JoinHandle<()>>,
}

impl SubscriptionWorkerHandle {
    fn spawn(id: usize, config: Arc<EngineConfig>) -> Result<Self, BlpError> {
        let (cmd_tx, cmd_rx) = mpsc::channel(config.command_queue_size);

        let config_clone = config.clone();
        let thread = thread::Builder::new()
            .name(format!("xbbg-sub-{}", id))
            .spawn(move || {
                match SubscriptionWorker::new(id, config_clone, cmd_rx) {
                    Ok(mut worker) => {
                        if let Err(e) = worker.run() {
                            xbbg_log::error!(worker_id = id, error = %e, "subscription worker error");
                        }
                    }
                    Err(e) => {
                        xbbg_log::error!(worker_id = id, error = %e, "subscription worker creation failed");
                    }
                }
            })
            .map_err(|e| BlpError::Internal {
                detail: format!("failed to spawn subscription worker: {}", e),
            })?;

        Ok(Self {
            id,
            cmd_tx,
            thread: Some(thread),
        })
    }

    /// Signal shutdown without waiting (non-blocking).
    fn signal_shutdown(&self) {
        let _ = self.cmd_tx.try_send(SubscriptionCommand::Shutdown);
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
                    worker_id = handle.id,
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
            worker_id = handle.id,
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
/// Uses `Arc` internally for `'static` lifetime (required for PyO3).
pub struct SessionClaim {
    handle: Option<SubscriptionWorkerHandle>,
    pool: Arc<SubscriptionSessionPool>,
}

impl SessionClaim {
    /// Subscribe to topics on this session.
    ///
    /// # Arguments
    /// * `service` - Bloomberg service (e.g., "//blp/mktdata", "//blp/mktvwap")
    /// * `topics` - Securities to subscribe to
    /// * `fields` - Fields to subscribe to
    /// * `options` - Subscription options (e.g., ["VWAP_START_TIME=09:30"])
    /// * `stream` - Channel to send data batches (or errors) to
    pub async fn subscribe(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpAsyncError> {
        let handle = self
            .handle
            .as_ref()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "session already released".to_string(),
            })?;

        let (reply_tx, reply_rx) = tokio::sync::oneshot::channel();

        handle
            .cmd_tx
            .send(SubscriptionCommand::Subscribe {
                service,
                topics,
                fields,
                options,
                flush_threshold,
                overflow_policy,
                stream,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx.await.map_err(|_| BlpAsyncError::ChannelClosed)
    }

    /// Add topics to an existing subscription.
    pub async fn add_topics(
        &self,
        service: String,
        topics: Vec<String>,
        fields: Vec<String>,
        options: Vec<String>,
        flush_threshold: Option<usize>,
        overflow_policy: Option<OverflowPolicy>,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    ) -> Result<(Vec<SlabKey>, Vec<Arc<SubscriptionMetrics>>), BlpAsyncError> {
        let handle = self
            .handle
            .as_ref()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "session already released".to_string(),
            })?;

        let (reply_tx, reply_rx) = tokio::sync::oneshot::channel();

        handle
            .cmd_tx
            .send(SubscriptionCommand::AddTopics {
                service,
                topics,
                fields,
                options,
                flush_threshold,
                overflow_policy,
                stream,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx.await.map_err(|_| BlpAsyncError::ChannelClosed)
    }

    /// Unsubscribe from topics on this session.
    pub async fn unsubscribe(&self, keys: Vec<SlabKey>) -> Result<(), BlpAsyncError> {
        let handle = self
            .handle
            .as_ref()
            .ok_or_else(|| BlpAsyncError::ConfigError {
                detail: "session already released".to_string(),
            })?;

        handle
            .cmd_tx
            .send(SubscriptionCommand::Unsubscribe { keys })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        Ok(())
    }

    /// Get the worker ID.
    pub fn worker_id(&self) -> Option<usize> {
        self.handle.as_ref().map(|h| h.id)
    }
}

impl Drop for SessionClaim {
    fn drop(&mut self) {
        if let Some(handle) = self.handle.take() {
            self.pool.release(handle);
        }
    }
}

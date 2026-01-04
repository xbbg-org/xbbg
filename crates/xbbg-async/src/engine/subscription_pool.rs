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

use super::state::SubscriptionState;
use super::{BlpAsyncError, EngineConfig, SlabKey};

/// Commands sent to a subscription worker.
pub enum SubscriptionCommand {
    /// Start a subscription.
    Subscribe {
        topics: Vec<String>,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
        /// Reply with slab keys for later unsubscribe.
        reply: tokio::sync::oneshot::Sender<Vec<SlabKey>>,
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

        let session = Session::new(&opts)?;
        session.start()?;

        // Pre-open the mktdata service
        session.open_service("//blp/mktdata")?;

        tracing::info!(worker_id = id, "subscription worker pre-warmed");

        Ok(Self {
            id,
            session,
            subs: Slab::new(),
            cmd_rx,
            config,
        })
    }

    fn run(&mut self) -> Result<(), BlpError> {
        tracing::info!(worker_id = self.id, "SubscriptionWorker started");

        loop {
            // 1. Drain commands (non-blocking)
            loop {
                match self.cmd_rx.try_recv() {
                    Ok(SubscriptionCommand::Shutdown) => {
                        tracing::info!(worker_id = self.id, "SubscriptionWorker shutting down");
                        return Ok(());
                    }
                    Ok(SubscriptionCommand::Subscribe {
                        topics,
                        fields,
                        stream,
                        reply,
                    }) => {
                        let keys = self.subscribe(topics, fields, stream);
                        let _ = reply.send(keys);
                    }
                    Ok(SubscriptionCommand::Unsubscribe { keys }) => {
                        self.unsubscribe(keys);
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

    fn subscribe(
        &mut self,
        topics: Vec<String>,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
    ) -> Vec<SlabKey> {
        let mut sub_list = match SubscriptionList::new() {
            Ok(list) => list,
            Err(e) => {
                tracing::error!(worker_id = self.id, error = %e, "failed to create subscription list");
                return vec![];
            }
        };

        let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();
        let mut keys = Vec::with_capacity(topics.len());

        for topic in &topics {
            let state = SubscriptionState::with_policy(
                topic.clone(),
                fields.clone(),
                stream.clone(),
                self.config.subscription_flush_threshold,
                self.config.overflow_policy,
            );
            let key = self.subs.insert(state);
            keys.push(key);

            let cid = CorrelationId::U64(key as u64);
            if let Err(e) = sub_list.add(topic, &field_refs, Some(&cid)) {
                tracing::error!(worker_id = self.id, topic = %topic, error = %e, "failed to add topic");
            }

            tracing::debug!(worker_id = self.id, topic = %topic, key = key, "subscription added");
        }

        if let Err(e) = self.session.subscribe(&sub_list, None) {
            tracing::error!(worker_id = self.id, error = %e, "subscribe failed");
        }

        keys
    }

    fn unsubscribe(&mut self, keys: Vec<SlabKey>) {
        for key in keys {
            if self.subs.contains(key) {
                self.subs.remove(key);
                tracing::debug!(worker_id = self.id, key = key, "subscription removed");
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

    fn handle_subscription_data(&mut self, msg: &xbbg_core::MessageRef) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                if let Some(state) = self.subs.get_mut(key as usize) {
                    // Check for DATALOSS
                    let elem = msg.elements();
                    if let Some(event_type) = elem.get_element("MKTDATA_EVENT_TYPE") {
                        if let Some(val) = event_type.get_value_as_string(0) {
                            if val == "SUMMARY" {
                                if let Some(subtype) = elem.get_element("MKTDATA_EVENT_SUBTYPE") {
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

                    state.on_message(msg);
                }
            }
        }
    }

    fn handle_subscription_status(&mut self, msg: &xbbg_core::MessageRef) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        let n = msg.num_correlation_ids();

        for i in 0..n {
            if let Some(CorrelationId::U64(key)) = msg.correlation_id(i as usize) {
                match msg_type {
                    "SubscriptionStarted" => {
                        tracing::debug!(worker_id = self.id, key = key, "subscription started");
                    }
                    "SubscriptionFailure" => {
                        tracing::error!(worker_id = self.id, key = key, "subscription failed");
                        if self.subs.contains(key as usize) {
                            self.subs.remove(key as usize);
                        }
                    }
                    "SubscriptionTerminated" => {
                        tracing::info!(worker_id = self.id, key = key, "subscription terminated");
                        if self.subs.contains(key as usize) {
                            self.subs.remove(key as usize);
                        }
                    }
                    _ => {
                        tracing::trace!(
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
                            tracing::error!(worker_id = id, error = %e, "subscription worker error");
                        }
                    }
                    Err(e) => {
                        tracing::error!(worker_id = id, error = %e, "subscription worker creation failed");
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

    fn shutdown(&mut self) {
        let _ = self.cmd_tx.try_send(SubscriptionCommand::Shutdown);
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

impl Drop for SubscriptionWorkerHandle {
    fn drop(&mut self) {
        self.shutdown();
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
        tracing::info!(pool_size = size, "creating subscription session pool");

        let mut available = Vec::with_capacity(size);
        for id in 0..size {
            let handle = SubscriptionWorkerHandle::spawn(id, config.clone()).map_err(|e| {
                BlpAsyncError::BlpError(BlpError::Internal {
                    detail: format!("failed to spawn subscription worker {}: {}", id, e),
                })
            })?;
            available.push(handle);
        }

        tracing::info!(pool_size = size, "subscription session pool ready");

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
    pub fn claim(&self) -> Result<SessionClaim<'_>, BlpAsyncError> {
        let handle = {
            let mut available = self.available.lock();
            if let Some(handle) = available.pop() {
                tracing::debug!(
                    worker_id = handle.id,
                    remaining = available.len(),
                    "claimed session from pool"
                );
                handle
            } else {
                drop(available); // Release lock before creating new worker

                // Pool exhausted - create new session dynamically
                let new_id = self.next_id.fetch_add(1, Ordering::Relaxed);
                tracing::warn!(
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
            pool: self,
        })
    }

    /// Release a session back to the pool.
    fn release(&self, handle: SubscriptionWorkerHandle) {
        let mut available = self.available.lock();
        tracing::debug!(
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

    /// Graceful shutdown of all workers.
    pub fn shutdown(&self) {
        let mut available = self.available.lock();
        tracing::info!(count = available.len(), "shutting down subscription pool");
        for handle in available.drain(..) {
            drop(handle); // Drop triggers shutdown
        }
    }
}

impl Drop for SubscriptionSessionPool {
    fn drop(&mut self) {
        self.shutdown();
    }
}

/// Handle to a claimed session.
///
/// Releases the session back to the pool on drop.
pub struct SessionClaim<'a> {
    handle: Option<SubscriptionWorkerHandle>,
    pool: &'a SubscriptionSessionPool,
}

impl<'a> SessionClaim<'a> {
    /// Subscribe to topics on this session.
    pub async fn subscribe(
        &self,
        topics: Vec<String>,
        fields: Vec<String>,
        stream: mpsc::Sender<RecordBatch>,
    ) -> Result<Vec<SlabKey>, BlpAsyncError> {
        let handle = self.handle.as_ref().ok_or_else(|| BlpAsyncError::ConfigError {
            detail: "session already released".to_string(),
        })?;

        let (reply_tx, reply_rx) = tokio::sync::oneshot::channel();

        handle
            .cmd_tx
            .send(SubscriptionCommand::Subscribe {
                topics,
                fields,
                stream,
                reply: reply_tx,
            })
            .await
            .map_err(|_| BlpAsyncError::ChannelClosed)?;

        reply_rx.await.map_err(|_| BlpAsyncError::ChannelClosed)
    }

    /// Unsubscribe from topics on this session.
    pub async fn unsubscribe(&self, keys: Vec<SlabKey>) -> Result<(), BlpAsyncError> {
        let handle = self.handle.as_ref().ok_or_else(|| BlpAsyncError::ConfigError {
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

impl<'a> Drop for SessionClaim<'a> {
    fn drop(&mut self) {
        if let Some(handle) = self.handle.take() {
            self.pool.release(handle);
        }
    }
}

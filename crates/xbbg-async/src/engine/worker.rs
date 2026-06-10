//! Unified request worker for all Bloomberg request types.
//!
//! Workers run Bloomberg sessions in **asynchronous (event-handler) mode**:
//! the SDK delivers events by invoking [`WorkerShared::dispatch_event`] on an
//! SDK dispatcher thread, and submitters call `sendRequest` / `cancel`
//! directly from their own threads — async sessions are the SDK's documented
//! multi-threaded mode (see [`xbbg_core::async_session`]). There is no
//! command queue and no poll loop: request dispatch latency is bounded by
//! the SDK, not by a poll quantum, and an idle worker costs zero wakeups.
//!
//! Request state lives in a slab shared between submitters and the
//! dispatcher callback. Slots are generation-tagged (see
//! [`super::dispatch::DispatchKey`]); state is registered **before**
//! `sendRequest` because in async mode the response can reach the handler
//! before the submitting call returns (blpapi_session.h:490-495).
//!
//! Handled request/response patterns:
//! - Reference data (bdp)
//! - Historical data (bdh)
//! - Bulk data (bds)
//! - Intraday bars (bdib)
//! - Intraday ticks (bdtick)
//! - Field info queries

use std::collections::hash_map::Entry;
use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicBool, AtomicI64, AtomicU32, AtomicU8, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use arrow_array::RecordBatch;
use parking_lot::{Condvar, Mutex, RwLock};
use slab::Slab;
use tokio::sync::{mpsc, oneshot};

use xbbg_core::{AsyncSession, BlpError, CorrelationId, EventType};

/// Max wall time we'll wait for an async open_service reply.
const SERVICE_OPEN_TIMEOUT_MS: u64 = 10_000;

/// Threshold for warning about slow Bloomberg responses (30 seconds).
const SLOW_REQUEST_WARN_THRESHOLD: Duration = Duration::from_secs(30);

use super::dispatch::{DispatchKey, SERVICE_OPEN_CID_TAG};
use super::state::{
    BqlState, BsrchState, BulkDataState, FieldInfoState, GenericState, HistDataState,
    HistDataStreamState, IntradayBarState, IntradayBarStreamState, IntradayTickState,
    IntradayTickStreamState, RefDataState,
};
use super::{
    attach_auth_context, build_session_options, EngineConfig, PlannedRequestShape, PreparedRequest,
    RequestParams, SlabKey, WorkerHealth, SESSION_STARTUP_TIMEOUT_MS,
};

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

fn apply_excel_grid_request_parameters(
    request: &mut xbbg_core::Request,
    params: &RequestParams,
) -> Result<(), BlpError> {
    if let Some(domain) = params
        .elements
        .iter()
        .flat_map(|pairs| pairs.iter())
        .rev()
        .find(|(name, _)| name.eq_ignore_ascii_case("Domain"))
        .map(|(_, value)| value.as_str())
    {
        request.set_str("Domain", domain)?;
    }

    let Some(overrides) = params
        .overrides
        .as_ref()
        .filter(|values| !values.is_empty())
    else {
        return Ok(());
    };

    let overrides_ptr = request.get_or_create_element("Overrides")?;
    for (name, value) in overrides {
        if name.is_empty() {
            continue;
        }
        // SAFETY: overrides_ptr is a valid element obtained from get_or_create_element;
        // entry_ptr is valid from append_element and belongs to this request.
        let entry_ptr = unsafe { request.append_element(overrides_ptr)? };
        unsafe { request.set_element_string(entry_ptr, "name", name)? };
        unsafe { request.set_element_string(entry_ptr, "value", value)? };
    }

    Ok(())
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

fn send_stream_error(stream: mpsc::Sender<Result<RecordBatch, BlpError>>, error: BlpError) {
    let _ = stream.blocking_send(Err(error));
}

/// Identifies one in-flight request on a specific worker: slab slot plus the
/// generation encoded into its correlation ID. Required for cancellation.
#[derive(Clone, Copy, Debug)]
pub(crate) struct RequestTicket {
    pub(crate) key: SlabKey,
    pub(crate) generation: u32,
}

/// One in-flight request slot.
struct RequestSlot {
    /// Generation encoded into this request's correlation ID.
    generation: u32,
    /// When the request was registered (just before `sendRequest`).
    sent_at: Instant,
    /// Whether the slow-request warning has fired for this slot.
    warned: bool,
    state: UnifiedRequestState,
}

/// A pending async `open_service` call plus everyone awaiting its outcome.
struct PendingServiceOpen {
    cid: i64,
    waiters: Vec<oneshot::Sender<Result<(), BlpError>>>,
}

/// Session startup outcome latch, resolved exactly once by the first
/// startup-relevant SESSION_STATUS message.
#[derive(Default)]
struct StartupLatch {
    resolved: bool,
    result: Option<Result<(), BlpError>>,
}

/// State shared between submitter threads and the SDK dispatcher callback.
pub(super) struct WorkerShared {
    id: usize,
    /// Slab for O(1) correlation dispatch. Slots carry the generation tag
    /// encoded into the request's correlation ID so dispatch can reject
    /// stale messages after a slot is recycled.
    requests: Mutex<Slab<RequestSlot>>,
    /// Wrapping generation counter encoded into request dispatch CIDs.
    next_generation: AtomicU32,
    /// Services opened on this worker's session.
    open_services: RwLock<HashSet<String>>,
    /// Pending async `open_service` calls keyed by service name; resolved by
    /// `handle_service_status` matching on the open's correlation ID.
    pending_service_opens: Mutex<HashMap<String, PendingServiceOpen>>,
    /// Counter for generating unique service-open CIDs.
    next_service_open_id: AtomicI64,
    startup: Mutex<StartupLatch>,
    startup_cv: Condvar,
    health: Arc<AtomicU8>,
    /// Set before an intentional stop so terminal SDK status events are logged
    /// as normal teardown instead of unexpected worker death.
    shutting_down: AtomicBool,
}

impl WorkerShared {
    fn new(id: usize, health: Arc<AtomicU8>) -> Self {
        Self {
            id,
            requests: Mutex::new(Slab::new()),
            next_generation: AtomicU32::new(0),
            open_services: RwLock::new(HashSet::new()),
            pending_service_opens: Mutex::new(HashMap::new()),
            next_service_open_id: AtomicI64::new(0),
            startup: Mutex::new(StartupLatch::default()),
            startup_cv: Condvar::new(),
            health,
            shutting_down: AtomicBool::new(false),
        }
    }

    /// Next wrapping generation tag for request dispatch CIDs.
    fn next_generation(&self) -> u32 {
        self.next_generation
            .fetch_add(1, Ordering::Relaxed)
            .wrapping_add(1)
    }

    fn insert_slot(&self, generation: u32, state: UnifiedRequestState) -> SlabKey {
        self.requests.lock().insert(RequestSlot {
            generation,
            sent_at: Instant::now(),
            warned: false,
            state,
        })
    }

    /// Remove and return the slot addressed by `dispatch_key` iff its
    /// generation matches; stale keys (recycled slots) are dropped.
    fn take_slot(&self, dispatch_key: DispatchKey) -> Option<RequestSlot> {
        let key = dispatch_key.to_slab_key();
        let mut requests = self.requests.lock();
        match requests.get(key) {
            Some(slot) if slot.generation == dispatch_key.generation() => {
                Some(requests.remove(key))
            }
            Some(_) => {
                xbbg_log::debug!(
                    worker_id = self.id,
                    key = key,
                    "stale message for recycled slot; dropped"
                );
                None
            }
            None => None,
        }
    }

    fn resolve_startup(&self, result: Result<(), BlpError>) {
        let mut latch = self.startup.lock();
        if !latch.resolved {
            latch.resolved = true;
            latch.result = Some(result);
            self.startup_cv.notify_all();
        }
    }

    /// Block until the first startup-relevant status arrives (or `timeout`).
    fn wait_startup(&self, timeout: Duration) -> Result<(), BlpError> {
        let deadline = Instant::now() + timeout;
        let mut latch = self.startup.lock();
        while latch.result.is_none() {
            if self.startup_cv.wait_until(&mut latch, deadline).timed_out() {
                return Err(BlpError::Timeout);
            }
        }
        latch.result.take().expect("checked above")
    }

    /// Mark expired slow requests and return hard-timeout candidates.
    pub(super) fn scan_timeouts(&self, hard_timeout: Option<Duration>) -> Vec<RequestTicket> {
        let now = Instant::now();
        let mut expired = Vec::new();
        let mut requests = self.requests.lock();
        for (key, slot) in requests.iter_mut() {
            let elapsed = now.duration_since(slot.sent_at);
            if elapsed > SLOW_REQUEST_WARN_THRESHOLD && !slot.warned {
                slot.warned = true;
                xbbg_log::warn!(
                    worker_id = self.id,
                    request_key = key,
                    elapsed_secs = elapsed.as_secs(),
                    "request outstanding longer than expected; still waiting on Bloomberg"
                );
            }
            if let Some(hard) = hard_timeout {
                if elapsed >= hard {
                    expired.push(RequestTicket {
                        key,
                        generation: slot.generation,
                    });
                }
            }
        }
        expired
    }

    fn drain_in_flight(&self, reason: &str) {
        let drained: Vec<RequestSlot> = {
            let mut requests = self.requests.lock();
            requests.drain().collect()
        };
        if drained.is_empty() {
            return;
        }
        let count = drained.len();
        for slot in drained {
            slot.state.fail(BlpError::Internal {
                detail: format!("{} (worker={})", reason, self.id),
            });
        }
        xbbg_log::error!(
            worker_id = self.id,
            drained = count,
            reason = reason,
            "drained in-flight requests"
        );
    }

    fn fail_pending_service_opens(&self, reason: &str) {
        let drained: Vec<(String, PendingServiceOpen)> = {
            let mut pending = self.pending_service_opens.lock();
            pending.drain().collect()
        };
        for (service, open) in drained {
            for waiter in open.waiters {
                let _ = waiter.send(Err(BlpError::OpenService {
                    service: service.clone(),
                    source: None,
                    label: Some(reason.to_string()),
                }));
            }
        }
    }

    /// SDK dispatcher entry point: route every message of `ev`.
    pub(super) fn dispatch_event(&self, ev: xbbg_core::Event) {
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

    fn handle_partial_response(&self, msg: &xbbg_core::Message<'_>) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(correlation_id) = msg.correlation_id(i) {
                let Some(dispatch_key) = DispatchKey::from_correlation_id(&correlation_id) else {
                    continue;
                };
                let key = dispatch_key.to_slab_key();
                // Hold the slab lock while appending: partials mutate state
                // in place. Submitter inserts briefly contend; the state
                // machines take no other locks, so no deadlock is possible.
                let mut requests = self.requests.lock();
                if let Some(slot) = requests.get_mut(key) {
                    if slot.generation == dispatch_key.generation() {
                        slot.state.on_partial(msg);
                        xbbg_log::trace!(worker_id = self.id, key = key, "partial response");
                    } else {
                        xbbg_log::debug!(
                            worker_id = self.id,
                            key = key,
                            "stale partial response for recycled slot; dropped"
                        );
                    }
                }
            }
        }
    }

    fn handle_response(&self, msg: &xbbg_core::Message<'_>) {
        let n = msg.num_correlation_ids();
        for i in 0..n {
            if let Some(correlation_id) = msg.correlation_id(i) {
                let Some(dispatch_key) = DispatchKey::from_correlation_id(&correlation_id) else {
                    continue;
                };
                if let Some(slot) = self.take_slot(dispatch_key) {
                    let key = dispatch_key.to_slab_key();
                    let rtt_ms = slot.sent_at.elapsed().as_micros() as f64 / 1000.0;
                    xbbg_log::debug!(
                        worker_id = self.id,
                        rtt_ms = rtt_ms,
                        key = key,
                        "bloomberg_roundtrip"
                    );
                    // Build the final batch outside the slab lock.
                    slot.state.finish_and_reply(msg);
                    xbbg_log::debug!(worker_id = self.id, key = key, "response completed");
                }
            }
        }
    }

    fn handle_request_status(&self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        if msg_type != "RequestFailure" {
            return;
        }
        let n = msg.num_correlation_ids();

        for i in 0..n {
            if let Some(correlation_id) = msg.correlation_id(i) {
                let Some(dispatch_key) = DispatchKey::from_correlation_id(&correlation_id) else {
                    continue;
                };
                let reason = extract_reason_description(msg);
                xbbg_log::error!(
                    worker_id = self.id,
                    key = dispatch_key.to_slab_key(),
                    reason = %reason.as_deref().unwrap_or(""),
                    "request failed"
                );
                if let Some(slot) = self.take_slot(dispatch_key) {
                    slot.state.fail(BlpError::Internal {
                        detail: reason.unwrap_or_else(|| "RequestFailure".to_string()),
                    });
                }
            }
        }
    }

    fn handle_session_status(&self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();
        match msg_type {
            "SessionStarted" => {
                self.health.store(0, Ordering::Release);
                self.resolve_startup(Ok(()));
                xbbg_log::info!(worker_id = self.id, "session started");
            }
            "SessionStartupFailure" => {
                let reason = extract_reason_description(msg);
                xbbg_log::error!(
                    worker_id = self.id,
                    reason = %reason.as_deref().unwrap_or(""),
                    "session startup failure"
                );
                self.health.store(2, Ordering::Release);
                self.resolve_startup(Err(session_start_error("session startup failure", reason)));
            }
            "SessionTerminated" => {
                // SDK has given up reconnecting. The session is dead. Drain
                // everything and mark the worker so the pool evicts it.
                let reason = extract_reason_description(msg);
                self.resolve_startup(Err(session_start_error(
                    "session terminated during startup",
                    reason.clone(),
                )));
                self.drain_in_flight(reason.as_deref().unwrap_or("Bloomberg session terminated"));
                self.fail_pending_service_opens("Bloomberg session terminated");
                self.health.store(2, Ordering::Release);
                if self.shutting_down.load(Ordering::Acquire) {
                    xbbg_log::info!(
                        worker_id = self.id,
                        reason = %reason.as_deref().unwrap_or(""),
                        "SessionTerminated during requested shutdown"
                    );
                } else {
                    xbbg_log::error!(
                        worker_id = self.id,
                        reason = %reason.as_deref().unwrap_or(""),
                        "SessionTerminated — worker is dead"
                    );
                }
            }
            "AuthorizationFailure" => {
                let reason = extract_reason_description(msg);
                self.resolve_startup(Err(session_start_error(
                    "session identity authorization failed",
                    reason,
                )));
            }
            "AuthorizationRevoked" => {
                // Session identity was revoked mid-session. Authorized requests
                // will now fail. Drain + mark Dead so the pool evicts this
                // worker.
                let reason = extract_reason_description(msg);
                self.resolve_startup(Err(session_start_error(
                    "session identity authorization revoked",
                    reason.clone(),
                )));
                self.drain_in_flight(
                    reason
                        .as_deref()
                        .unwrap_or("Bloomberg session identity revoked"),
                );
                self.fail_pending_service_opens("Bloomberg session identity revoked");
                self.health.store(2, Ordering::Release);
                xbbg_log::error!(
                    worker_id = self.id,
                    reason = %reason.as_deref().unwrap_or(""),
                    "AuthorizationRevoked — identity gone; worker is dead"
                );
            }
            "SessionConnectionDown" => {
                // Transient network drop. Unlike subscriptions (which the SDK
                // auto-recovers via SubscriptionStreamsActivated/Deactivated),
                // requests are transactional: any response mid-transit when TCP
                // dropped is lost. Fail in-flight requests immediately so the
                // caller can retry on a healthy worker or back off. The session
                // is still alive and the SDK will auto-reconnect, so we go
                // Degraded (not Dead) — the worker resumes full service on the
                // subsequent SessionConnectionUp.
                let reason = extract_reason_description(msg);
                self.drain_in_flight(
                    reason
                        .as_deref()
                        .unwrap_or("Bloomberg session connection lost (transient)"),
                );
                self.health.store(1, Ordering::Release);
                if self.shutting_down.load(Ordering::Acquire) {
                    xbbg_log::info!(
                        worker_id = self.id,
                        reason = %reason.as_deref().unwrap_or(""),
                        "SessionConnectionDown during requested shutdown"
                    );
                } else {
                    xbbg_log::warn!(
                        worker_id = self.id,
                        reason = %reason.as_deref().unwrap_or(""),
                        "SessionConnectionDown — failing in-flight requests; SDK will auto-reconnect"
                    );
                }
            }
            "SessionConnectionUp" => {
                self.health.store(0, Ordering::Release);
                let reason = extract_reason_description(msg);
                xbbg_log::info!(
                    worker_id = self.id,
                    reason = %reason.as_deref().unwrap_or(""),
                    "SessionConnectionUp — worker healthy"
                );
            }
            _ => {
                xbbg_log::debug!(worker_id = self.id, msg_type = msg_type, "session status");
            }
        }
    }

    fn handle_service_status(&self, msg: &xbbg_core::Message<'_>) {
        let msg_type_name = msg.message_type();
        let msg_type = msg_type_name.as_str();

        // If this ServiceOpened/ServiceOpenFailure is a reply to one of our
        // async `open_service_async` calls, resolve the matching pending open
        // so every waiting `ensure_service` unblocks.
        if matches!(msg_type, "ServiceOpened" | "ServiceOpenFailure") {
            if let Some(CorrelationId::Int(cid_int)) = msg.correlation_id(0) {
                let entry = {
                    let mut pending = self.pending_service_opens.lock();
                    let service = pending
                        .iter()
                        .find_map(|(name, open)| (open.cid == cid_int).then(|| name.clone()));
                    service.and_then(|name| pending.remove(&name).map(|open| (name, open)))
                };
                if let Some((service, open)) = entry {
                    if msg_type == "ServiceOpened" {
                        self.open_services.write().insert(service.clone());
                        xbbg_log::debug!(worker_id = self.id, service = %service, "service opened");
                        for waiter in open.waiters {
                            let _ = waiter.send(Ok(()));
                        }
                    } else {
                        let reason = extract_reason_description(msg);
                        xbbg_log::warn!(
                            worker_id = self.id,
                            service = %service,
                            reason = %reason.as_deref().unwrap_or(""),
                            "service open failed"
                        );
                        for waiter in open.waiters {
                            let _ = waiter.send(Err(BlpError::OpenService {
                                service: service.clone(),
                                source: None,
                                label: reason.clone(),
                            }));
                        }
                    }
                    return;
                }
            }
        }

        xbbg_log::debug!(worker_id = self.id, msg_type = msg_type, "service status");
    }
}

fn session_start_error(context: &str, reason: Option<String>) -> BlpError {
    BlpError::SessionStart {
        source: None,
        label: Some(match reason {
            Some(reason) => format!("{context}: {reason}"),
            None => context.to_string(),
        }),
    }
}

/// A request worker backed by an asynchronous Bloomberg session.
///
/// All methods take `&self`; submissions, cancellations, and SDK callback
/// dispatch may run concurrently from different threads.
pub(crate) struct AsyncRequestWorker {
    pub(crate) id: usize,
    session: AsyncSession,
    shared: Arc<WorkerShared>,
    config: Arc<EngineConfig>,
}

impl AsyncRequestWorker {
    /// Create a worker: build options, start the session (blocking), wait for
    /// the startup status, and pre-warm configured services.
    pub(crate) fn new(id: usize, config: Arc<EngineConfig>) -> Result<Self, BlpError> {
        let options = build_session_options(&config, false)?;
        let health = Arc::new(AtomicU8::new(0));
        let shared = Arc::new(WorkerShared::new(id, health));

        let handler_shared = Arc::clone(&shared);
        let session = AsyncSession::new(&options, move |event| {
            handler_shared.dispatch_event(event);
        })?;

        session
            .start()
            .map_err(|err| attach_auth_context(err, config.auth.as_ref()))?;
        shared
            .wait_startup(Duration::from_millis(u64::from(SESSION_STARTUP_TIMEOUT_MS)))
            .map_err(|err| attach_auth_context(err, config.auth.as_ref()))?;

        let worker = Self {
            id,
            session,
            shared,
            config,
        };
        worker.warmup();
        xbbg_log::info!(worker_id = id, "AsyncRequestWorker started");
        Ok(worker)
    }

    /// Pre-warm commonly used services. Blocking; only called at creation.
    /// Synchronous opens do not stall event delivery on an async session —
    /// events keep flowing on the SDK dispatcher thread.
    fn warmup(&self) {
        for service_name in &self.config.warmup_services {
            match self.session.open_service(service_name) {
                Ok(()) => {
                    self.shared
                        .open_services
                        .write()
                        .insert(service_name.clone());
                }
                Err(e) => {
                    xbbg_log::warn!(
                        worker_id = self.id,
                        service = %service_name,
                        error = %e,
                        "failed to pre-warm service"
                    );
                }
            }
        }
        xbbg_log::info!(
            worker_id = self.id,
            services = ?self.shared.open_services.read().iter().collect::<Vec<_>>(),
            "worker pre-warmed"
        );
    }

    pub(crate) fn health(&self) -> WorkerHealth {
        match self.shared.health.load(Ordering::Acquire) {
            0 => WorkerHealth::Healthy,
            1 => WorkerHealth::Degraded,
            _ => WorkerHealth::Dead,
        }
    }

    /// Ensure a service is open, awaiting an async open if necessary.
    /// Concurrent opens of the same service coalesce onto one SDK call.
    async fn ensure_service(&self, name: &str) -> Result<(), BlpError> {
        if self.shared.open_services.read().contains(name) {
            return Ok(());
        }

        let rx = {
            let mut pending = self.shared.pending_service_opens.lock();
            // Re-check under the pending lock: the dispatcher inserts into
            // open_services before resolving waiters.
            if self.shared.open_services.read().contains(name) {
                return Ok(());
            }
            let (tx, rx) = oneshot::channel();
            match pending.entry(name.to_string()) {
                Entry::Occupied(mut entry) => entry.get_mut().waiters.push(tx),
                Entry::Vacant(entry) => {
                    let id = self
                        .shared
                        .next_service_open_id
                        .fetch_add(1, Ordering::Relaxed)
                        .wrapping_add(1);
                    let cid_int = SERVICE_OPEN_CID_TAG | (id & (SERVICE_OPEN_CID_TAG - 1));
                    let cid = CorrelationId::Int(cid_int);
                    // The enqueue-only FFI call is cheap; holding the lock
                    // across it closes the insert/resolve race.
                    self.session.open_service_async(name, &cid)?;
                    entry.insert(PendingServiceOpen {
                        cid: cid_int,
                        waiters: vec![tx],
                    });
                }
            }
            rx
        };

        match tokio::time::timeout(Duration::from_millis(SERVICE_OPEN_TIMEOUT_MS), rx).await {
            Ok(Ok(result)) => result,
            Ok(Err(_)) => Err(BlpError::Internal {
                detail: format!("service open for {name} dropped without resolution"),
            }),
            Err(_) => Err(BlpError::Timeout),
        }
    }

    /// Submit a unified request. Failures are delivered through `reply`;
    /// `Some(ticket)` is returned only when the request is in flight and
    /// cancellable.
    pub(crate) async fn submit(
        &self,
        request: PreparedRequest,
        reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
    ) -> Option<RequestTicket> {
        let params = request.params();
        let t0 = Instant::now();
        if let Err(error) = self.ensure_service(&params.service).await {
            let _ = reply.send(Err(error));
            return None;
        }
        xbbg_log::debug!(
            worker_id = self.id,
            elapsed_us = t0.elapsed().as_micros(),
            "ensure_service"
        );

        xbbg_log::debug!(
            worker_id = self.id,
            shape = ?request.shape(),
            fields = ?params.fields,
            "creating request state"
        );
        let state = create_request_state(&request, reply);
        self.dispatch_prepared(request, state)
    }

    /// Submit a unified streaming request.
    pub(crate) async fn submit_stream(
        &self,
        request: PreparedRequest,
        stream: mpsc::Sender<Result<RecordBatch, BlpError>>,
    ) -> Option<RequestTicket> {
        let params = request.params();
        let fields = params.fields.clone().unwrap_or_default();
        let ticker = params.security.clone().unwrap_or_default();

        let state = match request.shape() {
            PlannedRequestShape::HistData(_) => {
                UnifiedRequestState::HistDataStream(HistDataStreamState::new(fields, stream))
            }
            PlannedRequestShape::IntradayBar => {
                UnifiedRequestState::IntradayBarStream(IntradayBarStreamState::new(ticker, stream))
            }
            PlannedRequestShape::IntradayTick => UnifiedRequestState::IntradayTickStream(
                IntradayTickStreamState::new(ticker, stream),
            ),
            _ => {
                send_stream_error(
                    stream,
                    BlpError::InvalidArgument {
                        detail: format!(
                            "Streaming not supported for extractor: {:?}",
                            params.extractor
                        ),
                    },
                );
                return None;
            }
        };

        if let Err(error) = self.ensure_service(&params.service).await {
            state.fail(error);
            return None;
        }

        self.dispatch_prepared(request, state)
    }

    /// Register `state` in the slab and send the Bloomberg request. State is
    /// inserted before `sendRequest` so a response arriving on the dispatcher
    /// thread before this returns still finds its slot.
    fn dispatch_prepared(
        &self,
        request: PreparedRequest,
        state: UnifiedRequestState,
    ) -> Option<RequestTicket> {
        let generation = self.shared.next_generation();
        let key = self.shared.insert_slot(generation, state);
        let dispatch_key = DispatchKey::with_generation(key, generation);
        let cid = dispatch_key.to_correlation_id();

        let result = (|| -> Result<(), BlpError> {
            let params = request.params();
            // Build the request from a short-lived service view borrowed from
            // this worker's session. Do not cache the SDK service handle;
            // Bloomberg owns it through the session.
            let service = self.session.get_service(&params.service)?;
            xbbg_log::debug!(
                worker_id = self.id,
                operation = %request.effective_operation(),
                securities = ?params.securities,
                start_date = ?params.start_date,
                end_date = ?params.end_date,
                "building request"
            );
            let blp_request = build_request_from_params(self.id, &service, &request)?;

            let actual_cid = self.session.send_request_with_label(
                &blp_request,
                Some(&cid),
                params.request_id.as_deref(),
            )?;
            let actual_dispatch_key =
                DispatchKey::from_correlation_id(&actual_cid).ok_or_else(|| {
                    BlpError::Internal {
                        detail: format!(
                            "Bloomberg returned non-dispatch correlation ID for request: {:?}",
                            actual_cid
                        ),
                    }
                })?;
            if actual_dispatch_key != dispatch_key {
                return Err(BlpError::Internal {
                    detail: format!(
                        "Bloomberg returned unexpected dispatch correlation ID {:?} for slab key {}",
                        actual_cid, key
                    ),
                });
            }

            xbbg_log::debug!(
                worker_id = self.id,
                key = key,
                service = %params.service,
                operation = %request.effective_operation(),
                "request sent"
            );
            Ok(())
        })();

        match result {
            Ok(()) => Some(RequestTicket { key, generation }),
            Err(err) => {
                if let Some(slot) = self.shared.take_slot(dispatch_key) {
                    slot.state.fail(err);
                }
                None
            }
        }
    }

    /// Cancel an in-flight request (caller dropped the awaitable). The
    /// generation makes the CID single-use, so a recycled slot never aliases
    /// it; cancelling an already-completed ticket is a no-op.
    pub(crate) fn cancel_request(&self, ticket: RequestTicket) {
        let dispatch_key = DispatchKey::with_generation(ticket.key, ticket.generation);
        let Some(slot) = self.shared.take_slot(dispatch_key) else {
            return;
        };
        let cid = dispatch_key.to_correlation_id();

        if let Err(error) = self.session.cancel(&cid) {
            xbbg_log::warn!(
                worker_id = self.id,
                key = ticket.key,
                error = %error,
                "failed to cancel Bloomberg request"
            );
            drop(slot);
            self.shared.health.store(2, Ordering::Release);
            self.shared
                .drain_in_flight("Bloomberg request cancellation failed");
            return;
        }

        // Caller cancelled: drop the state without replying.
        drop(slot);
        xbbg_log::info!(
            worker_id = self.id,
            key = ticket.key,
            "cancelled Bloomberg request"
        );
    }

    /// Fail a request that exceeded the configured hard timeout.
    pub(crate) fn timeout_request(&self, ticket: RequestTicket, timeout_ms: u64) {
        let dispatch_key = DispatchKey::with_generation(ticket.key, ticket.generation);
        let Some(slot) = self.shared.take_slot(dispatch_key) else {
            return;
        };
        let cid = dispatch_key.to_correlation_id();
        if let Err(error) = self.session.cancel(&cid) {
            // Cancel failed — session is probably terminal. We still must fail
            // the caller's oneshot; the request is not coming back.
            xbbg_log::warn!(
                worker_id = self.id,
                key = ticket.key,
                error = %error,
                "timeout_request: Bloomberg cancel failed"
            );
        }
        slot.state.fail(BlpError::Timeout);
        xbbg_log::warn!(
            worker_id = self.id,
            key = ticket.key,
            timeout_ms = timeout_ms,
            "request exceeded request_timeout_ms; failed with BlpError::Timeout"
        );
    }

    /// Mark slow requests and return hard-timeout candidates for
    /// [`AsyncRequestWorker::timeout_request`].
    pub(crate) fn scan_timeouts(&self, hard_timeout: Option<Duration>) -> Vec<RequestTicket> {
        self.shared.scan_timeouts(hard_timeout)
    }

    /// Introspect a service's schema.
    pub(crate) async fn introspect_schema(
        &self,
        service_uri: &str,
    ) -> Result<crate::schema::ServiceSchema, BlpError> {
        xbbg_log::debug!(worker_id = self.id, service = %service_uri, "introspecting schema");

        self.ensure_service(service_uri).await?;

        let service = self.session.get_service(service_uri)?;
        let schema = crate::schema::introspect_service(&service, service_uri);

        xbbg_log::debug!(
            worker_id = self.id,
            service = %service_uri,
            operations = schema.operations.len(),
            "schema introspection complete"
        );

        Ok(schema)
    }

    /// Begin stopping the session without blocking (Drop-friendly).
    pub(crate) fn signal_shutdown(&self) {
        self.shared.shutting_down.store(true, Ordering::Release);
        self.session.stop_async();
    }

    /// Stop the session (blocks until in-flight callbacks drain) and fail
    /// anything still registered.
    pub(crate) fn shutdown_blocking(&self) {
        self.shared.shutting_down.store(true, Ordering::Release);
        xbbg_log::info!(worker_id = self.id, "AsyncRequestWorker shutting down");
        self.session.stop();
        self.shared.fail_pending_service_opens("worker shutdown");
        self.shared.drain_in_flight("worker shutdown");
    }
}

/// Create the appropriate request state based on the prepared request kind.
fn create_request_state(
    request: &PreparedRequest,
    reply: oneshot::Sender<Result<RecordBatch, BlpError>>,
) -> UnifiedRequestState {
    let params = request.params();
    let fields = params.fields.clone().unwrap_or_default();
    let field_types = params.field_types.clone();

    match request.shape() {
        PlannedRequestShape::RefData(output) => {
            UnifiedRequestState::RefData(RefDataState::with_format(
                fields,
                output.format,
                output.long_mode,
                field_types,
                params.include_security_errors,
                reply,
            ))
        }
        PlannedRequestShape::HistData(output) => UnifiedRequestState::HistData(
            HistDataState::with_format(fields, output.format, output.long_mode, field_types, reply),
        ),
        PlannedRequestShape::BulkData => {
            let field = fields.first().cloned().unwrap_or_default();
            UnifiedRequestState::BulkData(BulkDataState::new(field, reply))
        }
        PlannedRequestShape::Generic => UnifiedRequestState::Generic(GenericState::new(reply)),
        PlannedRequestShape::Bql => UnifiedRequestState::Bql(BqlState::new(reply)),
        PlannedRequestShape::Bsrch => UnifiedRequestState::Bsrch(BsrchState::new(reply)),
        PlannedRequestShape::FieldInfo => {
            UnifiedRequestState::FieldInfo(FieldInfoState::new(reply))
        }
        PlannedRequestShape::IntradayBar => {
            // IntradayBarRequest has no column-adding elements (maxDataPoints,
            // gapFillInitialBar, adjustment*, etc. are behavior-only). The response
            // shape is always `barData.barTickData[]` with the same fields.
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
        PlannedRequestShape::IntradayTick => {
            let ticker = params.security.clone().unwrap_or_default();
            UnifiedRequestState::IntradayTick(IntradayTickState::new(ticker, reply))
        }
    }
}

/// Build a Bloomberg request from a prepared request.
fn build_request_from_params(
    worker_id: usize,
    service: &xbbg_core::Service<'_>,
    prepared: &PreparedRequest,
) -> Result<xbbg_core::Request, BlpError> {
    let params = prepared.params();
    let operation = prepared.effective_operation();
    xbbg_log::trace!(operation = %operation, "creating request");
    let mut request = service.create_request(operation)?;
    xbbg_log::trace!("request created");

    if prepared.is_excel_get_grid_request() {
        apply_excel_grid_request_parameters(&mut request, params)?;
        return Ok(request);
    }

    // Set securities (multi or single)
    if let Some(securities) = &params.securities {
        for sec in securities {
            xbbg_log::trace!(element = "securities", value = %sec, "appending");
            request.append_str("securities", sec)?;
        }
    }
    if let Some(security) = &params.security {
        // Bloomberg intraday operations use a scalar "security" element; other
        // operations treat the singular convenience input as one "securities" entry.
        if prepared.uses_intraday_security_element() {
            xbbg_log::trace!(element = "security", value = %security, "setting scalar");
            request.set_str("security", security)?;
        } else {
            xbbg_log::trace!(element = "securities", value = %security, "appending");
            request.append_str("securities", security)?;
        }
    }

    // Set fields
    if let Some(fields) = &params.fields {
        for field in fields {
            xbbg_log::trace!(element = "fields", value = %field, "appending");
            request.append_str("fields", field)?;
        }
    }

    // Set date range (for historical) - scalar elements use set_str
    if let Some(start) = &params.start_date {
        xbbg_log::trace!(element = "startDate", value = %start, "setting");
        request.set_str("startDate", start)?;
    }
    if let Some(end) = &params.end_date {
        xbbg_log::trace!(element = "endDate", value = %end, "setting");
        request.set_str("endDate", end)?;
    }

    // Set datetime range (for intraday) - use proper datetime type
    if let Some(start) = &params.start_datetime {
        xbbg_log::trace!(element = "startDateTime", value = %start, "setting datetime");
        request.set_datetime("startDateTime", start)?;
    }
    if let Some(end) = &params.end_datetime {
        xbbg_log::trace!(element = "endDateTime", value = %end, "setting datetime");
        request.set_datetime("endDateTime", end)?;
    }

    // Set event type (singular, for intraday bars)
    if let Some(event_type) = &params.event_type {
        request.set_str("eventType", event_type)?;
    }
    // Set event types (array, for intraday ticks)
    if let Some(event_types) = &params.event_types {
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
    if let Some(field_ids) = &params.field_ids {
        for id in field_ids {
            request.append_str("id", id)?;
        }
    }

    // Set overrides (fieldId/value pairs on the "overrides" sequence element)
    if let Some(overrides) = &params.overrides {
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
                worker_id = worker_id,
                count = overrides.len(),
                "overrides applied"
            );
        }
    }

    // Set search spec (for FieldSearchRequest)
    if let Some(search_spec) = &params.search_spec {
        request.set_str("searchSpec", search_spec)?;
    }

    Ok(request)
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::RequestParams;

    fn shared() -> WorkerShared {
        WorkerShared::new(0, Arc::new(AtomicU8::new(0)))
    }

    fn generic_state() -> (
        UnifiedRequestState,
        oneshot::Receiver<Result<RecordBatch, BlpError>>,
    ) {
        let (tx, rx) = oneshot::channel();
        (UnifiedRequestState::Generic(GenericState::new(tx)), rx)
    }

    #[test]
    fn take_slot_requires_matching_generation() {
        let shared = shared();
        let (state, _rx) = generic_state();
        let generation = shared.next_generation();
        let key = shared.insert_slot(generation, state);

        // Wrong generation: slot stays.
        let stale = DispatchKey::with_generation(key, generation.wrapping_add(1));
        assert!(shared.take_slot(stale).is_none());
        assert_eq!(shared.requests.lock().len(), 1);

        // Right generation: slot removed.
        let fresh = DispatchKey::with_generation(key, generation);
        assert!(shared.take_slot(fresh).is_some());
        assert!(shared.requests.lock().is_empty());

        // Removing again is a no-op.
        assert!(shared.take_slot(fresh).is_none());
    }

    #[test]
    fn recycled_slot_is_not_visible_to_old_ticket() {
        let shared = shared();
        let (first, _rx1) = generic_state();
        let g1 = shared.next_generation();
        let key = shared.insert_slot(g1, first);
        let first_key = DispatchKey::with_generation(key, g1);
        assert!(shared.take_slot(first_key).is_some());

        // Recycle the same slab slot with a new generation.
        let (second, _rx2) = generic_state();
        let g2 = shared.next_generation();
        let key2 = shared.insert_slot(g2, second);
        assert_eq!(key, key2, "slab should recycle the slot");

        // The old ticket no longer addresses the slot.
        assert!(shared.take_slot(first_key).is_none());
        assert_eq!(shared.requests.lock().len(), 1);
    }

    #[test]
    fn scan_timeouts_warns_once_and_reports_expired() {
        let shared = shared();
        let (state, _rx) = generic_state();
        let generation = shared.next_generation();
        let key = shared.insert_slot(generation, state);

        // Backdate the slot beyond both thresholds.
        shared.requests.lock().get_mut(key).unwrap().sent_at =
            Instant::now() - Duration::from_secs(120);

        let expired = shared.scan_timeouts(Some(Duration::from_secs(60)));
        assert_eq!(expired.len(), 1);
        assert_eq!(expired[0].key, key);
        assert_eq!(expired[0].generation, generation);
        assert!(shared.requests.lock().get(key).unwrap().warned);

        // Without a hard timeout nothing is reported, and the warning does
        // not repeat.
        let expired = shared.scan_timeouts(None);
        assert!(expired.is_empty());
    }

    #[test]
    fn drain_in_flight_fails_all_slots() {
        let shared = shared();
        let (s1, mut rx1) = generic_state();
        let (s2, mut rx2) = generic_state();
        let g1 = shared.next_generation();
        let g2 = shared.next_generation();
        shared.insert_slot(g1, s1);
        shared.insert_slot(g2, s2);

        shared.drain_in_flight("test drain");

        assert!(shared.requests.lock().is_empty());
        assert!(matches!(rx1.try_recv(), Ok(Err(BlpError::Internal { .. }))));
        assert!(matches!(rx2.try_recv(), Ok(Err(BlpError::Internal { .. }))));
    }

    #[test]
    fn startup_latch_resolves_once() {
        let shared = shared();
        shared.resolve_startup(Ok(()));
        shared.resolve_startup(Err(BlpError::Timeout)); // ignored: already resolved
        assert!(shared.wait_startup(Duration::from_millis(10)).is_ok());
    }

    #[test]
    fn startup_latch_times_out_when_unresolved() {
        let shared = shared();
        assert!(matches!(
            shared.wait_startup(Duration::from_millis(10)),
            Err(BlpError::Timeout)
        ));
    }

    #[test]
    fn iter_named_request_parameters_includes_options_after_elements() {
        let params = RequestParams {
            elements: Some(vec![(
                "periodicitySelection".to_string(),
                "DAILY".to_string(),
            )]),
            options: Some(vec![("returnEids".to_string(), "true".to_string())]),
            ..Default::default()
        };

        let collected: Vec<(String, String)> = iter_named_request_parameters(&params)
            .map(|(name, value)| (name.to_string(), value.to_string()))
            .collect();

        assert_eq!(
            collected,
            vec![
                ("periodicitySelection".to_string(), "DAILY".to_string()),
                ("returnEids".to_string(), "true".to_string()),
            ]
        );
    }
}

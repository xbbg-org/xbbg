use thiserror::Error;

use xbbg_core::BlpError;

#[derive(Debug, Error)]
pub enum BlpAsyncError {
    /// Wraps a core BlpError, preserving all structured error context.
    #[error(transparent)]
    Blp(#[from] BlpError),

    /// Bloomberg error (explicit, not From trait)
    #[error("bloomberg error: {0}")]
    BlpError(BlpError),

    #[error("internal error: {0}")]
    Internal(String),

    #[error("configuration error: {detail}")]
    ConfigError { detail: String },

    #[error("channel closed")]
    ChannelClosed,

    #[error("stream full")]
    StreamFull,

    #[error("cancelled")]
    Cancelled,

    #[error("timeout")]
    Timeout,

    /// Bloomberg session lost — transport dropped or session terminated.
    ///
    /// In-flight requests on the affected worker have been failed immediately.
    /// Callers should retry with a different worker or wait for the pool to
    /// recover.
    #[error("session lost on worker {worker_id} ({in_flight_count} in-flight requests failed)")]
    SessionLost {
        worker_id: usize,
        in_flight_count: usize,
    },

    /// All request workers in the pool are dead.
    ///
    /// No healthy worker is available to accept requests. The pool needs
    /// worker replacement (Phase 4) or manual intervention.
    #[error("all {pool_size} request workers are dead — no healthy worker available")]
    AllWorkersDown { pool_size: usize },
}

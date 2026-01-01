use thiserror::Error;

use xbbg_core::BlpError;

#[derive(Debug, Error)]
pub enum BlpAsyncError {
    /// Wraps a core BlpError, preserving all structured error context.
    #[error(transparent)]
    Blp(#[from] BlpError),

    #[error("internal error: {0}")]
    Internal(String),

    #[error("stream full")]
    StreamFull,

    #[error("cancelled")]
    Cancelled,

    #[error("timeout")]
    Timeout,
}

use thiserror::Error;

#[derive(Debug, Error)]
pub enum BlpAsyncError {
    #[error("internal error: {0}")]
    Internal(String),
    #[error("stream full")]
    StreamFull,
    #[error("cancelled")]
    Cancelled,
    #[error("timeout")]
    Timeout,
}

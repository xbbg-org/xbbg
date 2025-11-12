use std::fmt;

use thiserror::Error;

/// Unified result type for the core crate.
pub type Result<T, E = BlpError> = std::result::Result<T, E>;

/// Lightweight CorrelationId context display (string or number).
#[derive(Debug, Clone)]
pub enum CorrelationContext {
    U64(u64),
    Tag(String),
}

impl fmt::Display for CorrelationContext {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CorrelationContext::U64(v) => write!(f, "{v}"),
            CorrelationContext::Tag(s) => write!(f, "{s}"),
        }
    }
}

/// Common error type surfaced by xbbg-core.
#[derive(Debug, Error)]
pub enum BlpError {
    #[error("session start failed")]
    SessionStart {
        #[source]
        source: Option<anyhow::Error>,
        label: Option<String>,
    },

    #[error("open service failed")]
    OpenService {
        service: String,
        #[source]
        source: Option<anyhow::Error>,
        label: Option<String>,
    },

    #[error("request failed")]
    RequestFailure {
        service: String,
        operation: Option<String>,
        cid: Option<CorrelationContext>,
        label: Option<String>,
        request_id: Option<String>,
        #[source]
        source: Option<anyhow::Error>,
    },

    #[error("invalid argument")]
    InvalidArgument { detail: String },

    #[error("operation timed out")]
    Timeout,

    #[error("request template terminated")]
    TemplateTerminated {
        cid: Option<CorrelationContext>,
    },

    #[error("subscription failure")]
    SubscriptionFailure {
        cid: Option<CorrelationContext>,
        label: Option<String>,
    },

    #[error("internal error")]
    Internal { detail: String },

    // Schema errors
    #[error("operation not found: {service}::{operation}")]
    SchemaOperationNotFound { service: String, operation: String },

    #[error("schema element not found: {parent}.{name}")]
    SchemaElementNotFound { parent: String, name: String },

    #[error("schema type mismatch at {element}: expected {expected:?}, found {found:?}")]
    SchemaTypeMismatch {
        element: String,
        expected: crate::schema::DataType,
        found: crate::schema::DataType,
    },

    #[error("unsupported schema construct at {element}: {detail}")]
    SchemaUnsupported { element: String, detail: String },
}

impl BlpError {
    pub fn with_request_ctx(
        service: impl Into<String>,
        operation: Option<impl Into<String>>,
        cid: Option<CorrelationContext>,
        label: Option<impl Into<String>>,
        request_id: Option<impl Into<String>>,
        source: Option<anyhow::Error>,
    ) -> Self {
        BlpError::RequestFailure {
            service: service.into(),
            operation: operation.map(Into::into),
            cid,
            label: label.map(Into::into),
            request_id: request_id.map(Into::into),
            source,
        }
    }
}



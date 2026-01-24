// Allow large error types - BlpError contains rich context for debugging
#![allow(clippy::result_large_err)]

mod config;
// TODO: dispatcher requires Session to be Sync (Arc<Session> across threads)
// Commenting out until we decide on threading model
// mod dispatcher;
mod errors;
pub mod field_cache;
// mod requests;  // Uses AsyncSession which is deprecated
mod router;
// mod subscriptions;  // Uses dispatcher
pub mod engine;
mod metrics;
mod status;

pub use config::{AsyncOptions, BackpressurePolicy};
pub use errors::BlpAsyncError;
pub use metrics::RouterMetrics;
pub use router::{Envelope, Router};
// pub use subscriptions::SubscriptionHandle;

// New worker pool Engine - the main API
pub use engine::{Engine, EngineConfig, SlabKey, ValidationMode};

// AsyncSession is deprecated in favor of Engine
// It requires Arc<Session> to be Send, which requires Session to be Sync
// The Engine uses per-worker sessions instead, avoiding this issue
// TODO: Consider removing AsyncSession entirely or using Mutex<Session>

#[cfg(test)]
mod tests;

// Allow large error types - BlpError contains rich context for debugging
#![allow(clippy::result_large_err)]

pub mod engine;
mod errors;
pub mod field_cache;
pub mod request_builder;
pub mod schema;
pub mod services;

pub use errors::BlpAsyncError;

// Worker-pool Engine — the primary API
pub use engine::{Engine, EngineConfig, OverflowPolicy, SlabKey, ValidationMode};

// Request building and validation
pub use request_builder::{RequestBuilder, RoutedParams};

// Schema introspection and caching
pub use schema::{ElementInfo, OperationSchema, SchemaCache, ServiceSchema};

#[cfg(test)]
mod tests;

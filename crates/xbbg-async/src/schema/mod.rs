//! Schema introspection and caching for Bloomberg services.
//!
//! This module provides:
//! - Serde-enabled schema types for JSON serialization
//! - Conversion from xbbg_core FFI types to serde types
//! - In-memory and disk caching for introspected schemas
//!
//! # Example
//!
//! ```ignore
//! use xbbg_async::schema::{SchemaCache, ServiceSchema};
//!
//! // Cache is typically managed by Engine
//! let cache = SchemaCache::new();
//!
//! // Check if schema is cached
//! if let Some(schema) = cache.get("//blp/refdata") {
//!     for op in &schema.operations {
//!         println!("{}: {}", op.name, op.description);
//!     }
//! }
//! ```

mod cache;
mod introspector;
mod types;

pub use cache::{CacheStats, SchemaCache};
pub use introspector::{introspect_operation, introspect_service, list_operation_names};
pub use types::{ElementInfo, OperationSchema, ServiceSchema};

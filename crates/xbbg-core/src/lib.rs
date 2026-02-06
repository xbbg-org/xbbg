//! xbbg-core: Zero-allocation Bloomberg API wrapper
//!
//! High-performance Rust bindings for the Bloomberg C++ SDK.
//!
//! - Zero-allocation hot paths
//! - Direct typed access (no JSON serialization)
//! - Sub-microsecond field extraction

#![allow(clippy::result_large_err)]

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

// Core types
pub mod datatype;
pub mod datetime;
pub mod element;
pub mod event;
pub mod ffi;
pub mod message;
pub mod name;
pub mod simd;
pub mod value;

// Session API
pub mod correlation;
pub mod errors;
pub mod identity;
pub mod options;
pub mod request;
pub mod schema;
pub mod service;
pub mod session;
pub mod subscription;

// Re-exports for convenience
pub use correlation::CorrelationId;
pub use datatype::DataType;
pub use datetime::HighPrecisionDatetime;
pub use element::{ChildrenIter, Element, ValuesIter};
pub use errors::{BlpError, Result};
pub use event::{Event, EventType};
pub use identity::Identity;
pub use message::Message;
pub use name::{clear_name_cache, name_cache_size, Name};
pub use request::Request;
pub use service::Service;
pub use session::{Session, SessionOptions};
pub use subscription::SubscriptionList;
pub use value::{OwnedValue, Value};

// Schema introspection types
pub use schema::{
    Constant, ConstantList, Operation, SchemaElementDefinition, SchemaStatus, SchemaTypeDefinition,
};

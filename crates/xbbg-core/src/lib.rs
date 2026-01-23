//! xbbg-core: Zero-allocation Bloomberg API wrapper (REWRITE IN PROGRESS)
//!
//! This crate provides high-performance Rust wrappers around the Bloomberg C++ SDK.
//! The rewrite focuses on:
//! - Zero-allocation hot paths
//! - Direct typed access (no JSON serialization)
//! - Sub-microsecond field extraction

// Allow large error types - BlpError contains rich context for debugging
#![allow(clippy::result_large_err)]
// Allow unused_unsafe: Mock backend (datamock) declares FFI functions as safe,
// but real backend (blpapi-sys) requires unsafe. The unsafe blocks are correct
// for production use with the real Bloomberg API.
#![allow(unused_unsafe)]

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

// Core types
pub mod datatype;
pub mod datetime;
pub mod element;
pub mod event;
pub mod ffi; // FFI bindings
pub mod message;
pub mod name;
pub mod value; // Dynamic value type for typed extraction

// Session/Service/Request API (Task 9)
pub mod correlation; // Task 9
pub mod errors; // Task 9 (already existed)
pub mod identity; // Task 9
pub mod options; // Task 9 (already existed)
pub mod request; // Task 9
pub mod service; // Task 9
pub mod session; // Task 9
pub mod subscription; // Task 9

// Re-exports for convenience
pub use correlation::CorrelationId;
pub use datatype::DataType;
pub use datetime::HighPrecisionDatetime;
pub use element::Element;
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

/// Type alias for Message (compatibility with older code expecting MessageRef).
///
/// The Message type is already a reference-like wrapper around Bloomberg's
/// message pointer. This alias is provided for migration purposes.
pub type MessageRef<'a> = Message<'a>;

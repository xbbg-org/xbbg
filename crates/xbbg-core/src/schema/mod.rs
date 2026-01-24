//! Schema introspection types for Bloomberg services.
//!
//! This module provides safe Rust wrappers over Bloomberg's schema introspection API,
//! allowing runtime discovery of service operations, request/response schemas, and
//! enumeration values.
//!
//! # Overview
//!
//! Bloomberg services expose their schemas through a hierarchical structure:
//! - **Service** contains **Operations** (e.g., ReferenceDataRequest, HistoricalDataRequest)
//! - **Operations** have request and response **SchemaElementDefinitions**
//! - **SchemaElementDefinitions** reference **SchemaTypeDefinitions**
//! - **SchemaTypeDefinitions** can be simple types, complex types (with child elements),
//!   or enumeration types (with a **ConstantList** of valid values)
//!
//! # Example
//!
//! ```ignore
//! // Get service and introspect its schema
//! let service = session.get_service("//blp/refdata")?;
//!
//! // Iterate over all operations
//! for i in 0..service.num_operations() {
//!     let op = service.get_operation_at(i)?;
//!     println!("Operation: {}", op.name());
//!     
//!     // Get request schema
//!     if let Ok(req_def) = op.request_definition() {
//!         println!("  Request type: {}", req_def.name());
//!     }
//! }
//! ```
//!
//! # Note on Lifetimes
//!
//! All schema objects (Operation, SchemaElementDefinition, SchemaTypeDefinition,
//! ConstantList, Constant) are non-owning views into data managed by the Bloomberg
//! session. They remain valid as long as the session is active and the service
//! remains open.

mod constant;
mod element_def;
mod operation;
mod type_def;

pub use constant::{Constant, ConstantList};
pub use element_def::SchemaElementDefinition;
pub use operation::Operation;
pub use type_def::SchemaTypeDefinition;

/// Schema status values (deprecation status).
///
/// Mirrors Bloomberg's SchemaStatus enum.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(i32)]
pub enum SchemaStatus {
    /// This item is current and may appear in messages
    Active = 0,
    /// This item is current but will be removed in due course
    Deprecated = 1,
    /// This item is not current and will not appear in messages
    Inactive = 2,
    /// This item is expected to be deprecated in the future
    PendingDeprecation = 3,
}

impl SchemaStatus {
    /// Convert from raw integer status code.
    pub fn from_raw(value: i32) -> Self {
        match value {
            0 => SchemaStatus::Active,
            1 => SchemaStatus::Deprecated,
            2 => SchemaStatus::Inactive,
            3 => SchemaStatus::PendingDeprecation,
            _ => SchemaStatus::Active, // Default to active for unknown values
        }
    }
}

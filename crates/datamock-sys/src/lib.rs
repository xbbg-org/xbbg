//! Unsafe FFI bindings to datamock C API.
//!
//! This crate provides raw bindings to the datamock library, which simulates
//! Bloomberg BLPAPI for testing purposes.
//!
//! # Safety
//!
//! All functions in this crate are unsafe and should be used with care.
//! Prefer using higher-level safe wrappers when available.
//!
//! # Example
//!
//! ```ignore
//! use datamock_sys::*;
//!
//! unsafe {
//!     let opts = datamock_SessionOptions_create();
//!     let session = datamock_Session_create(opts);
//!     datamock_Session_start(session);
//!     // ... use session ...
//!     datamock_Session_destroy(session);
//!     datamock_SessionOptions_destroy(opts);
//! }
//! ```

#![no_std]
#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]
#![allow(dead_code)]
#![allow(clippy::all)]

include!(concat!(env!("OUT_DIR"), "/bindings.rs"));

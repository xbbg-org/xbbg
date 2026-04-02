//! # datamock
//!
//! A mock library for Bloomberg-style market data API, enabling testing without
//! a Bloomberg Terminal connection.
//!
//! This crate provides a C++ library that mimics the Bloomberg API interface,
//! allowing you to test applications that depend on market data without requiring
//! actual Bloomberg connectivity.
//!
//! ## Features
//!
//! - **Request/Response** (`//blp/refdata` service)
//!   - ReferenceDataRequest
//!   - HistoricalDataRequest
//!   - IntradayBarRequest
//!   - IntradayTickRequest
//!
//! - **Streaming** (`//blp/mktdata` service)
//!   - Real-time market data subscriptions via EventHandler
//!
//! ## Usage
//!
//! This crate builds a static C++ library. Link against it from your Rust code
//! or use it with `blpapi-sys` for testing purposes.

// The C++ library is built by build.rs and linked automatically.

#[allow(non_camel_case_types)]
#[allow(non_snake_case)]
#[allow(non_upper_case_globals)]
#[allow(dead_code)]
#[allow(clippy::all)]
mod ffi {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

pub use ffi::*;

//! Unified FFI abstraction over blpapi-sys (real) and datamock (mock).
//!
//! Default: mock mode (datamock backend)
//! Feature "live": real backend (blpapi-sys)

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]
#![allow(dead_code)]

// Mutual exclusivity check
#[cfg(all(feature = "mock", feature = "live"))]
compile_error!("Features 'mock' and 'live' are mutually exclusive");

#[cfg(not(any(feature = "mock", feature = "live")))]
compile_error!("Must enable either 'mock' or 'live' feature");

// Link the datamock C++ library when using mock backend
#[cfg(feature = "mock")]
#[link(name = "datamock", kind = "static")]
extern "C" {}

#[cfg(feature = "mock")]
mod mock_backend {
    // Re-export shim functions FIRST (these override bindings with same name)
    pub use crate::shim::*;

    // Re-export stubs (for functions not in shim or bindings)
    pub use crate::stubs::*;

    // Include renamed bindings from build.rs LAST
    // This way shim and stubs take precedence over bindings
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

#[cfg(feature = "live")]
mod live_backend {
    // Re-export everything from blpapi-sys
    pub use blpapi_sys::*;
}

// Public API - re-export from active backend
#[cfg(feature = "mock")]
pub use mock_backend::*;

#[cfg(feature = "live")]
pub use live_backend::*;

// Stubs module (only compiled in mock mode)
#[cfg(feature = "mock")]
mod stubs;

// Shim module (only compiled in mock mode)
#[cfg(feature = "mock")]
mod shim;

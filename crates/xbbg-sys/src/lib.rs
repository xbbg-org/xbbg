//! Unified FFI abstraction over blpapi-sys (real) and datamock (mock).
//!
//! Default: live mode (blpapi-sys backend)
//! Feature "mock": datamock backend (not yet production-ready)

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]
// Note: #[allow(dead_code)] is applied to the stubs module below, not crate-wide.
// The #[no_mangle] stubs satisfy the linker (not Rust), so Rust considers them unused.

// The mock backend (datamock) is not yet production-ready.
// ABI mismatches and missing stubs remain. Use 'live' only for now.
#[cfg(feature = "mock")]
compile_error!(
    "The 'mock' feature (datamock backend) is not yet production-ready. \
     Use the 'live' feature instead."
);

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
// Allow dead_code: these #[no_mangle] functions are linker symbols, not called from Rust.
#[cfg(feature = "mock")]
#[allow(dead_code)]
mod stubs;

// Shim module (only compiled in mock mode)
#[cfg(feature = "mock")]
mod shim;

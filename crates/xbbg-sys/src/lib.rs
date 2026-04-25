//! FFI abstraction over blpapi-sys.

#![allow(non_upper_case_globals)]
#![allow(non_camel_case_types)]
#![allow(non_snake_case)]

#[cfg(not(feature = "live"))]
compile_error!("The 'live' feature must be enabled");

#[cfg(feature = "live")]
mod live_backend {
    pub use blpapi_sys::*;
}

#[cfg(feature = "live")]
pub use live_backend::*;

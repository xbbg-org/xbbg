//! Identity for authenticated Bloomberg sessions

use crate::errors::{BlpError, Result};

/// Identity handle for authenticated Bloomberg sessions.
///
/// Identities are created by the session and used for authorization.
/// Required for accessing permissioned data or services.
///
/// # Examples
///
/// ```ignore
/// // Generate token and authorize
/// let identity = session.generate_token()?;
/// session.authorize(&identity)?;
///
/// // Use identity for permissioned requests
/// session.send_request(&req, Some(&identity), None)?;
/// ```
///
/// # Lifecycle
/// The identity is owned by the session and will be released when dropped.
pub struct Identity {
    ptr: *mut crate::ffi::blpapi_Identity_t,
}

// SAFETY: Identity can be sent between threads
// The underlying Bloomberg API allows identity to be used from different threads
unsafe impl Send for Identity {}

// SAFETY: Identity can be shared between threads
// The underlying Bloomberg API allows concurrent access to identity
unsafe impl Sync for Identity {}

impl Identity {
    /// Create an Identity from a raw pointer (internal use only)
    pub(crate) fn from_raw(ptr: *mut crate::ffi::blpapi_Identity_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null identity pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    /// Get the raw pointer (internal use only)
    pub(crate) fn as_ptr(&self) -> *mut crate::ffi::blpapi_Identity_t {
        self.ptr
    }
}

impl Drop for Identity {
    fn drop(&mut self) {
        // Note: Bloomberg API does not provide an explicit destroy function for Identity
        // The identity is managed by the session and will be cleaned up when the session is destroyed
        // We just null out the pointer to prevent use-after-free
        self.ptr = std::ptr::null_mut();
    }
}

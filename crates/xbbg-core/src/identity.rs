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
/// The identity is a reference-counted Bloomberg handle. The local SDK headers
/// do not document cross-thread use, so this wrapper is not `Send` or `Sync`.
pub struct Identity {
    ptr: *mut crate::ffi::blpapi_Identity_t,
}

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

    pub(crate) fn as_ptr(&self) -> *mut crate::ffi::blpapi_Identity_t {
        self.ptr
    }

    pub fn is_authorized(&self, service: &crate::Service<'_>) -> bool {
        let rc = unsafe { crate::ffi::blpapi_Identity_isAuthorized(self.ptr, service.as_ptr()) };
        rc != 0
    }

    pub fn has_entitlements(&self, service: &crate::Service<'_>, eids: &[i32]) -> Result<bool> {
        let mut failed_count: i32 = 0;
        let rc = unsafe {
            crate::ffi::blpapi_Identity_hasEntitlements(
                self.ptr,
                service.as_ptr(),
                std::ptr::null(),
                eids.as_ptr(),
                eids.len(),
                std::ptr::null_mut(),
                &mut failed_count,
            )
        };
        if rc < 0 {
            return Err(BlpError::Internal {
                detail: format!("hasEntitlements failed: rc={rc}"),
            });
        }
        Ok(failed_count == 0)
    }

    pub fn seat_type(&self) -> Result<SeatType> {
        let mut raw: i32 = -1;
        let rc = unsafe { crate::ffi::blpapi_Identity_getSeatType(self.ptr, &mut raw) };
        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("getSeatType failed: rc={rc}"),
            });
        }
        Ok(SeatType::from_raw(raw))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SeatType {
    Bps,
    NonBps,
    Invalid,
}

impl SeatType {
    fn from_raw(raw: i32) -> Self {
        match raw {
            0 => Self::Bps,
            1 => Self::NonBps,
            _ => Self::Invalid,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Bps => "BPS",
            Self::NonBps => "NONBPS",
            Self::Invalid => "INVALID",
        }
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

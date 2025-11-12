use std::ffi::{CStr, CString};
use std::fmt;

use crate::errors::{BlpError, Result};

/// Bloomberg SDK `Name` wrapper.
///
/// Interns strings in the SDK for efficient comparisons and lookups.
pub struct Name {
    ptr: *mut blpapi_sys::blpapi_Name_t,
}

unsafe impl Send for Name {}
unsafe impl Sync for Name {}

impl Name {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Name_t) -> Self {
        // duplicate to own
        let dup = unsafe { blpapi_sys::blpapi_Name_duplicate(ptr) };
        Self { ptr: dup }
    }

    /// Create (intern) a name from a string.
    pub fn new(s: &str) -> Result<Self> {
        let cs = CString::new(s).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid name (nul byte): {e}"),
        })?;
        let ptr = unsafe { blpapi_sys::blpapi_Name_create(cs.as_ptr()) };
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "blpapi_Name_create returned null".into(),
            });
        }
        Ok(Self { ptr })
    }

    /// Find an existing name if already interned (non-allocating).
    pub fn find(s: &str) -> Option<Self> {
        let cs = CString::new(s).ok()?;
        let ptr = unsafe { blpapi_sys::blpapi_Name_findName(cs.as_ptr()) };
        if ptr.is_null() {
            None
        } else {
            // duplicate to own a destroyable handle
            let dup = unsafe { blpapi_sys::blpapi_Name_duplicate(ptr) };
            if dup.is_null() {
                None
            } else {
                Some(Self { ptr: dup })
            }
        }
    }

    /// Return the underlying string.
    pub fn as_str(&self) -> &str {
        let cptr = unsafe { blpapi_sys::blpapi_Name_string(self.ptr) };
        if cptr.is_null() {
            ""
        } else {
            unsafe { CStr::from_ptr(cptr) }.to_str().unwrap_or_default()
        }
    }

    /// Length of the underlying string.
    pub fn len(&self) -> usize {
        unsafe { blpapi_sys::blpapi_Name_length(self.ptr) as usize }
    }

    #[allow(dead_code)]
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_Name_t {
        self.ptr
    }
}

impl Clone for Name {
    fn clone(&self) -> Self {
        let dup = unsafe { blpapi_sys::blpapi_Name_duplicate(self.ptr) };
        Self { ptr: dup }
    }
}

impl Drop for Name {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_Name_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

impl fmt::Debug for Name {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Name({})", self.as_str())
    }
}

impl fmt::Display for Name {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}



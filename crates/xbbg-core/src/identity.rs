use crate::errors::{BlpError, Result};

pub struct Identity {
    ptr: *mut blpapi_sys::blpapi_Identity_t,
}

unsafe impl Send for Identity {}
unsafe impl Sync for Identity {}

impl Identity {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Identity_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null identity pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    #[allow(dead_code)]
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_Identity_t {
        self.ptr
    }
}

impl Drop for Identity {
    fn drop(&mut self) {
        // blpapi has no explicit destroy call for identity; it is owned by session.
        self.ptr = std::ptr::null_mut();
    }
}



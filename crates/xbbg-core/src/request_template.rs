use crate::errors::{BlpError, Result};

pub struct RequestTemplate {
    ptr: *mut blpapi_sys::blpapi_RequestTemplate_t,
}

unsafe impl Send for RequestTemplate {}
unsafe impl Sync for RequestTemplate {}

impl RequestTemplate {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_RequestTemplate_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null request template pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    #[allow(dead_code)]
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_RequestTemplate_t {
        self.ptr
    }
}

impl Drop for RequestTemplate {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // refcounted; release via API function
            unsafe { blpapi_sys::blpapi_RequestTemplate_release(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}


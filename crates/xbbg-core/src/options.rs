use std::ffi::CString;

use crate::errors::{BlpError, Result};

/// Safe wrapper around `blpapi_SessionOptions_t`.
pub struct SessionOptions {
    ptr: *mut blpapi_sys::blpapi_SessionOptions_t,
}

unsafe impl Send for SessionOptions {}
unsafe impl Sync for SessionOptions {}

impl SessionOptions {
    pub fn new() -> Result<Self> {
        let ptr = unsafe { blpapi_sys::blpapi_SessionOptions_create() };
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "blpapi_SessionOptions_create returned null".into(),
            });
        }
        Ok(Self { ptr })
    }

    pub fn set_server_host(&mut self, host: &str) -> Result<&mut Self> {
        let cs = CString::new(host).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid host: {e}"),
        })?;
        unsafe { blpapi_sys::blpapi_SessionOptions_setServerHost(self.ptr, cs.as_ptr()) };
        Ok(self)
    }

    pub fn set_server_port(&mut self, port: u16) -> &mut Self {
        unsafe { blpapi_sys::blpapi_SessionOptions_setServerPort(self.ptr, port) };
        self
    }

    pub fn set_default_subscription_service(&mut self, svc: &str) -> Result<&mut Self> {
        let cs = CString::new(svc).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid service: {e}"),
        })?;
        unsafe {
            blpapi_sys::blpapi_SessionOptions_setDefaultSubscriptionService(self.ptr, cs.as_ptr())
        };
        Ok(self)
    }

    pub fn set_default_topic_prefix(&mut self, prefix: &str) -> Result<&mut Self> {
        let cs = CString::new(prefix).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid prefix: {e}"),
        })?;
        unsafe { blpapi_sys::blpapi_SessionOptions_setDefaultTopicPrefix(self.ptr, cs.as_ptr()) };
        Ok(self)
    }

    pub fn set_record_subscription_receive_times(&mut self, record: bool) -> &mut Self {
        unsafe {
            blpapi_sys::blpapi_SessionOptions_setRecordSubscriptionDataReceiveTimes(
                self.ptr,
                record as i32,
            )
        };
        self
    }

    pub fn set_connect_timeout_ms(&mut self, timeout_ms: u32) -> Result<&mut Self> {
        let rc = unsafe {
            blpapi_sys::blpapi_SessionOptions_setConnectTimeout(self.ptr, timeout_ms)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("connect timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    pub fn set_service_check_timeout_ms(&mut self, timeout_ms: i32) -> Result<&mut Self> {
        let rc =
            unsafe { blpapi_sys::blpapi_SessionOptions_setServiceCheckTimeout(self.ptr, timeout_ms) };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("service check timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    pub fn set_service_download_timeout_ms(&mut self, timeout_ms: i32) -> Result<&mut Self> {
        let rc = unsafe {
            blpapi_sys::blpapi_SessionOptions_setServiceDownloadTimeout(self.ptr, timeout_ms)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("service download timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_SessionOptions_t {
        self.ptr
    }
}

impl Drop for SessionOptions {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_SessionOptions_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}



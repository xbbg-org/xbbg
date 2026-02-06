use std::ffi::CString;

use crate::errors::{BlpError, Result};
use crate::ffi;

/// Safe wrapper around `blpapi_SessionOptions_t`.
pub struct SessionOptions {
    ptr: *mut ffi::blpapi_SessionOptions_t,
}

unsafe impl Send for SessionOptions {}
unsafe impl Sync for SessionOptions {}

impl SessionOptions {
    pub fn new() -> Result<Self> {
        // SAFETY: blpapi_SessionOptions_create allocates and returns a valid pointer or null.
        let ptr = unsafe { ffi::blpapi_SessionOptions_create() };
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
        // SAFETY: self.ptr is valid (checked in new()), cs is a valid null-terminated C string.
        unsafe { ffi::blpapi_SessionOptions_setServerHost(self.ptr, cs.as_ptr()) };
        Ok(self)
    }

    pub fn set_server_port(&mut self, port: u16) -> &mut Self {
        // SAFETY: self.ptr is valid (checked in new()).
        unsafe { ffi::blpapi_SessionOptions_setServerPort(self.ptr, port) };
        self
    }

    pub fn set_default_subscription_service(&mut self, svc: &str) -> Result<&mut Self> {
        let cs = CString::new(svc).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid service: {e}"),
        })?;
        // SAFETY: FFI call with valid pointers
        unsafe {
            ffi::blpapi_SessionOptions_setDefaultSubscriptionService(self.ptr, cs.as_ptr());
        }
        Ok(self)
    }

    pub fn set_default_topic_prefix(&mut self, prefix: &str) -> Result<&mut Self> {
        let cs = CString::new(prefix).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid prefix: {e}"),
        })?;
        // SAFETY: FFI call with valid pointers
        unsafe {
            ffi::blpapi_SessionOptions_setDefaultTopicPrefix(self.ptr, cs.as_ptr());
        }
        Ok(self)
    }

    pub fn set_record_subscription_receive_times(&mut self, record: bool) -> &mut Self {
        // SAFETY: FFI call with valid pointer
        unsafe {
            ffi::blpapi_SessionOptions_setRecordSubscriptionDataReceiveTimes(
                self.ptr,
                record as i32,
            );
        }
        self
    }

    pub fn set_connect_timeout_ms(&mut self, timeout_ms: u32) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe { ffi::blpapi_SessionOptions_setConnectTimeout(self.ptr, timeout_ms) };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("connect timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    pub fn set_service_check_timeout_ms(&mut self, timeout_ms: i32) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe { ffi::blpapi_SessionOptions_setServiceCheckTimeout(self.ptr, timeout_ms) };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("service check timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    pub fn set_service_download_timeout_ms(&mut self, timeout_ms: i32) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc =
            unsafe { ffi::blpapi_SessionOptions_setServiceDownloadTimeout(self.ptr, timeout_ms) };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("service download timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    // ========== Performance Tuning Options ==========

    /// Set the maximum number of events that can be queued.
    ///
    /// Larger queue sizes can improve throughput but increase memory usage.
    /// Default is typically 10000. For high-volume use cases, consider 65536+.
    pub fn set_max_event_queue_size(&mut self, size: usize) -> &mut Self {
        // SAFETY: FFI call with valid pointer
        unsafe {
            ffi::blpapi_SessionOptions_setMaxEventQueueSize(self.ptr, size);
        }
        self
    }

    /// Get the current maximum event queue size.
    pub fn max_event_queue_size(&self) -> usize {
        // SAFETY: FFI call with valid pointer
        unsafe { ffi::blpapi_SessionOptions_maxEventQueueSize(self.ptr) }
    }

    /// Set the high watermark for slow consumer warnings (0.0 to 1.0).
    ///
    /// When queue usage exceeds this fraction, slow consumer warnings are generated.
    /// Default is typically 0.75.
    pub fn set_slow_consumer_warning_hi_watermark(
        &mut self,
        hi_watermark: f32,
    ) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe {
            ffi::blpapi_SessionOptions_setSlowConsumerWarningHiWaterMark(self.ptr, hi_watermark)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("slow consumer hi watermark invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    /// Set the low watermark for slow consumer warnings (0.0 to 1.0).
    ///
    /// When queue usage drops below this fraction after being above hi watermark,
    /// the slow consumer state is cleared. Default is typically 0.5.
    pub fn set_slow_consumer_warning_lo_watermark(
        &mut self,
        lo_watermark: f32,
    ) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe {
            ffi::blpapi_SessionOptions_setSlowConsumerWarningLoWaterMark(self.ptr, lo_watermark)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("slow consumer lo watermark invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    /// Enable or disable keep-alive messages.
    ///
    /// Keep-alive helps detect dead connections. Enabled by default.
    pub fn set_keep_alive_enabled(&mut self, enabled: bool) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc =
            unsafe { ffi::blpapi_SessionOptions_setKeepAliveEnabled(self.ptr, enabled as i32) };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("keep alive enabled invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    /// Set the keep-alive inactivity time in milliseconds.
    ///
    /// Time of inactivity before sending keep-alive. Default is typically 20000ms.
    pub fn set_keep_alive_inactivity_time_ms(&mut self, time_ms: i32) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe {
            ffi::blpapi_SessionOptions_setDefaultKeepAliveInactivityTime(self.ptr, time_ms)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("keep alive inactivity time invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    /// Set the keep-alive response timeout in milliseconds.
    ///
    /// Time to wait for keep-alive response. Default is typically 5000ms.
    pub fn set_keep_alive_response_timeout_ms(&mut self, timeout_ms: i32) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe {
            ffi::blpapi_SessionOptions_setDefaultKeepAliveResponseTimeout(self.ptr, timeout_ms)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("keep alive response timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    /// Disable bandwidth save mode.
    ///
    /// When disabled, the API uses more bandwidth but may have lower latency.
    /// This is useful for high-frequency data scenarios.
    pub fn set_bandwidth_save_mode_disabled(&mut self, disabled: bool) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe {
            ffi::blpapi_SessionOptions_setBandwidthSaveModeDisabled(self.ptr, disabled as i32)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("bandwidth save mode disabled invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    /// Set the flush published events timeout in milliseconds.
    ///
    /// Controls how long to wait when flushing events. Default is typically 2000ms.
    pub fn set_flush_published_events_timeout_ms(&mut self, timeout_ms: i32) -> Result<&mut Self> {
        // SAFETY: FFI call with valid pointer
        let rc = unsafe {
            ffi::blpapi_SessionOptions_setFlushPublishedEventsTimeout(self.ptr, timeout_ms)
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("flush published events timeout invalid: rc={rc}"),
            });
        }
        Ok(self)
    }

    pub(crate) fn as_raw(&self) -> *mut ffi::blpapi_SessionOptions_t {
        self.ptr
    }
}

impl Drop for SessionOptions {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // SAFETY: self.ptr is valid and we own it. Drop is called exactly once.
            unsafe { ffi::blpapi_SessionOptions_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

//! Bloomberg service handle

use std::ffi::CString;

use crate::errors::{BlpError, Result};
use crate::request::Request;

/// Service handle for creating requests.
///
/// A Service is obtained from a Session after opening the service.
/// Services are immutable after creation and can be safely shared across threads.
///
/// # Examples
///
/// ```ignore
/// // Open service
/// session.open_service("//blp/refdata")?;
/// let svc = session.get_service("//blp/refdata")?;
///
/// // Create request
/// let req = svc.create_request("ReferenceDataRequest")?;
/// ```
pub struct Service {
    ptr: *mut crate::ffi::blpapi_Service_t,
}

// SAFETY: Service can be sent between threads
// The underlying Bloomberg API allows service handles to be used from different threads
unsafe impl Send for Service {}

// SAFETY: Service can be shared between threads
// Service is immutable after get_service() and can be safely accessed concurrently
unsafe impl Sync for Service {}

impl Service {
    /// Create a Service from a raw pointer (internal use only)
    pub(crate) fn from_raw(ptr: *mut crate::ffi::blpapi_Service_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null service pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    /// Get the raw pointer (internal use only)
    #[allow(dead_code)] // Used in integration, not unit tests
    pub(crate) fn as_ptr(&self) -> *mut crate::ffi::blpapi_Service_t {
        self.ptr
    }

    /// Create a new request for the specified operation.
    ///
    /// Common operations:
    /// - `"ReferenceDataRequest"` - Get reference data for securities
    /// - `"HistoricalDataRequest"` - Get historical time series data
    /// - `"IntradayBarRequest"` - Get intraday bar data
    ///
    /// # Arguments
    /// * `operation` - The operation name (e.g., "ReferenceDataRequest")
    ///
    /// # Returns
    /// A new Request object that can be populated and sent
    pub fn create_request(&self, operation: &str) -> Result<Request> {
        let c_operation = CString::new(operation).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid operation name: {}", e),
        })?;

        let mut req_ptr: *mut crate::ffi::blpapi_Request_t = std::ptr::null_mut();

        // SAFETY: We're calling the Bloomberg API with valid pointers
        // - self.ptr is guaranteed non-null by from_raw()
        // - req_ptr is a valid mutable pointer
        // - c_operation is a valid C string
        let rc = unsafe {
            crate::ffi::blpapi_Service_createRequest(self.ptr, &mut req_ptr, c_operation.as_ptr())
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Service_createRequest failed with rc={}", rc),
            });
        }

        Request::from_raw(req_ptr)
    }

    /// Get the service name.
    ///
    /// Returns the full service URI (e.g., "//blp/refdata").
    ///
    /// # Returns
    /// The service name as a string slice
    pub fn name(&self) -> &str {
        // SAFETY: We're calling the Bloomberg API with a valid pointer
        // The returned pointer is valid for the lifetime of the Service
        unsafe {
            let name_ptr = crate::ffi::blpapi_Service_name(self.ptr);
            if name_ptr.is_null() {
                return "";
            }

            // Convert C string to Rust string
            let c_str = std::ffi::CStr::from_ptr(name_ptr);
            c_str.to_str().unwrap_or("")
        }
    }
}

// Note: Service does NOT implement Drop
// The service pointer is managed by the session and will be cleaned up
// when the session is destroyed

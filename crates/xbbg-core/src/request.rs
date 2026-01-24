//! Bloomberg request building

use std::ffi::CString;

use crate::element::Element;
use crate::errors::{BlpError, Result};
use crate::name::Name;

/// Request object for sending to Bloomberg services.
///
/// Requests are created by calling `Service::create_request()` and then
/// populated with data before being sent via `Session::send_request()`.
///
/// # Examples
///
/// ```ignore
/// // Pre-intern names at setup (do once)
/// let securities = Name::get_or_intern("securities");
/// let fields = Name::get_or_intern("fields");
///
/// let mut req = svc.create_request("ReferenceDataRequest")?;
///
/// // Add securities
/// req.append_string(&securities, "IBM US Equity")?;
/// req.append_string(&securities, "AAPL US Equity")?;
///
/// // Add fields
/// req.append_string(&fields, "PX_LAST")?;
/// req.append_string(&fields, "SECURITY_NAME")?;
///
/// // Send request
/// session.send_request(&req, None, None)?;
/// ```
pub struct Request {
    ptr: *mut crate::ffi::blpapi_Request_t,
}

// SAFETY: Request can be sent between threads
unsafe impl Send for Request {}

// SAFETY: Request can be shared between threads (though typically used from one thread)
unsafe impl Sync for Request {}

impl Request {
    /// Create a Request from a raw pointer (internal use only)
    pub(crate) fn from_raw(ptr: *mut crate::ffi::blpapi_Request_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null request pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    /// Get the raw pointer (internal use only)
    pub(crate) fn as_ptr(&self) -> *mut crate::ffi::blpapi_Request_t {
        self.ptr
    }

    /// Get the root element of this request for manipulation.
    ///
    /// This provides low-level access to the request structure.
    /// For most use cases, the convenience methods like `append_string()` are preferred.
    pub fn elements(&self) -> Element<'_> {
        // SAFETY: We're calling the Bloomberg API with a valid pointer
        // The returned element is valid for the lifetime of the Request
        unsafe {
            let elem_ptr = crate::ffi::blpapi_Request_elements(self.ptr);
            Element::new(elem_ptr)
        }
    }

    /// Get a child element by name
    ///
    /// This is a convenience method that calls `elements().get(name)`.
    pub fn get(&self, name: &Name) -> Option<Element<'_>> {
        self.elements().get(name)
    }

    /// Append a string value to an array element.
    ///
    /// This is commonly used for adding securities or fields to a request.
    /// The array element must exist in the request schema.
    ///
    /// # Example
    /// ```ignore
    /// let securities = Name::get_or_intern("securities");
    /// let fields = Name::get_or_intern("fields");
    /// req.append_string(&securities, "IBM US Equity")?;
    /// req.append_string(&securities, "AAPL US Equity")?;
    /// req.append_string(&fields, "PX_LAST")?;
    /// ```
    pub fn append_string(&mut self, array_name: &Name, value: &str) -> Result<()> {
        let root = self.elements();
        let array_elem = root
            .get(array_name)
            .ok_or_else(|| BlpError::InvalidArgument {
                detail: format!("element '{}' not found", array_name.as_str()),
            })?;

        let c_value = CString::new(value).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid string value: {}", e),
        })?;

        // SAFETY: We're calling the Bloomberg API with valid pointers
        // - array_elem.as_ptr() is valid for the lifetime of the element
        // - c_value is a valid C string
        // - BLPAPI_ELEMENT_INDEX_END indicates append operation
        let rc = unsafe {
            crate::ffi::blpapi_Element_setValueString(
                array_elem.as_ptr(),
                c_value.as_ptr(),
                crate::ffi::BLPAPI_ELEMENT_INDEX_END as usize,
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Element_setValueString failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Append a string value to an array element by string name.
    ///
    /// Convenience method that takes a string name instead of a Name reference.
    /// Slightly slower than `append_string()` but more convenient for simple use cases.
    ///
    /// # Example
    /// ```ignore
    /// req.append_str("securities", "IBM US Equity")?;
    /// req.append_str("securities", "AAPL US Equity")?;
    /// req.append_str("fields", "PX_LAST")?;
    /// ```
    pub fn append_str(&mut self, array_name: &str, value: &str) -> Result<()> {
        let root = self.elements();
        let array_elem = root
            .get_by_str(array_name)
            .ok_or_else(|| BlpError::InvalidArgument {
                detail: format!("element '{}' not found", array_name),
            })?;

        let c_value = CString::new(value).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid string value: {}", e),
        })?;

        // SAFETY: array_elem.as_ptr() is valid, c_value is a valid C string.
        // BLPAPI_ELEMENT_INDEX_END indicates append operation.
        let rc = unsafe {
            crate::ffi::blpapi_Element_setValueString(
                array_elem.as_ptr(),
                c_value.as_ptr(),
                crate::ffi::BLPAPI_ELEMENT_INDEX_END as usize,
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Element_setValueString failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Set a string value on an element
    pub fn set_string(&mut self, name: &Name, value: &str) -> Result<()> {
        let root = self.elements();

        let c_name = CString::new(name.as_str()).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid name: {}", e),
        })?;

        let c_value = CString::new(value).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid string value: {}", e),
        })?;

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Element_setElementString(
                root.as_ptr(),
                c_name.as_ptr(),
                std::ptr::null(),
                c_value.as_ptr(),
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Element_setElementString failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Set an i32 value on an element
    pub fn set_i32(&mut self, name: &Name, value: i32) -> Result<()> {
        let root = self.elements();

        let c_name = CString::new(name.as_str()).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid name: {}", e),
        })?;

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Element_setElementInt32(
                root.as_ptr(),
                c_name.as_ptr(),
                std::ptr::null(),
                value,
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Element_setElementInt32 failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Set an i64 value on an element by name.
    ///
    /// Gets the child element by name, then sets its value.
    pub fn set_i64(&mut self, name: &Name, value: i64) -> Result<()> {
        let root = self.elements();
        let child = root.get(name).ok_or_else(|| BlpError::InvalidArgument {
            detail: format!("element '{}' not found", name.as_str()),
        })?;

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Element_setValueInt64(
                child.as_ptr(),
                value,
                0, // index 0 for non-array elements
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Element_setValueInt64 failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Set an f64 value on an element
    pub fn set_f64(&mut self, name: &Name, value: f64) -> Result<()> {
        let root = self.elements();

        let c_name = CString::new(name.as_str()).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid name: {}", e),
        })?;

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Element_setElementFloat64(
                root.as_ptr(),
                c_name.as_ptr(),
                std::ptr::null(),
                value,
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Element_setElementFloat64 failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Set a bool value on an element
    pub fn set_bool(&mut self, name: &Name, value: bool) -> Result<()> {
        let root = self.elements();

        let c_name = CString::new(name.as_str()).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid name: {}", e),
        })?;

        // Bloomberg API uses int for bool (0 = false, non-zero = true)
        let int_value = if value { 1 } else { 0 };

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Element_setElementInt32(
                root.as_ptr(),
                c_name.as_ptr(),
                std::ptr::null(),
                int_value,
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!(
                    "blpapi_Element_setElementInt32 (bool) failed with rc={}",
                    rc
                ),
            });
        }

        Ok(())
    }
}

impl Drop for Request {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // SAFETY: We own this pointer and it's valid.
            // blpapi_Request_destroy releases the request resources.
            unsafe {
                crate::ffi::blpapi_Request_destroy(self.ptr);
            }
            self.ptr = std::ptr::null_mut();
        }
    }
}

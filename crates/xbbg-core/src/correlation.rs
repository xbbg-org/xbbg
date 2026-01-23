//! Correlation ID for tracking requests and subscriptions

use std::ffi::c_void;

/// Correlation ID used to match requests/subscriptions with responses.
///
/// Correlation IDs allow you to track which responses correspond to which requests.
/// Most commonly used as integer IDs, but pointer IDs are supported for advanced use cases.
///
/// # Examples
///
/// ```
/// use xbbg_core::CorrelationId;
///
/// // Integer correlation ID (most common)
/// let cid = CorrelationId::new_int(42);
/// assert_eq!(cid.as_int(), Some(42));
///
/// // Default is Int(0)
/// let default_cid = CorrelationId::default();
/// assert_eq!(default_cid.as_int(), Some(0));
/// ```
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CorrelationId {
    /// Integer correlation ID
    Int(i64),
    /// Pointer correlation ID (for advanced use cases)
    Ptr(*mut c_void),
}

impl Default for CorrelationId {
    fn default() -> Self {
        CorrelationId::Int(0)
    }
}

impl CorrelationId {
    /// Create a new integer correlation ID.
    ///
    /// This is the most common way to create correlation IDs.
    pub fn new_int(value: i64) -> Self {
        CorrelationId::Int(value)
    }

    /// Create a new pointer correlation ID.
    ///
    /// Advanced use case - allows associating arbitrary pointers with requests.
    pub fn new_ptr(ptr: *mut c_void) -> Self {
        CorrelationId::Ptr(ptr)
    }

    /// Get the integer value if this is an Int variant.
    ///
    /// Returns `None` if this is a Ptr variant.
    pub fn as_int(&self) -> Option<i64> {
        match self {
            CorrelationId::Int(v) => Some(*v),
            _ => None,
        }
    }

    /// Get the pointer value if this is a Ptr variant.
    ///
    /// Returns `None` if this is an Int variant.
    pub fn as_ptr(&self) -> Option<*mut c_void> {
        match self {
            CorrelationId::Ptr(p) => Some(*p),
            _ => None,
        }
    }

    /// Convert to FFI representation.
    ///
    /// Uses Bloomberg's helper functions to properly initialize the CorrelationId struct,
    /// including the valueType bitfield.
    pub(crate) fn to_ffi(&self) -> crate::ffi::blpapi_CorrelationId_t {
        unsafe {
            let mut cid = std::mem::zeroed::<crate::ffi::blpapi_CorrelationId_t>();
            crate::ffi::blpapi_CorrelationId_init(&mut cid);
            match self {
                CorrelationId::Int(v) => {
                    crate::ffi::blpapi_CorrelationId_setInt(&mut cid, *v as u64);
                }
                CorrelationId::Ptr(p) => {
                    crate::ffi::blpapi_CorrelationId_setPointer(&mut cid, *p);
                }
            }
            cid
        }
    }

    /// Create from FFI representation.
    ///
    /// Uses Bloomberg's helper functions to properly read the valueType and extract
    /// the correct value from the union.
    #[allow(dead_code)] // Used in integration, not unit tests
    pub(crate) fn from_ffi(cid: &mut crate::ffi::blpapi_CorrelationId_t) -> Self {
        // Constants from Bloomberg API
        const CORRELATION_TYPE_UNSET: i32 = 0;
        const CORRELATION_TYPE_INT: i32 = 1;
        const CORRELATION_TYPE_POINTER: i32 = 2;

        unsafe {
            let value_type = crate::ffi::blpapi_CorrelationId_type(cid);
            match value_type {
                CORRELATION_TYPE_INT => {
                    let value = crate::ffi::blpapi_CorrelationId_asInt(cid);
                    CorrelationId::Int(value as i64)
                }
                CORRELATION_TYPE_POINTER => {
                    let ptr = crate::ffi::blpapi_CorrelationId_asPointer(cid);
                    CorrelationId::Ptr(ptr)
                }
                CORRELATION_TYPE_UNSET | _ => {
                    // Unset or unknown type - default to Int(0)
                    CorrelationId::Int(0)
                }
            }
        }
    }
}

// SAFETY: CorrelationId can be safely sent between threads
// - Int variant is just an i64
// - Ptr variant is a raw pointer, which is Send (caller must ensure validity)
unsafe impl Send for CorrelationId {}

// SAFETY: CorrelationId can be safely shared between threads
// - Int variant is just an i64
// - Ptr variant is a raw pointer, which is Sync (caller must ensure validity)
unsafe impl Sync for CorrelationId {}

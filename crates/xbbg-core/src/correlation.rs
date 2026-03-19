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
/// // Default is unset so the Bloomberg SDK can autogenerate one when needed.
/// let default_cid = CorrelationId::default();
/// assert!(matches!(default_cid, CorrelationId::Unset));
/// ```
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub enum CorrelationId {
    /// Unset correlation ID. The Bloomberg SDK may autogenerate one internally.
    #[default]
    Unset,
    /// Integer correlation ID
    Int(i64),
    /// Pointer correlation ID (for advanced use cases)
    Ptr(*mut c_void),
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
    /// Directly initializes the CorrelationId struct fields.
    pub(crate) fn to_ffi(&self) -> crate::ffi::blpapi_CorrelationId_t {
        // SAFETY: zeroed memory is valid for blpapi_CorrelationId_t, then we
        // set the appropriate bitfields and union member.
        unsafe {
            let mut cid = std::mem::zeroed::<crate::ffi::blpapi_CorrelationId_t>();
            cid.set_size(std::mem::size_of::<crate::ffi::blpapi_CorrelationId_t>() as u32);
            match self {
                CorrelationId::Unset => {
                    cid.set_valueType(crate::ffi::BLPAPI_CORRELATION_TYPE_UNSET);
                }
                CorrelationId::Int(v) => {
                    cid.set_valueType(crate::ffi::BLPAPI_CORRELATION_TYPE_INT);
                    cid.value.intValue = *v as u64;
                }
                CorrelationId::Ptr(p) => {
                    cid.set_valueType(crate::ffi::BLPAPI_CORRELATION_TYPE_POINTER);
                    cid.value.ptrValue.pointer = *p;
                }
            }
            cid
        }
    }

    /// Create from FFI representation.
    ///
    /// Reads the valueType bitfield and extracts the correct union member.
    pub fn from_ffi(cid: &crate::ffi::blpapi_CorrelationId_t) -> Self {
        // SAFETY: cid is a valid struct from Bloomberg API. We read the valueType
        // bitfield and access the correct union member.
        let value_type = cid.valueType();
        match value_type {
            x if x == crate::ffi::BLPAPI_CORRELATION_TYPE_UNSET => CorrelationId::Unset,
            x if x == crate::ffi::BLPAPI_CORRELATION_TYPE_INT => {
                // SAFETY: valueType indicates this is an int value
                let value = unsafe { cid.value.intValue };
                CorrelationId::Int(value as i64)
            }
            x if x == crate::ffi::BLPAPI_CORRELATION_TYPE_AUTOGEN => {
                // SAFETY: Bloomberg documents AUTOGEN correlation IDs as integer-valued.
                let value = unsafe { cid.value.intValue };
                CorrelationId::Int(value as i64)
            }
            x if x == crate::ffi::BLPAPI_CORRELATION_TYPE_POINTER => {
                // SAFETY: valueType indicates this is a pointer value
                let ptr = unsafe { cid.value.ptrValue.pointer };
                CorrelationId::Ptr(ptr)
            }
            _ => CorrelationId::Unset,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_unset() {
        assert_eq!(CorrelationId::default(), CorrelationId::Unset);
    }

    #[test]
    fn unset_round_trips_through_ffi() {
        let cid = CorrelationId::Unset;
        let ffi_cid = cid.to_ffi();

        assert_eq!(
            ffi_cid.valueType(),
            crate::ffi::BLPAPI_CORRELATION_TYPE_UNSET
        );
        assert_eq!(CorrelationId::from_ffi(&ffi_cid), CorrelationId::Unset);
    }

    #[test]
    fn autogen_ffi_maps_to_integer_correlation_id() {
        let mut ffi_cid = unsafe { std::mem::zeroed::<crate::ffi::blpapi_CorrelationId_t>() };
        ffi_cid.set_size(std::mem::size_of::<crate::ffi::blpapi_CorrelationId_t>() as u32);
        ffi_cid.set_valueType(crate::ffi::BLPAPI_CORRELATION_TYPE_AUTOGEN);
        ffi_cid.value.intValue = 123;

        assert_eq!(CorrelationId::from_ffi(&ffi_cid), CorrelationId::Int(123));
    }
}

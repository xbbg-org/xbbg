use std::sync::Arc;

/// High-level correlation id used across requests/subscriptions.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CorrelationId {
    U64(u64),
    /// Safe tag; held by the library to ensure backing memory outlives in-flight ops.
    Tag(Arc<str>),
}

impl CorrelationId {
    pub fn as_u64(&self) -> Option<u64> {
        match self {
            CorrelationId::U64(v) => Some(*v),
            _ => None,
        }
    }

    pub fn as_tag(&self) -> Option<&str> {
        match self {
            CorrelationId::Tag(s) => Some(s.as_ref()),
            _ => None,
        }
    }

    pub(crate) fn to_ffi_u64(value: u64) -> blpapi_sys::blpapi_CorrelationId_t {
        let mut cid = unsafe { std::mem::zeroed::<blpapi_sys::blpapi_CorrelationId_t>() };
        unsafe { blpapi_sys::blpapiext_cid_from_u64(&mut cid as *mut _, value) };
        cid
    }

    pub(crate) fn to_ffi_ptr(ptr: *const core::ffi::c_void) -> blpapi_sys::blpapi_CorrelationId_t {
        let mut cid = unsafe { std::mem::zeroed::<blpapi_sys::blpapi_CorrelationId_t>() };
        unsafe { blpapi_sys::blpapiext_cid_from_ptr(&mut cid as *mut _, ptr) };
        cid
    }

    pub(crate) fn to_ffi_autogen() -> blpapi_sys::blpapi_CorrelationId_t {
        let mut cid = unsafe { std::mem::zeroed::<blpapi_sys::blpapi_CorrelationId_t>() };
        unsafe { blpapi_sys::blpapiext_cid_autogen(&mut cid as *mut _) };
        cid
    }

    pub(crate) fn to_ffi(&self) -> blpapi_sys::blpapi_CorrelationId_t {
        match self {
            CorrelationId::U64(v) => Self::to_ffi_u64(*v),
            CorrelationId::Tag(s) => {
                let ptr = s.as_ptr() as *const core::ffi::c_void;
                Self::to_ffi_ptr(ptr)
            }
        }
    }
}



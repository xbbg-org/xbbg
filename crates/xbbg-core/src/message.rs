use std::ffi::CStr;
use std::sync::Arc;

use crate::correlation::CorrelationId;
use crate::name::Name;
use crate::tag_registry::TAG_REGISTRY;

pub struct MessageRef {
    ptr: *mut blpapi_sys::blpapi_Message_t,
    // Borrowed by iterator; do not release
}

#[allow(dead_code)]
pub struct MessageOwned {
    ptr: *mut blpapi_sys::blpapi_Message_t,
}

impl MessageRef {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Message_t) -> Option<Self> {
        if ptr.is_null() {
            None
        } else {
            Some(Self { ptr })
        }
    }

    pub fn elements(&self) -> crate::element::ElementRef {
        let el_ptr = unsafe { blpapi_sys::blpapi_Message_elements(self.ptr) };
        crate::element::ElementRef::from_raw(el_ptr).expect("message elements")
    }

    pub fn payload_definition(&self) -> crate::schema::SchemaElementDefinition {
        let el_ptr = unsafe { blpapi_sys::blpapi_Message_elements(self.ptr) };
        let def_ptr = unsafe { blpapi_sys::blpapi_Element_definition(el_ptr) };
        crate::schema::SchemaElementDefinition::from_raw(def_ptr).expect("payload definition")
    }
    pub fn message_type(&self) -> Name {
        let name_ptr = unsafe { blpapi_sys::blpapi_Message_messageType(self.ptr) };
        Name::from_raw(name_ptr)
    }

    pub fn num_correlation_ids(&self) -> i32 {
        unsafe { blpapi_sys::blpapi_Message_numCorrelationIds(self.ptr) }
    }

    pub fn correlation_id(&self, index: usize) -> Option<CorrelationId> {
        let n = self.num_correlation_ids();
        if n <= 0 || index >= n as usize {
            return None;
        }
        let raw = unsafe { blpapi_sys::blpapi_Message_correlationId(self.ptr, index) };
        let mut out_u64: u64 = 0;
        let is_int = unsafe { blpapi_sys::blpapiext_cid_is_int(&raw as *const _) } != 0;
        if is_int {
            let rc = unsafe {
                blpapi_sys::blpapiext_cid_get_u64(&raw as *const _, &mut out_u64 as *mut _)
            };
            if rc == 0 {
                return Some(CorrelationId::U64(out_u64));
            }
        }
        let mut out_ptr: *const core::ffi::c_void = core::ptr::null();
        let is_ptr = unsafe { blpapi_sys::blpapiext_cid_is_ptr(&raw as *const _) } != 0;
        if is_ptr {
            let rc = unsafe {
                blpapi_sys::blpapiext_cid_get_ptr(&raw as *const _, &mut out_ptr as *mut _)
            };
            if rc == 0 && !out_ptr.is_null() {
                if let Some(s) = TAG_REGISTRY.lookup(out_ptr) {
                    if let Ok(st) = s.to_str() {
                        return Some(CorrelationId::Tag(Arc::from(st)));
                    }
                }
                // Unknown pointer tag: surface diagnostic string
                let diag = format!("<unknown:{out_ptr:p}>");
                return Some(CorrelationId::Tag(Arc::from(diag.as_str())));
            }
        }
        None
    }

    /// Check if this message matches the given correlation ID.
    /// Returns `false` if the message has no correlation ID or it doesn't match.
    pub fn matches_correlation_id(&self, cid: &CorrelationId) -> bool {
        self.correlation_id(0)
            .map(|msg_cid| &msg_cid == cid)
            .unwrap_or(false)
    }
    pub fn get_request_id(&self) -> Option<&str> {
        let mut req_id: *const i8 = std::ptr::null();
        let rc = unsafe { blpapi_sys::blpapi_Message_getRequestId(self.ptr, &mut req_id) };
        if rc == 0 && !req_id.is_null() {
            Some(
                unsafe { CStr::from_ptr(req_id) }
                    .to_str()
                    .unwrap_or_default(),
            )
        } else {
            None
        }
    }

    pub fn recap_type(&self) -> i32 {
        unsafe { blpapi_sys::blpapi_Message_recapType(self.ptr) }
    }

    pub fn print_to_string(&self) -> String {
        // Fallback: use type string if print is unavailable
        let mut out = String::new();
        unsafe extern "C" fn write_cb(
            data: *const i8,
            len: i32,
            ctx: *mut core::ffi::c_void,
        ) -> i32 {
            if ctx.is_null() || data.is_null() || len <= 0 {
                return 0;
            }
            let s = std::slice::from_raw_parts(data as *const u8, len as usize);
            let buf = &mut *(ctx as *mut String);
            buf.extend(s.iter().map(|&b| b as char));
            0
        }
        unsafe {
            let _rc = blpapi_sys::blpapi_Message_print(
                self.ptr,
                Some(write_cb),
                &mut out as *mut _ as *mut core::ffi::c_void,
                0,
                -1,
            );
        }
        if out.is_empty() {
            format!("{}", self.message_type())
        } else {
            out
        }
    }

    /// Serialize the message payload to JSON using the Bloomberg SDK's native toJson.
    ///
    /// This is significantly faster than iterating over elements individually
    /// because it makes a single FFI call and the SDK serializes internally.
    ///
    /// Returns `None` if the toJson function is not available (SDK < 3.25.11).
    pub fn to_json(&self) -> Option<String> {
        self.elements().to_json()
    }
}

#[allow(dead_code)]
impl MessageOwned {
    pub(crate) fn clone_from(ptr: *mut blpapi_sys::blpapi_Message_t) -> Option<Self> {
        if ptr.is_null() {
            None
        } else {
            unsafe {
                blpapi_sys::blpapi_Message_addRef(ptr);
            }
            Some(Self { ptr })
        }
    }

    pub fn message_type(&self) -> Name {
        let name_ptr = unsafe { blpapi_sys::blpapi_Message_messageType(self.ptr) };
        Name::from_raw(name_ptr)
    }

    pub fn num_correlation_ids(&self) -> i32 {
        unsafe { blpapi_sys::blpapi_Message_numCorrelationIds(self.ptr) }
    }

    pub fn get_request_id(&self) -> Option<&str> {
        let mut req_id: *const i8 = std::ptr::null();
        let rc = unsafe { blpapi_sys::blpapi_Message_getRequestId(self.ptr, &mut req_id) };
        if rc == 0 && !req_id.is_null() {
            Some(
                unsafe { CStr::from_ptr(req_id) }
                    .to_str()
                    .unwrap_or_default(),
            )
        } else {
            None
        }
    }
}

impl Drop for MessageOwned {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_Message_release(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

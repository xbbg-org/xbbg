use std::ffi::CString;

use crate::errors::{BlpError, Result};
use crate::request::Request;
use crate::schema::{SchemaElementDefinition, Operation};
use crate::name::Name;

pub struct Service {
    ptr: *mut blpapi_sys::blpapi_Service_t,
}

unsafe impl Send for Service {}
unsafe impl Sync for Service {}

impl Service {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Service_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null service pointer".into(),
            });
        }
        // addRef so drop can release
        let rc = unsafe { blpapi_sys::blpapi_Service_addRef(ptr) };
        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Service_addRef rc={rc}"),
            });
        }
        Ok(Self { ptr })
    }

    pub fn name(&self) -> &str {
        let cptr = unsafe { blpapi_sys::blpapi_Service_name(self.ptr) };
        if cptr.is_null() {
            ""
        } else {
            unsafe { std::ffi::CStr::from_ptr(cptr) }
                .to_str()
                .unwrap_or_default()
        }
    }

    pub fn description(&self) -> &str {
        let cptr = unsafe { blpapi_sys::blpapi_Service_description(self.ptr) };
        if cptr.is_null() {
            ""
        } else {
            unsafe { std::ffi::CStr::from_ptr(cptr) }
                .to_str()
                .unwrap_or_default()
        }
    }

    pub fn num_operations(&self) -> usize {
        unsafe { blpapi_sys::blpapi_Service_numOperations(self.ptr) as usize }
    }

    pub fn operation_names(&self) -> Vec<Name> {
        let n = self.num_operations();
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            let mut op_ptr: *mut blpapi_sys::blpapi_Operation_t = std::ptr::null_mut();
            let rc = unsafe { blpapi_sys::blpapi_Service_getOperationAt(self.ptr, &mut op_ptr, i) };
            if rc == 0 && !op_ptr.is_null() {
                let c = unsafe { blpapi_sys::blpapi_Operation_name(op_ptr) };
                if !c.is_null() {
                    if let Ok(s) = unsafe { std::ffi::CStr::from_ptr(c) }.to_str() {
                        if let Ok(nm) = Name::new(s) {
                            out.push(nm);
                        }
                    }
                }
            }
        }
        out
    }

    pub fn get_operation(&self, name: &Name) -> Result<Operation> {
        let mut op_ptr: *mut blpapi_sys::blpapi_Operation_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Service_getOperation(self.ptr, &mut op_ptr, std::ptr::null(), name.as_raw())
        };
        if rc != 0 || op_ptr.is_null() {
            return Err(BlpError::Internal { detail: format!("operation not found: {}", name.as_str()) });
        }
        Ok(Operation { ptr: op_ptr })
    }

    pub fn num_event_definitions(&self) -> usize {
        unsafe { blpapi_sys::blpapi_Service_numEventDefinitions(self.ptr) as usize }
    }

    pub fn get_event_definition(&self, index: usize) -> Result<SchemaElementDefinition> {
        let mut def_ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Service_getEventDefinitionAt(self.ptr, &mut def_ptr, index)
        };
        if rc != 0 || def_ptr.is_null() {
            return Err(BlpError::Internal { detail: format!("getEventDefinitionAt rc={rc}") });
        }
        SchemaElementDefinition::from_raw(def_ptr)
    }

    pub fn get_event_definition_by_name(&self, name: &Name) -> Result<SchemaElementDefinition> {
        let mut def_ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Service_getEventDefinition(self.ptr, &mut def_ptr, std::ptr::null(), name.as_raw())
        };
        if rc != 0 || def_ptr.is_null() {
            return Err(BlpError::Internal { detail: format!("getEventDefinition rc={rc}") });
        }
        SchemaElementDefinition::from_raw(def_ptr)
    }

    pub fn create_request(&self, operation: &str) -> Result<Request> {
        let mut req_ptr: *mut blpapi_sys::blpapi_Request_t = std::ptr::null_mut();
        let cop = CString::new(operation).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid operation: {e}"),
        })?;
        let rc = unsafe {
            blpapi_sys::blpapi_Service_createRequest(self.ptr, &mut req_ptr, cop.as_ptr())
        };
        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("createRequest failed rc={rc} op='{operation}'"),
            });
        }
        Request::from_raw(req_ptr)
    }

    #[cfg(feature = "schema-debug")]
    pub fn print_schema(&self) -> String {
        let mut out = String::new();
        unsafe extern "C" fn write_cb(data: *const i8, len: i32, ctx: *mut core::ffi::c_void) -> i32 {
            if ctx.is_null() || data.is_null() || len <= 0 {
                return 0;
            }
            let s = unsafe { std::slice::from_raw_parts(data as *const u8, len as usize) };
            let buf = unsafe { &mut *(ctx as *mut String) };
            let _ = buf.extend(s.iter().map(|&b| b as char));
            0
        }
        unsafe {
            let _ = blpapi_sys::blpapi_Service_print(
                self.ptr,
                Some(write_cb),
                &mut out as *mut _ as *mut core::ffi::c_void,
                0,
                -1,
            );
        }
        out
    }
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_Service_t {
        self.ptr
    }
}

impl Drop for Service {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_Service_release(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}



use crate::errors::{BlpError, Result};
use std::ffi::CString;
use crate::service::Service;

pub struct Request {
    ptr: *mut blpapi_sys::blpapi_Request_t,
}

unsafe impl Send for Request {}
unsafe impl Sync for Request {}

impl Request {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Request_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "null request pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    #[allow(dead_code)]
    pub fn as_raw(&self) -> *mut blpapi_sys::blpapi_Request_t {
        self.ptr
    }
}

impl Drop for Request {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_Request_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

#[allow(dead_code)]
pub struct RequestBuilder {
    securities: Vec<String>,
    fields: Vec<String>,
    overrides: Vec<(String, String)>,
    label: Option<String>,
}

#[allow(dead_code)]
impl RequestBuilder {
    pub fn new() -> Self {
        Self {
            securities: Vec::new(),
            fields: Vec::new(),
            overrides: Vec::new(),
            label: None,
        }
    }

    pub fn securities(mut self, secs: Vec<String>) -> Self {
        self.securities = secs;
        self
    }

    pub fn fields(mut self, flds: Vec<String>) -> Self {
        self.fields = flds;
        self
    }

    pub fn r#override(mut self, name: &str, value: impl ToString) -> Self {
        self.overrides.push((name.to_string(), value.to_string()));
        self
    }

    pub fn label(mut self, label: &str) -> Self {
        self.label = Some(label.to_string());
        self
    }

    pub fn build(self, service: &Service, operation: &str) -> Result<Request> {
        if self.securities.is_empty() || self.fields.is_empty() {
            return Err(BlpError::InvalidArgument {
                detail: "securities and fields must be non-empty".into(),
            });
        }
        let request = service.create_request(operation)?;
        unsafe {
            let root_el = blpapi_sys::blpapi_Request_elements(request.as_raw());
            // securities
            let mut el_secs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
            let k_secs = CString::new("securities").unwrap();
            let rc = blpapi_sys::blpapi_Element_getElement(root_el, &mut el_secs, k_secs.as_ptr(), std::ptr::null());
            if rc != 0 || el_secs.is_null() {
                return Err(BlpError::Internal { detail: format!("getElement('securities') rc={rc}") });
            }
            for s in &self.securities {
                let cs = CString::new(s.as_str()).unwrap();
                let rc = blpapi_sys::blpapi_Element_setValueString(el_secs, cs.as_ptr(), blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize);
                if rc != 0 {
                    return Err(BlpError::InvalidArgument { detail: format!("append security failed rc={rc}") });
                }
            }
            // fields
            let mut el_fields: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
            let k_fields = CString::new("fields").unwrap();
            let rc = blpapi_sys::blpapi_Element_getElement(root_el, &mut el_fields, k_fields.as_ptr(), std::ptr::null());
            if rc != 0 || el_fields.is_null() {
                return Err(BlpError::Internal { detail: format!("getElement('fields') rc={rc}") });
            }
            for f in &self.fields {
                let cf = CString::new(f.as_str()).unwrap();
                let rc = blpapi_sys::blpapi_Element_setValueString(el_fields, cf.as_ptr(), blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize);
                if rc != 0 {
                    return Err(BlpError::InvalidArgument { detail: format!("append field failed rc={rc}") });
                }
            }
            // overrides if present
            if !self.overrides.is_empty() {
                let mut el_ovs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
                let k_ovs = CString::new("overrides").unwrap();
                let rc = blpapi_sys::blpapi_Element_getElement(root_el, &mut el_ovs, k_ovs.as_ptr(), std::ptr::null());
                if rc != 0 || el_ovs.is_null() {
                    return Err(BlpError::InvalidArgument { detail: format!("operation does not support overrides") });
                }
                for (name, value) in &self.overrides {
                    // each override is a sequence with elements 'fieldId' and 'value'
                    let mut ov_seq: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
                    let rc = blpapi_sys::blpapi_Element_appendElement(el_ovs, &mut ov_seq);
                    if rc != 0 || ov_seq.is_null() {
                        return Err(BlpError::Internal { detail: format!("append override element rc={rc}") });
                    }
                    let k_field_id = CString::new("fieldId").unwrap();
                    let k_value = CString::new("value").unwrap();
                    let c_name = CString::new(name.as_str()).unwrap();
                    let c_val = CString::new(value.as_str()).unwrap();
                    let rc1 = blpapi_sys::blpapi_Element_setElementString(ov_seq, k_field_id.as_ptr(), std::ptr::null(), c_name.as_ptr());
                    let rc2 = blpapi_sys::blpapi_Element_setElementString(ov_seq, k_value.as_ptr(), std::ptr::null(), c_val.as_ptr());
                    if rc1 != 0 || rc2 != 0 {
                        return Err(BlpError::InvalidArgument { detail: format!("set override values failed rc1={rc1} rc2={rc2}") });
                    }
                }
            }
        }
        Ok(request)
    }
}



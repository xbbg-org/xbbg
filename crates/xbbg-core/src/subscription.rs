use std::ffi::CString;

use crate::correlation::CorrelationId;
use crate::errors::{BlpError, Result};

pub struct SubscriptionList {
    ptr: *mut blpapi_sys::blpapi_SubscriptionList_t,
}

unsafe impl Send for SubscriptionList {}
unsafe impl Sync for SubscriptionList {}

impl SubscriptionList {
    pub fn new() -> Result<Self> {
        let ptr = unsafe { blpapi_sys::blpapi_SubscriptionList_create() };
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "blpapi_SubscriptionList_create returned null".into(),
            });
        }
        Ok(Self { ptr })
    }

    pub fn add(&mut self, topic: &str, fields: &[&str], cid: Option<&CorrelationId>) -> Result<()> {
        let ctopic = CString::new(topic).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid topic: {e}"),
        })?;
        let fields_c: Vec<CString> = fields
            .iter()
            .map(|s| CString::new(*s).map_err(|e| BlpError::InvalidArgument {
                detail: format!("invalid field: {e}"),
            }))
            .collect::<Result<Vec<_>>>()?;
        let mut fields_ptrs: Vec<*const i8> = fields_c.iter().map(|c| c.as_ptr()).collect();
        let mut cid_raw = match cid {
            Some(c) => c.to_ffi(),
            None => CorrelationId::to_ffi_autogen(),
        };
        let fields_ptr_raw: *mut *const i8 = if fields_ptrs.is_empty() {
            std::ptr::null_mut()
        } else {
            fields_ptrs.as_mut_ptr()
        };
        let options_ptr_raw: *mut *const i8 = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_SubscriptionList_add(
                self.ptr,
                ctopic.as_ptr(),
                &mut cid_raw as *mut _,
                fields_ptr_raw,
                options_ptr_raw,
                fields_ptrs.len(),
                0,
            )
        };
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("add subscription failed rc={rc}"),
            });
        }
        Ok(())
    }

    pub(crate) fn as_raw(&self) -> *const blpapi_sys::blpapi_SubscriptionList_t {
        self.ptr
    }
}

impl Drop for SubscriptionList {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_SubscriptionList_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

pub struct SubscriptionListBuilder {
    subs: Vec<(String, Vec<String>, CorrelationId)>,
}

impl SubscriptionListBuilder {
    pub fn new() -> Self {
        Self { subs: Vec::new() }
    }

    pub fn add(mut self, topic: &str, fields: &[&str], cid: CorrelationId) -> Self {
        self.subs.push((
            topic.to_string(),
            fields.iter().map(|s| s.to_string()).collect(),
            cid,
        ));
        self
    }

    pub fn build(self) -> Result<SubscriptionList> {
        let mut list = SubscriptionList::new()?;
        for (topic, fields, cid) in self.subs {
            let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();
            list.add(&topic, &field_refs, Some(&cid))?;
        }
        Ok(list)
    }
}


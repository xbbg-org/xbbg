use std::ffi::CString;

use crate::errors::{BlpError, Result};
use crate::event::Event;
use crate::options::SessionOptions;
use crate::service::Service;
use crate::request_template::RequestTemplate;
use crate::identity::Identity;
use crate::subscription::SubscriptionList;
use crate::correlation::CorrelationId;
use crate::request::Request;

pub struct Session {
    ptr: *mut blpapi_sys::blpapi_Session_t,
}

unsafe impl Send for Session {}
unsafe impl Sync for Session {}

impl Session {
    pub fn new(options: &SessionOptions) -> Result<Self> {
        let ptr = unsafe {
            blpapi_sys::blpapi_Session_create(
                options.as_raw(),
                None, // handler: sync mode
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            )
        };
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "blpapi_Session_create returned null".into(),
            });
        }
        Ok(Self { ptr })
    }

    pub fn create_identity(&self) -> Result<Identity> {
        let ptr = unsafe { blpapi_sys::blpapi_Session_createIdentity(self.ptr) };
        Identity::from_raw(ptr)
    }

    pub fn start(&self) -> Result<()> {
        let rc = unsafe { blpapi_sys::blpapi_Session_start(self.ptr) };
        if rc != 0 {
            return Err(BlpError::SessionStart {
                source: None,
                label: None,
            });
        }
        Ok(())
    }

    pub fn start_async(&self) -> Result<()> {
        let rc = unsafe { blpapi_sys::blpapi_Session_startAsync(self.ptr) };
        if rc != 0 {
            return Err(BlpError::SessionStart {
                source: None,
                label: None,
            });
        }
        Ok(())
    }

    pub fn stop(&self) {
        unsafe { blpapi_sys::blpapi_Session_stop(self.ptr) };
    }

    pub fn stop_async(&self) {
        unsafe { blpapi_sys::blpapi_Session_stopAsync(self.ptr) };
    }

    pub fn next_event(&self, timeout_ms: Option<u32>) -> Result<Event> {
        let mut ev_ptr: *mut blpapi_sys::blpapi_Event_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Session_nextEvent(
                self.ptr,
                &mut ev_ptr,
                timeout_ms.unwrap_or(0),
            )
        };
        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("nextEvent rc={rc}"),
            });
        }
        Event::from_raw(ev_ptr)
    }

    pub fn try_next_event(&self) -> Option<Event> {
        let mut ev_ptr: *mut blpapi_sys::blpapi_Event_t = std::ptr::null_mut();
        let rc = unsafe { blpapi_sys::blpapi_Session_tryNextEvent(self.ptr, &mut ev_ptr) };
        if rc == 0 && !ev_ptr.is_null() {
            Event::from_raw(ev_ptr).ok()
        } else {
            None
        }
    }

    pub fn open_service(&self, name: &str) -> Result<()> {
        let cname = CString::new(name).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid service name: {e}"),
        })?;
        let rc = unsafe { blpapi_sys::blpapi_Session_openService(self.ptr, cname.as_ptr()) };
        if rc != 0 {
            return Err(BlpError::OpenService {
                service: name.to_string(),
                source: None,
                label: None,
            });
        }
        Ok(())
    }

    pub fn get_service(&self, name: &str) -> Result<Service> {
        let cname = CString::new(name).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid service name: {e}"),
        })?;
        let mut svc_ptr: *mut blpapi_sys::blpapi_Service_t = std::ptr::null_mut();
        let rc =
            unsafe { blpapi_sys::blpapi_Session_getService(self.ptr, &mut svc_ptr, cname.as_ptr()) };
        if rc != 0 {
            return Err(BlpError::OpenService {
                service: name.to_string(),
                source: None,
                label: None,
            });
        }
        Service::from_raw(svc_ptr)
    }

    pub fn subscribe(&self, subs: &SubscriptionList, label: Option<&str>) -> Result<()> {
        let (label_ptr, label_len, owned) = if let Some(s) = label {
            let cs = CString::new(s).map_err(|e| BlpError::InvalidArgument {
                detail: format!("invalid label: {e}"),
            })?;
            let len = s.len() as i32;
            (cs.as_ptr(), len, Some(cs))
        } else {
            (std::ptr::null(), 0, None)
        };
        let rc = unsafe {
            blpapi_sys::blpapi_Session_subscribe(
                self.ptr,
                subs.as_raw(),
                std::ptr::null(),
                label_ptr,
                label_len,
            )
        };
        drop(owned);
        if rc != 0 {
            return Err(BlpError::Internal { detail: format!("subscribe rc={rc}") });
        }
        Ok(())
    }

    pub fn unsubscribe(&self, subs: &SubscriptionList) -> Result<()> {
        let rc = unsafe {
            blpapi_sys::blpapi_Session_unsubscribe(
                self.ptr,
                subs.as_raw(),
                std::ptr::null(),
                0,
            )
        };
        if rc != 0 {
            return Err(BlpError::Internal { detail: format!("unsubscribe rc={rc}") });
        }
        Ok(())
    }

    pub fn set_status_correlation_id(&self, service: &Service, cid: &CorrelationId) -> Result<()> {
        let raw = cid.to_ffi();
        let rc = unsafe {
            blpapi_sys::blpapi_Session_setStatusCorrelationId(
                self.ptr,
                service.as_raw(),
                std::ptr::null_mut(),
                &raw as *const _,
            )
        };
        if rc != 0 {
            return Err(BlpError::Internal { detail: format!("setStatusCorrelationId rc={rc}") });
        }
        Ok(())
    }

    pub fn send_request(
        &self,
        request: &Request,
        identity: Option<&Identity>,
        cid: Option<&CorrelationId>,
    ) -> Result<()> {
        // Pass a valid CorrelationId pointer. If none provided, pass UNSET (all zeros),
        // matching the C++ default-constructed CorrelationId semantics.
        let mut raw = cid
            .map(|c| c.to_ffi())
            .unwrap_or_else(|| CorrelationId::to_ffi_autogen());
        let id_ptr = identity.map(|i| i.as_raw()).unwrap_or(std::ptr::null_mut());
        let rc = unsafe {
            blpapi_sys::blpapi_Session_sendRequest(
                self.ptr,
                request.as_raw(),
                &mut raw as *mut _,
                id_ptr,
                std::ptr::null_mut(),
                std::ptr::null(),
                0,
            )
        };
        if rc != 0 {
            return Err(BlpError::Internal { detail: format!("sendRequest rc={rc}") });
        }
        Ok(())
    }
    pub fn create_snapshot_request_template(
        &self,
        subscription_string: &str,
    ) -> Result<RequestTemplate> {
        self.create_snapshot_request_template_with_cid(subscription_string, None)
    }

    pub fn create_snapshot_request_template_with_cid(
        &self,
        subscription_string: &str,
        cid: Option<&CorrelationId>,
    ) -> Result<RequestTemplate> {
        let cstr = CString::new(subscription_string).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid subscription string: {e}"),
        })?;
        let mut tmpl_ptr: *mut blpapi_sys::blpapi_RequestTemplate_t = std::ptr::null_mut();
        // Using session identity (null); correlation id from caller or autogen.
        let mut raw_cid: blpapi_sys::blpapi_CorrelationId_t = if let Some(c) = cid {
            c.to_ffi()
        } else {
            CorrelationId::to_ffi_autogen()
        };
        let rc = unsafe {
            blpapi_sys::blpapi_Session_createSnapshotRequestTemplate(
                &mut tmpl_ptr,
                self.ptr,
                cstr.as_ptr(),
                std::ptr::null_mut(),
                &mut raw_cid,
            )
        };
        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("createSnapshotRequestTemplate rc={rc}"),
            });
        }
        RequestTemplate::from_raw(tmpl_ptr)
    }

    pub fn send_request_template(&self, tmpl: &RequestTemplate) -> Result<()> {
        self.send_request_template_with_cid(tmpl, None)
    }

    pub fn send_request_template_with_cid(
        &self,
        tmpl: &RequestTemplate,
        cid: Option<&CorrelationId>,
    ) -> Result<()> {
        let mut raw = cid
            .map(|c| c.to_ffi())
            .unwrap_or_else(|| CorrelationId::to_ffi_autogen());
        let rc = unsafe {
            blpapi_sys::blpapi_Session_sendRequestTemplate(self.ptr, tmpl.as_raw(), &mut raw)
        };
        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("sendRequestTemplate rc={rc}"),
            });
        }
        Ok(())
    }

    pub fn cancel(&self, cids: &[CorrelationId], label: Option<&str>) -> Result<()> {
        let raws: Vec<blpapi_sys::blpapi_CorrelationId_t> =
            cids.iter().map(|c| c.to_ffi()).collect();
        let (label_ptr, label_len, owned) = if let Some(s) = label {
            let cs = CString::new(s).map_err(|e| BlpError::InvalidArgument {
                detail: format!("invalid label: {e}"),
            })?;
            (cs.as_ptr(), s.len() as i32, Some(cs))
        } else {
            (std::ptr::null(), 0, None)
        };
        let rc = unsafe {
            blpapi_sys::blpapi_Session_cancel(
                self.ptr,
                raws.as_ptr(),
                raws.len(),
                label_ptr,
                label_len,
            )
        };
        drop(owned);
        if rc != 0 {
            return Err(BlpError::Internal { detail: format!("cancel rc={rc}") });
        }
        Ok(())
    }

    #[allow(dead_code)]
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_Session_t {
        self.ptr
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_Session_destroy(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}



use crate::errors::{BlpError, Result};
use crate::service::Service;
use std::ffi::CString;

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
    /// Generic request elements (for BQL expression, bsrch domain, etc.)
    elements: Vec<(String, String)>,
    label: Option<String>,
    /// Single security (for intraday requests)
    single_security: Option<String>,
    /// Event type (TRADE, BID, ASK, etc.) for IntradayBarRequest
    event_type: Option<String>,
    /// Interval in minutes for IntradayBarRequest
    interval: Option<u32>,
    /// Start datetime (for intraday requests)
    start_datetime: Option<String>,
    /// End datetime (for intraday requests)
    end_datetime: Option<String>,
    /// Start date (for HistoricalDataRequest)
    start_date: Option<String>,
    /// End date (for HistoricalDataRequest)
    end_date: Option<String>,
    /// Search spec for FieldSearchRequest (//blp/apiflds)
    search_spec: Option<String>,
    /// Field IDs for FieldInfoRequest (//blp/apiflds)
    field_ids: Vec<String>,
}

impl Default for RequestBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[allow(dead_code)]
impl RequestBuilder {
    pub fn new() -> Self {
        Self {
            securities: Vec::new(),
            fields: Vec::new(),
            overrides: Vec::new(),
            elements: Vec::new(),
            label: None,
            single_security: None,
            event_type: None,
            interval: None,
            start_datetime: None,
            end_datetime: None,
            start_date: None,
            end_date: None,
            search_spec: None,
            field_ids: Vec::new(),
        }
    }

    pub fn securities(mut self, secs: Vec<String>) -> Self {
        self.securities = secs;
        self
    }

    /// Set a single security (for intraday requests)
    pub fn security(mut self, sec: &str) -> Self {
        self.single_security = Some(sec.to_string());
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

    /// Set a generic request element (for BQL expression, bsrch domain, etc.)
    pub fn element(mut self, name: &str, value: impl ToString) -> Self {
        self.elements.push((name.to_string(), value.to_string()));
        self
    }

    pub fn label(mut self, label: &str) -> Self {
        self.label = Some(label.to_string());
        self
    }

    /// Set the event type (TRADE, BID, ASK, etc.) for IntradayBarRequest
    pub fn event_type(mut self, event_type: &str) -> Self {
        self.event_type = Some(event_type.to_string());
        self
    }

    /// Set the interval in minutes for IntradayBarRequest
    pub fn interval(mut self, interval: u32) -> Self {
        self.interval = Some(interval);
        self
    }

    /// Set the start datetime (for intraday requests)
    pub fn start_datetime(mut self, dt: &str) -> Self {
        self.start_datetime = Some(dt.to_string());
        self
    }

    /// Set the end datetime (for intraday requests)
    pub fn end_datetime(mut self, dt: &str) -> Self {
        self.end_datetime = Some(dt.to_string());
        self
    }

    /// Set the start date (for HistoricalDataRequest)
    pub fn start_date(mut self, date: &str) -> Self {
        self.start_date = Some(date.to_string());
        self
    }

    /// Set the end date (for HistoricalDataRequest)
    pub fn end_date(mut self, date: &str) -> Self {
        self.end_date = Some(date.to_string());
        self
    }

    /// Set the search spec for FieldSearchRequest (//blp/apiflds)
    pub fn search_spec(mut self, spec: &str) -> Self {
        self.search_spec = Some(spec.to_string());
        self
    }

    /// Set the field IDs for FieldInfoRequest (//blp/apiflds)
    pub fn field_ids(mut self, ids: Vec<String>) -> Self {
        self.field_ids = ids;
        self
    }

    pub fn build(self, service: &Service, operation: &str) -> Result<Request> {
        let request = service.create_request(operation)?;

        unsafe {
            let root_el = blpapi_sys::blpapi_Request_elements(request.as_raw());

            match operation {
                "IntradayBarRequest" => {
                    self.build_intraday_bar(root_el)?;
                }
                "IntradayTickRequest" => {
                    self.build_intraday_tick(root_el)?;
                }
                "HistoricalDataRequest" => {
                    self.build_historical_data(root_el)?;
                }
                "FieldInfoRequest" => {
                    self.build_field_info(root_el)?;
                }
                "FieldSearchRequest" => {
                    self.build_field_search(root_el)?;
                }
                _ => {
                    // For unknown operations, if we have elements, use generic build
                    // Otherwise fall back to reference data style
                    if !self.elements.is_empty() {
                        self.build_generic(root_el)?;
                    } else {
                        self.build_reference_data(root_el)?;
                    }
                }
            }
        }
        Ok(request)
    }

    /// Build a generic request by setting arbitrary elements.
    /// Used for services like BQL (//blp/bqlsvc) and bsrch (//blp/exrsvc).
    unsafe fn build_generic(&self, root_el: *mut blpapi_sys::blpapi_Element_t) -> Result<()> {
        // Set each element as a string on the request
        for (name, value) in &self.elements {
            let c_name = CString::new(name.as_str()).unwrap();
            let c_value = CString::new(value.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                c_name.as_ptr(),
                std::ptr::null(),
                c_value.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("failed to set element '{}': rc={}", name, rc),
                });
            }
        }
        Ok(())
    }

    unsafe fn build_reference_data(
        &self,
        root_el: *mut blpapi_sys::blpapi_Element_t,
    ) -> Result<()> {
        if self.securities.is_empty() || self.fields.is_empty() {
            return Err(BlpError::InvalidArgument {
                detail: "securities and fields must be non-empty".into(),
            });
        }

        // securities
        let mut el_secs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_secs = CString::new("securities").unwrap();
        let rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_secs,
            k_secs.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_secs.is_null() {
            return Err(BlpError::Internal {
                detail: format!("getElement('securities') rc={rc}"),
            });
        }
        for s in &self.securities {
            let cs = CString::new(s.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setValueString(
                el_secs,
                cs.as_ptr(),
                blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("append security failed rc={rc}"),
                });
            }
        }

        // fields
        let mut el_fields: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_fields = CString::new("fields").unwrap();
        let rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_fields,
            k_fields.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_fields.is_null() {
            return Err(BlpError::Internal {
                detail: format!("getElement('fields') rc={rc}"),
            });
        }
        for f in &self.fields {
            let cf = CString::new(f.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setValueString(
                el_fields,
                cf.as_ptr(),
                blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("append field failed rc={rc}"),
                });
            }
        }

        // overrides if present
        if !self.overrides.is_empty() {
            let mut el_ovs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
            let k_ovs = CString::new("overrides").unwrap();
            let rc = blpapi_sys::blpapi_Element_getElement(
                root_el,
                &mut el_ovs,
                k_ovs.as_ptr(),
                std::ptr::null(),
            );
            if rc != 0 || el_ovs.is_null() {
                return Err(BlpError::InvalidArgument {
                    detail: "operation does not support overrides".into(),
                });
            }
            for (name, value) in &self.overrides {
                let mut ov_seq: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
                let rc = blpapi_sys::blpapi_Element_appendElement(el_ovs, &mut ov_seq);
                if rc != 0 || ov_seq.is_null() {
                    return Err(BlpError::Internal {
                        detail: format!("append override element rc={rc}"),
                    });
                }
                let k_field_id = CString::new("fieldId").unwrap();
                let k_value = CString::new("value").unwrap();
                let c_name = CString::new(name.as_str()).unwrap();
                let c_val = CString::new(value.as_str()).unwrap();
                let rc1 = blpapi_sys::blpapi_Element_setElementString(
                    ov_seq,
                    k_field_id.as_ptr(),
                    std::ptr::null(),
                    c_name.as_ptr(),
                );
                let rc2 = blpapi_sys::blpapi_Element_setElementString(
                    ov_seq,
                    k_value.as_ptr(),
                    std::ptr::null(),
                    c_val.as_ptr(),
                );
                if rc1 != 0 || rc2 != 0 {
                    return Err(BlpError::InvalidArgument {
                        detail: format!("set override values failed rc1={rc1} rc2={rc2}"),
                    });
                }
            }
        }

        Ok(())
    }

    unsafe fn build_historical_data(
        &self,
        root_el: *mut blpapi_sys::blpapi_Element_t,
    ) -> Result<()> {
        if self.securities.is_empty() || self.fields.is_empty() {
            return Err(BlpError::InvalidArgument {
                detail: "securities and fields must be non-empty".into(),
            });
        }

        // securities
        let mut el_secs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_secs = CString::new("securities").unwrap();
        let rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_secs,
            k_secs.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_secs.is_null() {
            return Err(BlpError::Internal {
                detail: format!("getElement('securities') rc={rc}"),
            });
        }
        for s in &self.securities {
            let cs = CString::new(s.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setValueString(
                el_secs,
                cs.as_ptr(),
                blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("append security failed rc={rc}"),
                });
            }
        }

        // fields
        let mut el_fields: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_fields = CString::new("fields").unwrap();
        let rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_fields,
            k_fields.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_fields.is_null() {
            return Err(BlpError::Internal {
                detail: format!("getElement('fields') rc={rc}"),
            });
        }
        for f in &self.fields {
            let cf = CString::new(f.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setValueString(
                el_fields,
                cf.as_ptr(),
                blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("append field failed rc={rc}"),
                });
            }
        }

        // startDate
        if let Some(ref start_date) = self.start_date {
            let k = CString::new("startDate").unwrap();
            let v = CString::new(start_date.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set startDate failed rc={rc}"),
                });
            }
        }

        // endDate
        if let Some(ref end_date) = self.end_date {
            let k = CString::new("endDate").unwrap();
            let v = CString::new(end_date.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set endDate failed rc={rc}"),
                });
            }
        }

        Ok(())
    }

    unsafe fn build_intraday_bar(&self, root_el: *mut blpapi_sys::blpapi_Element_t) -> Result<()> {
        let security = self
            .single_security
            .as_ref()
            .ok_or_else(|| BlpError::InvalidArgument {
                detail: "IntradayBarRequest requires a single security".into(),
            })?;

        // security (single value, not array)
        let k = CString::new("security").unwrap();
        let v = CString::new(security.as_str()).unwrap();
        let rc = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k.as_ptr(),
            std::ptr::null(),
            v.as_ptr(),
        );
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("set security failed rc={rc}"),
            });
        }

        // eventType
        if let Some(ref event_type) = self.event_type {
            let k = CString::new("eventType").unwrap();
            let v = CString::new(event_type.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set eventType failed rc={rc}"),
                });
            }
        }

        // interval
        if let Some(interval) = self.interval {
            let k = CString::new("interval").unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementInt32(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                interval as i32,
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set interval failed rc={rc}"),
                });
            }
        }

        // startDateTime
        if let Some(ref start_dt) = self.start_datetime {
            let k = CString::new("startDateTime").unwrap();
            let v = CString::new(start_dt.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set startDateTime failed rc={rc}"),
                });
            }
        }

        // endDateTime
        if let Some(ref end_dt) = self.end_datetime {
            let k = CString::new("endDateTime").unwrap();
            let v = CString::new(end_dt.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set endDateTime failed rc={rc}"),
                });
            }
        }

        Ok(())
    }

    unsafe fn build_intraday_tick(&self, root_el: *mut blpapi_sys::blpapi_Element_t) -> Result<()> {
        let security = self
            .single_security
            .as_ref()
            .ok_or_else(|| BlpError::InvalidArgument {
                detail: "IntradayTickRequest requires a single security".into(),
            })?;

        // security (single value, not array)
        let k = CString::new("security").unwrap();
        let v = CString::new(security.as_str()).unwrap();
        let rc = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k.as_ptr(),
            std::ptr::null(),
            v.as_ptr(),
        );
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("set security failed rc={rc}"),
            });
        }

        // startDateTime
        if let Some(ref start_dt) = self.start_datetime {
            let k = CString::new("startDateTime").unwrap();
            let v = CString::new(start_dt.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set startDateTime failed rc={rc}"),
                });
            }
        }

        // endDateTime
        if let Some(ref end_dt) = self.end_datetime {
            let k = CString::new("endDateTime").unwrap();
            let v = CString::new(end_dt.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementString(
                root_el,
                k.as_ptr(),
                std::ptr::null(),
                v.as_ptr(),
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("set endDateTime failed rc={rc}"),
                });
            }
        }

        // eventTypes (array) - required for IntradayTickRequest
        // Get the eventTypes element
        let mut el_event_types: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_event_types = CString::new("eventTypes").unwrap();
        let rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_event_types,
            k_event_types.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_event_types.is_null() {
            return Err(BlpError::Internal {
                detail: format!("getElement('eventTypes') rc={rc}"),
            });
        }
        // Use provided event_type or default to TRADE
        let event_type = self.event_type.as_deref().unwrap_or("TRADE");
        let v = CString::new(event_type).unwrap();
        let rc = blpapi_sys::blpapi_Element_setValueString(
            el_event_types,
            v.as_ptr(),
            blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
        );
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("append eventType failed rc={rc}"),
            });
        }

        Ok(())
    }

    /// Build FieldInfoRequest for //blp/apiflds service.
    /// Uses "id" array for field IDs (per SDK example).
    unsafe fn build_field_info(&self, root_el: *mut blpapi_sys::blpapi_Element_t) -> Result<()> {
        if self.field_ids.is_empty() {
            return Err(BlpError::InvalidArgument {
                detail: "FieldInfoRequest requires at least one field ID".into(),
            });
        }

        // Get the "id" element (array of field IDs)
        let mut el_ids: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_id = CString::new("id").unwrap();
        let rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_ids,
            k_id.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_ids.is_null() {
            return Err(BlpError::Internal {
                detail: format!("getElement('id') rc={rc}"),
            });
        }

        // Append each field ID
        for field_id in &self.field_ids {
            let c_id = CString::new(field_id.as_str()).unwrap();
            let rc = blpapi_sys::blpapi_Element_setValueString(
                el_ids,
                c_id.as_ptr(),
                blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
            );
            if rc != 0 {
                return Err(BlpError::InvalidArgument {
                    detail: format!("append field id failed rc={rc}"),
                });
            }
        }

        Ok(())
    }

    /// Build FieldSearchRequest for //blp/apiflds service.
    /// Uses "searchSpec" string (per SDK example).
    unsafe fn build_field_search(&self, root_el: *mut blpapi_sys::blpapi_Element_t) -> Result<()> {
        let search_spec = self
            .search_spec
            .as_ref()
            .ok_or_else(|| BlpError::InvalidArgument {
                detail: "FieldSearchRequest requires a search_spec".into(),
            })?;

        // Set searchSpec
        let k = CString::new("searchSpec").unwrap();
        let v = CString::new(search_spec.as_str()).unwrap();
        let rc = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k.as_ptr(),
            std::ptr::null(),
            v.as_ptr(),
        );
        if rc != 0 {
            return Err(BlpError::InvalidArgument {
                detail: format!("set searchSpec failed rc={rc}"),
            });
        }

        // Set returnFieldDocumentation = true (useful default)
        let k_doc = CString::new("returnFieldDocumentation").unwrap();
        blpapi_sys::blpapi_Element_setElementBool(
            root_el,
            k_doc.as_ptr(),
            std::ptr::null(),
            1, // true
        );

        Ok(())
    }
}

use std::ffi::{CString, CStr};
use crate::errors::Result;

pub struct ElementRef {
    ptr: *mut blpapi_sys::blpapi_Element_t,
}

#[allow(dead_code)]
pub struct ElementOwned {
    ptr: *mut blpapi_sys::blpapi_Element_t,
}

impl ElementRef {
    #[allow(dead_code)]
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Element_t) -> Option<Self> {
        if ptr.is_null() { None } else { Some(Self { ptr }) }
    }

    pub fn num_elements(&self) -> usize {
        unsafe { blpapi_sys::blpapi_Element_numElements(self.ptr) as usize }
    }

    pub fn num_values(&self) -> usize {
        unsafe { blpapi_sys::blpapi_Element_numValues(self.ptr) as usize }
    }

    pub fn has(&self, name: &str, exclude_null: bool) -> bool {
        let cname = CString::new(name).unwrap();
        let rc = unsafe {
            if exclude_null {
                blpapi_sys::blpapi_Element_hasElementEx(self.ptr, cname.as_ptr(), std::ptr::null(), 1, 0)
            } else {
                blpapi_sys::blpapi_Element_hasElement(self.ptr, cname.as_ptr(), std::ptr::null())
            }
        };
        rc != 0
    }

    pub fn get_element(&self, name: &str) -> Option<ElementRef> {
        let cname = CString::new(name).unwrap();
        let mut el_ptr: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getElement(self.ptr, &mut el_ptr, cname.as_ptr(), std::ptr::null())
        };
        if rc == 0 && !el_ptr.is_null() {
            Some(ElementRef { ptr: el_ptr })
        } else {
            None
        }
    }

    pub fn get_element_at(&self, index: usize) -> Option<ElementRef> {
        let mut el_ptr: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getElementAt(self.ptr, &mut el_ptr, index)
        };
        if rc == 0 && !el_ptr.is_null() {
            Some(ElementRef { ptr: el_ptr })
        } else {
            None
        }
    }

    /// Get an array element by index (for arrays of complex types like sequences)
    pub fn get_value_as_element(&self, index: usize) -> Option<ElementRef> {
        let mut el_ptr: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getValueAsElement(self.ptr, &mut el_ptr, index)
        };
        if rc == 0 && !el_ptr.is_null() {
            Some(ElementRef { ptr: el_ptr })
        } else {
            None
        }
    }

    pub fn get_value_as_string(&self, index: usize) -> Option<String> {
        let mut buf: *const i8 = std::ptr::null();
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getValueAsString(self.ptr, &mut buf, index)
        };
        if rc == 0 && !buf.is_null() {
            Some(unsafe { CStr::from_ptr(buf) }.to_string_lossy().into_owned())
        } else {
            None
        }
    }

    pub fn get_value_as_float64(&self, index: usize) -> Option<f64> {
        let mut buf: f64 = 0.0;
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getValueAsFloat64(self.ptr, &mut buf, index)
        };
        if rc == 0 { Some(buf) } else { None }
    }

    pub fn get_value_as_int64(&self, index: usize) -> Option<i64> {
        let mut buf: i64 = 0;
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getValueAsInt64(self.ptr, &mut buf, index)
        };
        if rc == 0 { Some(buf) } else { None }
    }

    pub fn get_value_as_datetime(&self, index: usize) -> Result<Option<chrono::DateTime<chrono::Utc>>> {
        use blpapi_sys::blpapi_Datetime_t;
        let mut dt: blpapi_Datetime_t = unsafe { std::mem::zeroed() };
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getValueAsDatetime(self.ptr, &mut dt, index)
        };
        if rc != 0 {
            return Ok(None);
        }
        // Convert BLPAPI datetime to chrono::DateTime<Utc>
        // BLPAPI datetime has year, month, day, hours, minutes, seconds, milliSeconds, offset
        let year = dt.year as i32;
        let month = dt.month as u32;
        let day = dt.day as u32;
        let hour = dt.hours as u32;
        let minute = dt.minutes as u32;
        let second = dt.seconds as u32;
        let millis = dt.milliSeconds as u32;
        
        if let Some(date) = chrono::NaiveDate::from_ymd_opt(year, month.max(1).min(12), day.max(1).min(31)) {
            if let Some(datetime) = date.and_hms_milli_opt(hour.min(23), minute.min(59), second.min(59), millis) {
                // BLPAPI offset is in minutes (signed)
                let offset_minutes = dt.offset as i32;
                let offset = chrono::FixedOffset::east_opt(offset_minutes * 60)
                    .unwrap_or(chrono::FixedOffset::east_opt(0).unwrap());
                let dt_with_tz = datetime.and_local_timezone(offset)
                    .unwrap()
                    .with_timezone(&chrono::Utc);
                Ok(Some(dt_with_tz))
            } else {
                Ok(None)
            }
        } else {
            Ok(None)
        }
    }

    pub fn is_null(&self) -> bool {
        unsafe { blpapi_sys::blpapi_Element_isNull(self.ptr) != 0 }
    }

    pub fn is_null_value(&self, index: usize) -> bool {
        unsafe { blpapi_sys::blpapi_Element_isNullValue(self.ptr, index) != 0 }
    }

    pub fn name_string(&self) -> Option<String> {
        let cstr = unsafe { blpapi_sys::blpapi_Element_nameString(self.ptr) };
        if cstr.is_null() {
            None
        } else {
            Some(unsafe { CStr::from_ptr(cstr) }.to_string_lossy().into_owned())
        }
    }

    pub fn definition(&self) -> crate::schema::SchemaElementDefinition {
        let def_ptr = unsafe { blpapi_sys::blpapi_Element_definition(self.ptr) };
        crate::schema::SchemaElementDefinition::from_raw(def_ptr).expect("element definition")
    }

    #[allow(dead_code)]
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_Element_t {
        self.ptr
    }
}


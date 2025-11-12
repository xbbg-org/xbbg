use std::ffi::CString;

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

    pub fn definition(&self) -> crate::schema::SchemaElementDefinition {
        let def_ptr = unsafe { blpapi_sys::blpapi_Element_definition(self.ptr) };
        crate::schema::SchemaElementDefinition::from_raw(def_ptr).expect("element definition")
    }
}


#[allow(dead_code)]
pub fn message_to_string(ptr: *mut blpapi_sys::blpapi_Message_t) -> String {
    let mut out = String::new();
    unsafe extern "C" fn write_cb(data: *const i8, len: i32, ctx: *mut core::ffi::c_void) -> i32 {
        if ctx.is_null() || data.is_null() || len <= 0 {
            return 0;
        }
        let s = std::slice::from_raw_parts(data as *const u8, len as usize);
        let buf = &mut *(ctx as *mut String);
        let _ = buf.extend(s.iter().map(|&b| b as char));
        0
    }
    unsafe {
        if blpapi_sys::blpapi_Message_print as *const () != std::ptr::null() {
            let _rc = blpapi_sys::blpapi_Message_print(
                ptr,
                Some(write_cb),
                &mut out as *mut _ as *mut core::ffi::c_void,
                0,
                -1,
            );
        }
    }
    out
}

#[allow(dead_code)]
pub fn request_to_string(ptr: *mut blpapi_sys::blpapi_Request_t) -> String {
    let mut out = String::new();
    unsafe extern "C" fn write_cb(data: *const i8, len: i32, ctx: *mut core::ffi::c_void) -> i32 {
        if ctx.is_null() || data.is_null() || len <= 0 {
            return 0;
        }
        let s = std::slice::from_raw_parts(data as *const u8, len as usize);
        let buf = &mut *(ctx as *mut String);
        let _ = buf.extend(s.iter().map(|&b| b as char));
        0
    }
    unsafe {
        if blpapi_sys::blpapi_Element_print as *const () != std::ptr::null() {
            let elem = blpapi_sys::blpapi_Request_elements(ptr);
            let _rc = blpapi_sys::blpapi_Element_print(
                elem,
                Some(write_cb),
                &mut out as *mut _ as *mut core::ffi::c_void,
                0,
                -1,
            );
        }
    }
    out
}

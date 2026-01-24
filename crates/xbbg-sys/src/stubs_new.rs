//! Stub implementations and wrappers for APIs missing from datamock or with different signatures.
//!
//! These stubs provide minimal implementations for APIs that datamock doesn't have,
//! and wrappers that adapt datamock's simplified signatures to match the real Bloomberg API.

use std::ffi::c_char;
use std::ptr;

// ============================================================================
// Opaque type stubs
// ============================================================================

/// Identity type stub (datamock doesn't have Identity)
#[repr(C)]
pub struct blpapi_Identity_t {
    _private: [u8; 0],
}

// ============================================================================
// Constants
// ============================================================================

/// Sentinel value for "append to end" in Element array operations
pub const BLPAPI_ELEMENT_INDEX_END: usize = usize::MAX;

// ============================================================================
// Name function stubs
// ============================================================================

/// Duplicate a Name (mock: just return same pointer, no actual duplication)
#[no_mangle]
pub extern "C" fn blpapi_Name_duplicate(name: *const crate::blpapi_Name_t) -> *mut crate::blpapi_Name_t {
    name as *mut crate::blpapi_Name_t
}

/// Find a Name by string (mock: return NULL - name not found)
#[no_mangle]
pub extern "C" fn blpapi_Name_findName(_name_string: *const c_char) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

// ============================================================================
// Element function wrappers and stubs
// ============================================================================

/// Get the Name of an Element (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Element_name(_element: *mut crate::blpapi_Element_t) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

/// Wrapper: Real API has 4 params (element, out, name_obj, name_str), datamock has 3
#[no_mangle]
pub extern "C" fn blpapi_Element_getElement(
    element: *mut crate::blpapi_Element_t,
    result: *mut *mut crate::blpapi_Element_t,
    _name_obj: *const crate::blpapi_Name_t,
    name_str: *const c_char,
) -> i32 {
    extern "C" {
        fn datamock_Element_getElement(
            element: *mut crate::blpapi_Element_t,
            result: *mut *mut crate::blpapi_Element_t,
            name: *const c_char,
        ) -> i32;
    }
    
    unsafe { datamock_Element_getElement(element, result, name_str) }
}

/// Set a named sub-element to a string value (Real API: 4 params)
#[no_mangle]
pub extern "C" fn blpapi_Element_setElementString(
    element: *mut crate::blpapi_Element_t,
    _name_obj: *const crate::blpapi_Name_t,
    name_str: *const c_char,
    value: *const c_char,
) -> i32 {
    extern "C" {
        fn datamock_Element_getElement(
            element: *mut crate::blpapi_Element_t,
            result: *mut *mut crate::blpapi_Element_t,
            name: *const c_char,
        ) -> i32;
        fn datamock_Element_setValueString(
            element: *mut crate::blpapi_Element_t,
            value: *const c_char,
            index: usize,
        ) -> i32;
    }
    
    let mut sub_element: *mut crate::blpapi_Element_t = ptr::null_mut();
    let rc = unsafe { datamock_Element_getElement(element, &mut sub_element, name_str) };
    if rc != 0 {
        return rc;
    }
    
    unsafe { datamock_Element_setValueString(sub_element, value, 0) }
}

/// Set a named sub-element to an int32 value (Real API: 4 params)
#[no_mangle]
pub extern "C" fn blpapi_Element_setElementInt32(
    element: *mut crate::blpapi_Element_t,
    _name_obj: *const crate::blpapi_Name_t,
    name_str: *const c_char,
    value: i32,
) -> i32 {
    extern "C" {
        fn datamock_Element_getElement(
            element: *mut crate::blpapi_Element_t,
            result: *mut *mut crate::blpapi_Element_t,
            name: *const c_char,
        ) -> i32;
        fn datamock_Element_setValueInt32(
            element: *mut crate::blpapi_Element_t,
            value: i32,
            index: usize,
        ) -> i32;
    }
    
    let mut sub_element: *mut crate::blpapi_Element_t = ptr::null_mut();
    let rc = unsafe { datamock_Element_getElement(element, &mut sub_element, name_str) };
    if rc != 0 {
        return rc;
    }
    
    unsafe { datamock_Element_setValueInt32(sub_element, value, 0) }
}

/// Set a named sub-element to a float64 value (Real API: 4 params)
#[no_mangle]
pub extern "C" fn blpapi_Element_setElementFloat64(
    element: *mut crate::blpapi_Element_t,
    _name_obj: *const crate::blpapi_Name_t,
    name_str: *const c_char,
    value: f64,
) -> i32 {
    extern "C" {
        fn datamock_Element_getElement(
            element: *mut crate::blpapi_Element_t,
            result: *mut *mut crate::blpapi_Element_t,
            name: *const c_char,
        ) -> i32;
        fn datamock_Element_setValueString(
            element: *mut crate::blpapi_Element_t,
            value: *const c_char,
            index: usize,
        ) -> i32;
    }
    
    let mut sub_element: *mut crate::blpapi_Element_t = ptr::null_mut();
    let rc = unsafe { datamock_Element_getElement(element, &mut sub_element, name_str) };
    if rc != 0 {
        return rc;
    }
    
    // Datamock doesn't have setValueFloat64, use setValueString with formatted value
    let value_str = format!("{}\0", value);
    unsafe { datamock_Element_setValueString(sub_element, value_str.as_ptr() as *const c_char, 0) }
}

/// Set element value at index to float64 (mock: convert to string)
#[no_mangle]
pub extern "C" fn blpapi_Element_setValueFloat64(
    element: *mut crate::blpapi_Element_t,
    value: f64,
    index: usize,
) -> i32 {
    extern "C" {
        fn datamock_Element_setValueString(
            element: *mut crate::blpapi_Element_t,
            value: *const c_char,
            index: usize,
        ) -> i32;
    }
    
    let value_str = format!("{}\0", value);
    unsafe { datamock_Element_setValueString(element, value_str.as_ptr() as *const c_char, index) }
}

/// Set element value at index to int64 (mock: use int32 or convert to string)
#[no_mangle]
pub extern "C" fn blpapi_Element_setValueInt64(
    element: *mut crate::blpapi_Element_t,
    value: i64,
    index: usize,
) -> i32 {
    extern "C" {
        fn datamock_Element_setValueInt32(
            element: *mut crate::blpapi_Element_t,
            value: i32,
            index: usize,
        ) -> i32;
        fn datamock_Element_setValueString(
            element: *mut crate::blpapi_Element_t,
            value: *const c_char,
            index: usize,
        ) -> i32;
    }
    
    // Try to fit in int32, otherwise use string
    if value >= i32::MIN as i64 && value <= i32::MAX as i64 {
        unsafe { datamock_Element_setValueInt32(element, value as i32, index) }
    } else {
        let value_str = format!("{}\0", value);
        unsafe { datamock_Element_setValueString(element, value_str.as_ptr() as *const c_char, index) }
    }
}

// ============================================================================
// Message function wrappers and stubs
// ============================================================================

/// Get the message type as a Name (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Message_messageType(_message: *mut crate::blpapi_Message_t) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

/// Wrapper: Real API returns pointer directly, datamock uses out-parameter
#[no_mangle]
pub extern "C" fn blpapi_Message_elements(
    message: *mut crate::blpapi_Message_t,
    element: *mut *mut crate::blpapi_Element_t,
) -> i32 {
    extern "C" {
        fn datamock_Message_elements(
            message: *mut crate::blpapi_Message_t,
            element: *mut *mut crate::blpapi_Element_t,
        ) -> i32;
    }
    
    unsafe { datamock_Message_elements(message, element) }
}

// ============================================================================
// MessageIterator wrappers
// ==========================

//! Stub implementations for APIs missing from datamock.
//!
//! These stubs provide minimal implementations for APIs that datamock doesn't have
//! but xbbg-core might call. They enable testing without full API coverage.
//!
//! NOTE: Functions with signature mismatches (Element_getElement, Message_elements, etc.)
//! are now provided by shim.rs instead of here.

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
// Name function stubs
// ============================================================================

/// Duplicate a Name (mock: just return same pointer, no actual duplication)
#[no_mangle]
pub extern "C" fn blpapi_Name_duplicate(
    name: *const crate::blpapi_Name_t,
) -> *mut crate::blpapi_Name_t {
    name as *mut crate::blpapi_Name_t
}

/// Find a Name by string (mock: return NULL - name not found)
#[no_mangle]
pub extern "C" fn blpapi_Name_findName(_name_string: *const c_char) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

// ============================================================================
// Element function stubs
// ============================================================================

/// Get the Name of an Element (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Element_name(
    _element: *mut crate::blpapi_Element_t,
) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

// ============================================================================
// Message function stubs
// ============================================================================

/// Get the message type as a Name (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Message_messageType(
    _message: *mut crate::blpapi_Message_t,
) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

/// Get number of correlation IDs on a message (mock: return 1 for testing)
#[no_mangle]
pub extern "C" fn blpapi_Message_numCorrelationIds(
    _message: *mut crate::blpapi_Message_t,
) -> usize {
    1 // Mock: return 1 correlation ID
}

/// Get correlation ID at index (mock: return the correlation ID with value 0)
#[no_mangle]
pub extern "C" fn blpapi_Message_correlationId(
    _message: *mut crate::blpapi_Message_t,
    result: *mut crate::blpapi_CorrelationId_t,
    _index: usize,
) -> i32 {
    if result.is_null() {
        return -1;
    }
    // Initialize to a default Int(0) correlation ID
    unsafe {
        crate::blpapi_CorrelationId_init(result);
        crate::blpapi_CorrelationId_setInt(result, 0);
    }
    0 // Success
}

/// Get topic name for subscription messages (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Message_topicName(
    _message: *mut crate::blpapi_Message_t,
) -> *const c_char {
    ptr::null()
}

// Schema/Introspection stubs (return NULL/error)
// ============================================================================

#[no_mangle]
pub extern "C" fn blpapi_SchemaElementDefinition_name(
    _def: *const std::ffi::c_void,
) -> *const c_char {
    ptr::null()
}

#[no_mangle]
pub extern "C" fn blpapi_SchemaElementDefinition_description(
    _def: *const std::ffi::c_void,
) -> *const c_char {
    ptr::null()
}

#[no_mangle]
pub extern "C" fn blpapi_SchemaTypeDefinition_name(_def: *const std::ffi::c_void) -> *const c_char {
    ptr::null()
}

#[no_mangle]
pub extern "C" fn blpapi_SchemaTypeDefinition_description(
    _def: *const std::ffi::c_void,
) -> *const c_char {
    ptr::null()
}

#[no_mangle]
pub extern "C" fn blpapi_Operation_name(_op: *const std::ffi::c_void) -> *const c_char {
    ptr::null()
}

#[no_mangle]
pub extern "C" fn blpapi_Operation_description(_op: *const std::ffi::c_void) -> *const c_char {
    ptr::null()
}

// ============================================================================
// Logging stubs (no-op)
// ============================================================================

#[no_mangle]
pub extern "C" fn blpapi_Logging_registerCallback(
    _callback: *const std::ffi::c_void,
    _user_data: *mut std::ffi::c_void,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_Logging_setLogLevel(_level: i32) -> i32 {
    0 // Success
}

// ============================================================================
// Identity/Auth stubs (return dummy handle or success)
// ============================================================================

#[no_mangle]
pub extern "C" fn blpapi_Session_createIdentity(
    _session: *mut crate::blpapi_Session_t,
) -> *mut blpapi_Identity_t {
    // Return a non-null dummy pointer (mock identity)
    1 as *mut blpapi_Identity_t
}

#[no_mangle]
pub extern "C" fn blpapi_Session_generateAuthorizedIdentity(
    _session: *mut std::ffi::c_void,
    _auth_options: *const std::ffi::c_void,
    _correlation_id: *mut std::ffi::c_void,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_Identity_release(_identity: *mut std::ffi::c_void) {
    // No-op
}

// ============================================================================
// Request Templates stub (return NULL)
// ============================================================================

#[no_mangle]
pub extern "C" fn blpapi_Session_createSnapshotRequestTemplate(
    _session: *mut std::ffi::c_void,
    _subscription_string: *const c_char,
    _identity: *mut std::ffi::c_void,
    _correlation_id: *mut std::ffi::c_void,
) -> *mut std::ffi::c_void {
    ptr::null_mut()
}

#[no_mangle]
pub extern "C" fn blpapi_RequestTemplate_destroy(_template: *mut std::ffi::c_void) {
    // No-op
}

// ============================================================================
// Advanced SessionOptions stubs (no-op setters)
// ============================================================================

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setMaxEventQueueSize(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _size: usize,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setSlowConsumerWarningHiWaterMark(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _mark: f32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setSlowConsumerWarningLoWaterMark(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _mark: f32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setDefaultKeepAliveInactivityTime(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _seconds: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setDefaultKeepAliveResponseTimeout(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _seconds: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setDefaultSubscriptionService(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _service: *const c_char,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setDefaultTopicPrefix(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _prefix: *const c_char,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setRecordSubscriptionDataReceiveTimes(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _record: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setConnectTimeout(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _timeout_ms: u32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setServiceCheckTimeout(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _timeout_ms: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setServiceDownloadTimeout(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _timeout_ms: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_maxEventQueueSize(
    _opts: *mut crate::blpapi_SessionOptions_t,
) -> usize {
    10000 // Default queue size
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setKeepAliveEnabled(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _enabled: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setBandwidthSaveModeDisabled(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _disabled: i32,
) -> i32 {
    0 // Success
}

#[no_mangle]
pub extern "C" fn blpapi_SessionOptions_setFlushPublishedEventsTimeout(
    _opts: *mut crate::blpapi_SessionOptions_t,
    _timeout_ms: i32,
) -> i32 {
    0 // Success
}

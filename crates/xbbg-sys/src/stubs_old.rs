//! Stub implementations for APIs missing from datamock.
//!
//! These stubs provide minimal implementations for APIs that datamock doesn't have
//! but xbbg-core might call. They enable testing without full API coverage.

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
// Element function wrappers (override bindgen to match real API signatures)
// ============================================================================

/// Get the Name of an Element (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Element_name(
    _element: *mut crate::blpapi_Element_t,
) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

// ============================================================================
// Schema/Introspection stubs (return NULL/error)
// ============================================================================
// Message function wrappers
// ============================================================================

/// Get the message type as a Name (mock: return NULL)
#[no_mangle]
pub extern "C" fn blpapi_Message_messageType(
    _message: *mut crate::blpapi_Message_t,
) -> *mut crate::blpapi_Name_t {
    ptr::null_mut()
}

// ============================================================================
// Schema/Introspection stubs (return NULL/error)
// ============================================================================
// MessageIterator wrappers
// ============================================================================

/// Wrapper: Real API has 2 params (out, event), datamock has same
/// This overrides the bindgen-generated version
#[no_mangle]
pub extern "C" fn blpapi_MessageIterator_create(
    iterator: *mut *mut crate::blpapi_MessageIterator_t,
    event: *mut crate::blpapi_Event_t,
) -> i32 {
    extern "C" {
        fn datamock_MessageIterator_create(
            iterator: *mut *mut crate::blpapi_MessageIterator_t,
            event: *mut crate::blpapi_Event_t,
        ) -> i32;
    }

    unsafe { datamock_MessageIterator_create(iterator, event) }
}

// ============================================================================
// Request function wrappers
// ============================================================================

/// Get the root element of a Request
/// Real API returns pointer directly, datamock uses out-parameter
#[no_mangle]
pub extern "C" fn blpapi_Request_elements(
    request: *mut crate::blpapi_Request_t,
    element: *mut *mut crate::blpapi_Element_t,
) -> i32 {
    extern "C" {
        fn datamock_Request_getElement(
            request: *mut crate::blpapi_Request_t,
            element: *mut *mut crate::blpapi_Element_t,
        ) -> i32;
    }

    unsafe { datamock_Request_getElement(request, element) }
}

// ============================================================================
// Session wrappers
// ============================================================================

/// Wrapper: Real API has 4 params, datamock has 3
#[no_mangle]
pub extern "C" fn blpapi_Session_create(
    options: *mut crate::blpapi_SessionOptions_t,
    handler: Option<
        unsafe extern "C" fn(
            *mut crate::blpapi_Event_t,
            *mut crate::blpapi_Session_t,
            *mut std::ffi::c_void,
        ),
    >,
    _dispatcher: *mut std::ffi::c_void,
    user_data: *mut std::ffi::c_void,
) -> *mut crate::blpapi_Session_t {
    extern "C" {
        fn datamock_Session_create(
            options: *mut crate::blpapi_SessionOptions_t,
            handler: Option<
                unsafe extern "C" fn(
                    *mut crate::blpapi_Event_t,
                    *mut crate::blpapi_Session_t,
                    *mut std::ffi::c_void,
                ),
            >,
            user_data: *mut std::ffi::c_void,
        ) -> *mut crate::blpapi_Session_t;
    }

    unsafe { datamock_Session_create(options, handler, user_data) }
}

/// Wrapper: Real API has 7 params, datamock has 4
#[no_mangle]
pub extern "C" fn blpapi_Session_sendRequest(
    session: *mut crate::blpapi_Session_t,
    request: *mut crate::blpapi_Request_t,
    correlation_id: *mut crate::blpapi_CorrelationId_t,
    _identity: *mut blpapi_Identity_t,
    _event_queue: *mut std::ffi::c_void,
    _request_label: *const c_char,
    _request_label_len: i32,
) -> i32 {
    extern "C" {
        fn datamock_Session_sendRequest(
            session: *mut crate::blpapi_Session_t,
            request: *mut crate::blpapi_Request_t,
            correlation_id: *mut crate::blpapi_CorrelationId_t,
            request_label: *const c_char,
        ) -> i32;
    }

    unsafe { datamock_Session_sendRequest(session, request, correlation_id, ptr::null()) }
}

/// Wrapper: Real API has 5 params, datamock has 2
#[no_mangle]
pub extern "C" fn blpapi_Session_subscribe(
    session: *mut crate::blpapi_Session_t,
    subscriptions: *const crate::blpapi_SubscriptionList_t,
    _identity: *const std::ffi::c_void,
    _request_label: *const c_char,
    _request_label_len: i32,
) -> i32 {
    extern "C" {
        fn datamock_Session_subscribe(
            session: *mut crate::blpapi_Session_t,
            subscriptions: *mut crate::blpapi_SubscriptionList_t,
        ) -> i32;
    }

    unsafe { datamock_Session_subscribe(session, subscriptions as *mut _) }
}

/// Wrapper: Real API has 4 params, datamock has 2
#[no_mangle]
pub extern "C" fn blpapi_Session_unsubscribe(
    session: *mut crate::blpapi_Session_t,
    subscriptions: *const crate::blpapi_SubscriptionList_t,
    _request_label: *const c_char,
    _request_label_len: i32,
) -> i32 {
    extern "C" {
        fn datamock_Session_unsubscribe(
            session: *mut crate::blpapi_Session_t,
            subscriptions: *mut crate::blpapi_SubscriptionList_t,
        ) -> i32;
    }

    unsafe { datamock_Session_unsubscribe(session, subscriptions as *mut _) }
}

// ============================================================================
// SubscriptionList wrappers
// ============================================================================

/// Wrapper: Real API has 7 params, datamock has 5
#[no_mangle]
pub extern "C" fn blpapi_SubscriptionList_add(
    list: *mut crate::blpapi_SubscriptionList_t,
    topic: *const c_char,
    fields: *const c_char,
    options: *const c_char,
    correlation_id: *mut crate::blpapi_CorrelationId_t,
    _field_list: *const *const c_char,
    _num_fields: usize,
) -> i32 {
    extern "C" {
        fn datamock_SubscriptionList_add(
            list: *mut crate::blpapi_SubscriptionList_t,
            topic: *const c_char,
            fields: *const c_char,
            options: *const c_char,
            correlation_id: *mut crate::blpapi_CorrelationId_t,
        ) -> i32;
    }

    unsafe { datamock_SubscriptionList_add(list, topic, fields, options, correlation_id) }
}

// ============================================================================
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
    _size: i32,
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

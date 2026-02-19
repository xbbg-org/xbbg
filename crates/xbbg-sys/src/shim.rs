//! Shim layer adapting datamock API to Bloomberg API signatures.
//!
//! datamock has simplified signatures. This shim provides Bloomberg-compatible
//! wrappers that call the underlying datamock functions.

// Import types from parent module (which includes bindings.rs)
use super::*;

// Declare the datamock functions that were blocklisted in build.rs
// Use #[link_name] to call the actual datamock_* symbols in the C library
extern "C" {
    #[link_name = "datamock_Element_getElement"]
    fn datamock_Element_getElement_impl(
        element: *mut blpapi_Element_t,
        result: *mut *mut blpapi_Element_t,
        name: *const std::ffi::c_char,
    ) -> i32;

    #[link_name = "datamock_Element_setValueString"]
    fn datamock_Element_setValueString_impl(
        element: *mut blpapi_Element_t,
        value: *const std::ffi::c_char,
        index: usize,
    ) -> i32;

    #[link_name = "datamock_Element_setValueInt32"]
    fn datamock_Element_setValueInt32_impl(
        element: *mut blpapi_Element_t,
        value: i32,
        index: usize,
    ) -> i32;

    #[link_name = "datamock_MessageIterator_create"]
    fn datamock_MessageIterator_create_impl(
        iterator: *mut *mut blpapi_MessageIterator_t,
        event: *mut blpapi_Event_t,
    ) -> i32;

    #[link_name = "datamock_Message_elements"]
    fn datamock_Message_elements_impl(
        message: *mut blpapi_Message_t,
        element: *mut *mut blpapi_Element_t,
    ) -> i32;

    #[link_name = "datamock_Request_getElement"]
    fn datamock_Request_getElement_impl(
        request: *mut blpapi_Request_t,
        element: *mut *mut blpapi_Element_t,
    ) -> i32;

    #[link_name = "datamock_Session_create"]
    fn datamock_Session_create_impl(
        options: *mut blpapi_SessionOptions_t,
        handler: Option<
            unsafe extern "C" fn(*mut blpapi_Event_t, *mut blpapi_Session_t, *mut std::ffi::c_void),
        >,
        user_data: *mut std::ffi::c_void,
    ) -> *mut blpapi_Session_t;

    #[link_name = "datamock_Session_sendRequest"]
    fn datamock_Session_sendRequest_impl(
        session: *mut blpapi_Session_t,
        request: *mut blpapi_Request_t,
        correlation_id: *mut blpapi_CorrelationId_t,
        request_label: *const std::ffi::c_char,
    ) -> i32;

    #[link_name = "datamock_Session_subscribe"]
    fn datamock_Session_subscribe_impl(
        session: *mut blpapi_Session_t,
        subscriptions: *mut blpapi_SubscriptionList_t,
    ) -> i32;

    #[link_name = "datamock_Session_unsubscribe"]
    fn datamock_Session_unsubscribe_impl(
        session: *mut blpapi_Session_t,
        subscriptions: *mut blpapi_SubscriptionList_t,
    ) -> i32;

    #[link_name = "datamock_SubscriptionList_add"]
    fn datamock_SubscriptionList_add_impl(
        list: *mut blpapi_SubscriptionList_t,
        topic: *const std::ffi::c_char,
        fields: *const std::ffi::c_char,
        options: *const std::ffi::c_char,
        correlation_id: *mut blpapi_CorrelationId_t,
    ) -> i32;
}

// ============================================================================
// Element API - Signature Adapters
// ============================================================================

/// Element getElement: Bloomberg has 4 params, datamock has 3
///
/// Bloomberg signature: (element, result, nameString, nameObj)
/// datamock signature: (element, result, name_str)
///
/// Bloomberg accepts EITHER a C string (nameString) OR a Name pointer (nameObj).
/// We prefer nameString if provided, otherwise convert nameObj to string.

pub unsafe extern "C" fn blpapi_Element_getElement(
    element: *mut blpapi_Element_t,
    result: *mut *mut blpapi_Element_t,
    name_string: *const std::ffi::c_char, // C string name (can be null)
    name_obj: *const blpapi_Name_t,       // Name pointer (can be null)
) -> i32 {
    // Prefer name_string if provided, otherwise convert Name to string
    let name_str = if !name_string.is_null() {
        name_string
    } else if !name_obj.is_null() {
        blpapi_Name_string(name_obj as *mut blpapi_Name_t)
    } else {
        return -1; // Error: no name provided
    };
    // Call datamock's 3-param version with the string name
    datamock_Element_getElement_impl(element, result, name_str)
}

/// Element setValueString: Bloomberg has 3 params (element, value, index)
/// datamock has 3 params but different semantics - index is used

pub unsafe extern "C" fn blpapi_Element_setValueString(
    element: *mut blpapi_Element_t,
    value: *const std::ffi::c_char,
    _index: usize, // datamock uses index parameter
) -> i32 {
    datamock_Element_setValueString_impl(element, value, 0)
}

/// Element setValueInt32: Add index parameter

pub unsafe extern "C" fn blpapi_Element_setValueInt32(
    element: *mut blpapi_Element_t,
    value: i32,
    _index: usize,
) -> i32 {
    datamock_Element_setValueInt32_impl(element, value, 0)
}

/// Element setValueInt64: Missing from datamock, use Int32 as fallback

pub unsafe extern "C" fn blpapi_Element_setValueInt64(
    element: *mut blpapi_Element_t,
    value: i64,
    _index: usize,
) -> i32 {
    // Truncate to i32 for mock (acceptable for testing)
    datamock_Element_setValueInt32_impl(element, value as i32, 0)
}

/// Element setValueFloat64: Add index parameter
/// datamock doesn't have setValueFloat64, so convert to string

pub unsafe extern "C" fn blpapi_Element_setValueFloat64(
    element: *mut blpapi_Element_t,
    value: f64,
    index: usize,
) -> i32 {
    // datamock doesn't have setValueFloat64, convert to string
    let value_str = format!("{}\0", value);
    datamock_Element_setValueString_impl(
        element,
        value_str.as_ptr() as *const std::ffi::c_char,
        index,
    )
}

/// Element setElementString: Set by name
///
/// Bloomberg signature: (element, name_str, name_obj, value)
/// Implementation: getElement + setValueString
/// Note: name_str is C string, name_obj is optional Name pointer (can be NULL)

pub unsafe extern "C" fn blpapi_Element_setElementString(
    element: *mut blpapi_Element_t,
    name_str: *const std::ffi::c_char,
    _name_obj: *const blpapi_Name_t, // Ignored
    value: *const std::ffi::c_char,
) -> i32 {
    // Get child element by name string, then set its value
    let mut child: *mut blpapi_Element_t = std::ptr::null_mut();
    let rc = datamock_Element_getElement_impl(element, &mut child, name_str);
    if rc != 0 || child.is_null() {
        return rc;
    }
    datamock_Element_setValueString_impl(child, value, 0)
}

/// Element setElementInt32: Set by name

pub unsafe extern "C" fn blpapi_Element_setElementInt32(
    element: *mut blpapi_Element_t,
    name_str: *const std::ffi::c_char,
    _name_obj: *const blpapi_Name_t, // Ignored
    value: i32,
) -> i32 {
    let mut child: *mut blpapi_Element_t = std::ptr::null_mut();
    let rc = datamock_Element_getElement_impl(element, &mut child, name_str);
    if rc != 0 || child.is_null() {
        return rc;
    }
    datamock_Element_setValueInt32_impl(child, value, 0)
}

/// Element setElementFloat64: Set by name

pub unsafe extern "C" fn blpapi_Element_setElementFloat64(
    element: *mut blpapi_Element_t,
    name_str: *const std::ffi::c_char,
    _name_obj: *const blpapi_Name_t, // Ignored
    value: f64,
) -> i32 {
    let mut child: *mut blpapi_Element_t = std::ptr::null_mut();
    let rc = datamock_Element_getElement_impl(element, &mut child, name_str);
    if rc != 0 || child.is_null() {
        return rc;
    }
    // datamock doesn't have setValueFloat64, convert to string
    let value_str = format!("{}\0", value);
    datamock_Element_setValueString_impl(child, value_str.as_ptr() as *const std::ffi::c_char, 0)
}

// ============================================================================
// MessageIterator API - Return Type Adapter
// ============================================================================

/// MessageIterator create: Bloomberg returns pointer, datamock returns int
///
/// Bloomberg signature: (event) -> *mut MessageIterator
/// datamock signature: (iterator_out, event) -> int

pub unsafe extern "C" fn blpapi_MessageIterator_create(
    event: *mut blpapi_Event_t,
) -> *mut blpapi_MessageIterator_t {
    let mut iterator: *mut blpapi_MessageIterator_t = std::ptr::null_mut();
    let rc = datamock_MessageIterator_create_impl(&mut iterator, event);
    if rc != 0 {
        return std::ptr::null_mut();
    }
    iterator
}

// ============================================================================
// Message API - Return Type Adapter
// ============================================================================

/// Message elements: Bloomberg returns pointer, datamock returns int
///
/// Bloomberg signature: (message) -> *mut Element
/// datamock signature: (message, element_out) -> int

pub unsafe extern "C" fn blpapi_Message_elements(
    message: *mut blpapi_Message_t,
) -> *mut blpapi_Element_t {
    let mut element: *mut blpapi_Element_t = std::ptr::null_mut();
    let rc = datamock_Message_elements_impl(message, &mut element);
    if rc != 0 {
        return std::ptr::null_mut();
    }
    element
}

// ============================================================================
// Request API - Return Type Adapter
// ============================================================================

/// Request elements: Bloomberg returns pointer, datamock returns int
///
/// Bloomberg signature: (request) -> *mut Element
/// datamock signature: (request, element_out) -> int

pub unsafe extern "C" fn blpapi_Request_elements(
    request: *mut blpapi_Request_t,
) -> *mut blpapi_Element_t {
    let mut element: *mut blpapi_Element_t = std::ptr::null_mut();
    let rc = datamock_Request_getElement_impl(request, &mut element);
    if rc != 0 {
        return std::ptr::null_mut();
    }
    element
}

// ============================================================================
// Session API - Signature Adapters
// ============================================================================

/// Session create: Bloomberg has 4 params, datamock has 3
///
/// Bloomberg signature: (options, handler, dispatcher, userData) -> *mut Session
/// datamock signature: (options, handler, userData) -> *mut Session

pub unsafe extern "C" fn blpapi_Session_create(
    options: *mut blpapi_SessionOptions_t,
    handler: Option<
        unsafe extern "C" fn(*mut blpapi_Event_t, *mut blpapi_Session_t, *mut std::ffi::c_void),
    >,
    _dispatcher: *mut std::ffi::c_void, // Ignored - datamock doesn't use dispatcher
    user_data: *mut std::ffi::c_void,
) -> *mut blpapi_Session_t {
    datamock_Session_create_impl(options, handler, user_data)
}

/// Session sendRequest: Bloomberg has 7 params, datamock has 4
///
/// Bloomberg signature: (session, request, correlationId, identity, eventQueue, requestLabel, requestLabelLen)
/// datamock signature: (session, request, correlationId, requestLabel)

pub unsafe extern "C" fn blpapi_Session_sendRequest(
    session: *mut blpapi_Session_t,
    request: *mut blpapi_Request_t,
    correlation_id: *mut blpapi_CorrelationId_t,
    _identity: *mut blpapi_Identity_t,   // Ignored
    _event_queue: *mut std::ffi::c_void, // Ignored
    request_label: *const std::ffi::c_char,
    _request_label_len: i32, // Ignored - datamock uses null-terminated strings
) -> i32 {
    datamock_Session_sendRequest_impl(session, request, correlation_id, request_label)
}

/// Session subscribe: Bloomberg has 5 params, datamock has 2
///
/// Bloomberg signature: (session, subscriptions, identity, requestLabel, requestLabelLen)
/// datamock signature: (session, subscriptions)

pub unsafe extern "C" fn blpapi_Session_subscribe(
    session: *mut blpapi_Session_t,
    subscriptions: *const blpapi_SubscriptionList_t,
    _identity: *const blpapi_Identity_t, // Ignored (const, not mut)
    _request_label: *const std::ffi::c_char, // Ignored
    _request_label_len: i32,             // Ignored
) -> i32 {
    datamock_Session_subscribe_impl(session, subscriptions as *mut blpapi_SubscriptionList_t)
}

/// Session unsubscribe: Bloomberg has 4 params, datamock has 2
///
/// Bloomberg signature: (session, subscriptions, requestLabel, requestLabelLen)
/// datamock signature: (session, subscriptions)

pub unsafe extern "C" fn blpapi_Session_unsubscribe(
    session: *mut blpapi_Session_t,
    subscriptions: *const blpapi_SubscriptionList_t,
    _request_label: *const std::ffi::c_char, // Ignored
    _request_label_len: i32,                 // Ignored
) -> i32 {
    datamock_Session_unsubscribe_impl(session, subscriptions as *mut blpapi_SubscriptionList_t)
}

// ============================================================================
// SubscriptionList API - Signature Adapters
// ============================================================================

/// SubscriptionList add: Bloomberg has 7 params, datamock has 5
///
/// Bloomberg signature: (list, topic, correlationId, fields, options, fieldLen, optionsLen)
/// datamock signature: (list, topic, fields, options, correlationId)

pub unsafe extern "C" fn blpapi_SubscriptionList_add(
    list: *mut blpapi_SubscriptionList_t,
    topic: *const std::ffi::c_char,
    correlation_id: *const blpapi_CorrelationId_t,
    fields: *const *const std::ffi::c_char,
    options: *const *const std::ffi::c_char,
    _fields_len: usize,  // Ignored - datamock uses null-terminated strings
    _options_len: usize, // Ignored
) -> i32 {
    // Bloomberg API takes arrays of strings, datamock takes single strings
    // For mock, just pass the first element (or null if array is null)
    let fields_str = if fields.is_null() {
        std::ptr::null()
    } else {
        *fields
    };
    let options_str = if options.is_null() {
        std::ptr::null()
    } else {
        *options
    };

    datamock_SubscriptionList_add_impl(
        list,
        topic,
        fields_str,
        options_str,
        correlation_id as *mut blpapi_CorrelationId_t,
    )
}

// ============================================================================
// Constants
// ============================================================================

/// BLPAPI_ELEMENT_INDEX_END constant
pub const BLPAPI_ELEMENT_INDEX_END: usize = usize::MAX;

// ============================================================================
// Name API
// ============================================================================
// Name functions (blpapi_Name_create, blpapi_Name_destroy, blpapi_Name_string)
// are provided directly by bindgen-generated bindings with correct #[link_name] attributes

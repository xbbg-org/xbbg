//! FFI bindings to Bloomberg BLPAPI
//!
//! Re-exports from xbbg-sys plus local type definitions.

// --- Opaque types ---
pub use xbbg_sys::{
    blpapi_CorrelationId_t, blpapi_Element_t, blpapi_Event_t, blpapi_Identity_t,
    blpapi_MessageIterator_t, blpapi_Message_t, blpapi_Name_t, blpapi_Request_t, blpapi_Service_t,
    blpapi_SessionOptions_t, blpapi_Session_t, blpapi_SubscriptionList_t,
};

// --- Name functions ---
pub use xbbg_sys::{
    blpapi_Name_create, blpapi_Name_destroy, blpapi_Name_duplicate, blpapi_Name_findName,
    blpapi_Name_string,
};

// --- Element functions ---
pub use xbbg_sys::{
    blpapi_Element_datatype, blpapi_Element_getElement, blpapi_Element_getElementAt,
    blpapi_Element_getValueAsBool, blpapi_Element_getValueAsElement,
    blpapi_Element_getValueAsFloat64, blpapi_Element_getValueAsInt32,
    blpapi_Element_getValueAsInt64, blpapi_Element_getValueAsString, blpapi_Element_isArray,
    blpapi_Element_isNull, blpapi_Element_name, blpapi_Element_numElements,
    blpapi_Element_numValues,
};

// --- Element setters ---
pub use xbbg_sys::{
    blpapi_Element_setElementFloat64, blpapi_Element_setElementInt32,
    blpapi_Element_setElementString, blpapi_Element_setValueFloat64, blpapi_Element_setValueInt32,
    blpapi_Element_setValueInt64, blpapi_Element_setValueString, BLPAPI_ELEMENT_INDEX_END,
};

// --- Message functions ---
pub use xbbg_sys::{
    blpapi_Message_correlationId, blpapi_Message_elements, blpapi_Message_messageType,
    blpapi_Message_numCorrelationIds, blpapi_Message_topicName,
};

// --- Event functions ---
pub use xbbg_sys::{
    blpapi_Event_eventType, blpapi_Event_release, blpapi_MessageIterator_create,
    blpapi_MessageIterator_destroy, blpapi_MessageIterator_next,
};

// --- Session functions ---
pub use xbbg_sys::{
    blpapi_Session_create, blpapi_Session_createIdentity, blpapi_Session_destroy,
    blpapi_Session_getService, blpapi_Session_nextEvent, blpapi_Session_openService,
    blpapi_Session_sendRequest, blpapi_Session_start, blpapi_Session_stop,
    blpapi_Session_subscribe, blpapi_Session_tryNextEvent, blpapi_Session_unsubscribe,
};

// --- Service functions ---
pub use xbbg_sys::{blpapi_Service_createRequest, blpapi_Service_name};

// --- Request functions ---
pub use xbbg_sys::{blpapi_Request_destroy, blpapi_Request_elements};

// --- SubscriptionList functions ---
pub use xbbg_sys::{
    blpapi_SubscriptionList_add, blpapi_SubscriptionList_create, blpapi_SubscriptionList_destroy,
};

// --- CorrelationId helpers ---
pub use xbbg_sys::{
    blpapi_CorrelationId_asInt, blpapi_CorrelationId_asPointer, blpapi_CorrelationId_init,
    blpapi_CorrelationId_setInt, blpapi_CorrelationId_setPointer, blpapi_CorrelationId_type,
};

// --- SessionOptions functions ---
pub use xbbg_sys::{
    blpapi_SessionOptions_create, blpapi_SessionOptions_destroy,
    blpapi_SessionOptions_setServerHost, blpapi_SessionOptions_setServerPort,
};

// --- HighPrecisionDatetime (defined locally for layout control) ---

/// Bloomberg high-precision datetime structure.
///
/// This is ALWAYS defined locally (not re-exported from blpapi-sys) to guarantee
/// exact layout control. 16 bytes, packed representation.
#[repr(C, packed)]
#[derive(Copy, Clone, Debug, PartialEq)]
pub struct blpapi_HighPrecisionDatetime_t {
    pub parts: u8,
    pub hours: u8,
    pub minutes: u8,
    pub seconds: u8,
    pub milliseconds: u16,
    pub month: u8,
    pub day: u8,
    pub year: u16,
    pub offset: i16,
    pub picoseconds: u32,
}

const _: () = assert!(std::mem::size_of::<blpapi_HighPrecisionDatetime_t>() == 16);

// Declare datetime FFI using our local type (not blpapi-sys's)
extern "C" {
    pub fn blpapi_Element_getValueAsHighPrecisionDatetime(
        element: *mut blpapi_Element_t,
        buffer: *mut blpapi_HighPrecisionDatetime_t,
        index: usize,
    ) -> i32;
}

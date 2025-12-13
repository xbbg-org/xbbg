use crate::errors::{BlpError, Result};
use crate::message::MessageRef;

#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub enum EventType {
    Admin,
    SessionStatus,
    SubscriptionStatus,
    RequestStatus,
    Response,
    PartialResponse,
    SubscriptionData,
    ServiceStatus,
    Timeout,
    AuthorizationStatus,
    ResolutionStatus,
    TopicStatus,
    TokenStatus,
    Unknown(i32),
}

impl From<i32> for EventType {
    fn from(v: i32) -> Self {
        match v {
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_ADMIN as i32 => EventType::Admin,
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_SESSION_STATUS as i32 => {
                EventType::SessionStatus
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_SUBSCRIPTION_STATUS as i32 => {
                EventType::SubscriptionStatus
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_REQUEST_STATUS as i32 => {
                EventType::RequestStatus
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_RESPONSE as i32 => EventType::Response,
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_PARTIAL_RESPONSE as i32 => {
                EventType::PartialResponse
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_SUBSCRIPTION_DATA as i32 => {
                EventType::SubscriptionData
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_SERVICE_STATUS as i32 => {
                EventType::ServiceStatus
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_TIMEOUT as i32 => EventType::Timeout,
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_AUTHORIZATION_STATUS as i32 => {
                EventType::AuthorizationStatus
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_RESOLUTION_STATUS as i32 => {
                EventType::ResolutionStatus
            }
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_TOPIC_STATUS as i32 => EventType::TopicStatus,
            x if x == blpapi_sys::BLPAPI_EVENTTYPE_TOKEN_STATUS as i32 => EventType::TokenStatus,
            other => EventType::Unknown(other),
        }
    }
}

pub struct Event {
    ptr: *mut blpapi_sys::blpapi_Event_t,
}

unsafe impl Send for Event {}
unsafe impl Sync for Event {}

impl Event {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_Event_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "received null event pointer".into(),
            });
        }
        Ok(Self { ptr })
    }

    pub fn event_type(&self) -> EventType {
        let t = unsafe { blpapi_sys::blpapi_Event_eventType(self.ptr) };
        EventType::from(t)
    }

    #[allow(dead_code)]
    pub(crate) fn as_raw(&self) -> *mut blpapi_sys::blpapi_Event_t {
        self.ptr
    }

    pub fn iter(&self) -> MessageIter {
        MessageIter::new(self)
    }
}

impl Drop for Event {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe { blpapi_sys::blpapi_Event_release(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

pub struct MessageIter {
    it: *mut blpapi_sys::blpapi_MessageIterator_t,
}

impl MessageIter {
    fn new(event: &Event) -> Self {
        let it = unsafe { blpapi_sys::blpapi_MessageIterator_create(event.ptr) };
        Self { it }
    }
}

impl Iterator for MessageIter {
    type Item = MessageRef;

    fn next(&mut self) -> Option<Self::Item> {
        let mut msg_ptr: *mut blpapi_sys::blpapi_Message_t = std::ptr::null_mut();
        let rc = unsafe { blpapi_sys::blpapi_MessageIterator_next(self.it, &mut msg_ptr) };
        if rc == 0 {
            MessageRef::from_raw(msg_ptr)
        } else {
            None
        }
    }
}

impl Drop for MessageIter {
    fn drop(&mut self) {
        if !self.it.is_null() {
            unsafe { blpapi_sys::blpapi_MessageIterator_destroy(self.it) };
            self.it = std::ptr::null_mut();
        }
    }
}

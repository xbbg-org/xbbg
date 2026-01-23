//! Bloomberg session management

use std::cell::Cell;
use std::ffi::CString;
use std::marker::PhantomData;

use crate::correlation::CorrelationId;
use crate::errors::{BlpError, Result};
use crate::event::Event;
use crate::identity::Identity;
use crate::request::Request;
use crate::service::Service;
use crate::subscription::SubscriptionList;

// Re-export SessionOptions from options module
pub use crate::options::SessionOptions;

/// Bloomberg session for making requests and receiving data.
///
/// A Session represents a connection to the Bloomberg API. It is Send but NOT Sync,
/// meaning it can be moved between threads but cannot be accessed concurrently from
/// multiple threads. If you need concurrent access, wrap it in a `Mutex<Session>`.
///
/// # Examples
///
/// ```ignore
/// use xbbg_core::{Session, SessionOptions, EventType, Name};
///
/// // Pre-intern names (do once at setup)
/// let securities = Name::get_or_intern("securities");
/// let fields = Name::get_or_intern("fields");
///
/// // Create and start session
/// let mut opts = SessionOptions::new()?;
/// opts.set_server_host("localhost")?;
/// opts.set_server_port(8194);
///
/// let sess = Session::new(&opts)?;
/// sess.start()?;
///
/// // Wait for SessionStarted
/// loop {
///     if let Ok(ev) = sess.next_event(Some(5000)) {
///         if ev.event_type() == EventType::SessionStatus {
///             break;
///         }
///     }
/// }
///
/// // Open service and make request
/// sess.open_service("//blp/refdata")?;
/// let svc = sess.get_service("//blp/refdata")?;
/// let mut req = svc.create_request("ReferenceDataRequest")?;
///
/// req.append_string(&securities, "IBM US Equity")?;
/// req.append_string(&fields, "PX_LAST")?;
///
/// sess.send_request(&req, None, None)?;
///
/// // Process response
/// loop {
///     if let Ok(ev) = sess.next_event(Some(5000)) {
///         if ev.event_type() == EventType::Response {
///             for msg in ev.messages() {
///                 // Extract data...
///             }
///             break;
///         }
///     }
/// }
///
/// sess.stop();
/// ```
///
/// # Threading Model
/// - `Send`: Yes - can be moved between threads
/// - `Sync`: No - cannot be accessed concurrently (use `Mutex` if needed)
///
/// This matches Bloomberg's threading model where session mutations (start, stop,
/// subscribe, sendRequest) are NOT thread-safe and must be serialized by the caller.
pub struct Session {
    ptr: *mut crate::ffi::blpapi_Session_t,
    _not_sync: PhantomData<Cell<()>>, // Makes !Sync
}

// SAFETY: Session can be sent between threads
// The underlying Bloomberg API allows a session to be used from different threads
// (just not concurrently)
unsafe impl Send for Session {}

// DO NOT implement Sync for Session
// Bloomberg API requires serialized access to session methods

impl Session {
    /// Create a new session with the given options.
    ///
    /// Creates a session but does not start it. Call `start()` to initiate the connection.
    ///
    /// # Arguments
    /// * `options` - Session configuration options
    ///
    /// # Returns
    /// A new Session on success, or an error if creation fails
    pub fn new(options: &SessionOptions) -> Result<Self> {
        // SAFETY: We're calling the Bloomberg API with valid pointers
        // - options.as_raw() is guaranteed valid by SessionOptions
        // - handler, dispatcher, and eventQueue are None/null (synchronous mode)
        let ptr = unsafe {
            crate::ffi::blpapi_Session_create(
                options.as_raw(),
                None,                 // handler (None = synchronous mode)
                std::ptr::null_mut(), // dispatcher
                std::ptr::null_mut(), // eventQueue
            )
        };

        if ptr.is_null() {
            return Err(BlpError::SessionStart {
                source: None,
                label: None,
            });
        }

        Ok(Self {
            ptr,
            _not_sync: PhantomData,
        })
    }

    /// Start the session.
    ///
    /// This initiates the connection to the Bloomberg API. You should wait for
    /// a `SessionStatus` event with `SessionStarted` message before making requests.
    ///
    /// # Returns
    /// Ok(()) on success, Err on failure
    pub fn start(&self) -> Result<()> {
        // SAFETY: We're calling the Bloomberg API with a valid pointer
        let rc = unsafe { crate::ffi::blpapi_Session_start(self.ptr) };

        if rc != 0 {
            return Err(BlpError::SessionStart {
                source: None,
                label: None,
            });
        }

        Ok(())
    }

    /// Stop the session.
    ///
    /// This closes the connection to the Bloomberg API. After calling stop(),
    /// the session cannot be restarted. Always call this before dropping the session
    /// to ensure clean shutdown.
    pub fn stop(&self) {
        // SAFETY: We're calling the Bloomberg API with a valid pointer
        unsafe {
            crate::ffi::blpapi_Session_stop(self.ptr);
        }
    }

    /// Wait for the next event with an optional timeout.
    ///
    /// This is the primary method for receiving data from Bloomberg. Blocks until
    /// an event is available or the timeout expires.
    ///
    /// # Arguments
    /// * `timeout_ms` - Optional timeout in milliseconds. None means wait indefinitely.
    ///
    /// # Returns
    /// The next Event, or an error if the timeout expires or an error occurs
    pub fn next_event(&self, timeout_ms: Option<u32>) -> Result<Event> {
        let mut event_ptr: *mut crate::ffi::blpapi_Event_t = std::ptr::null_mut();

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Session_nextEvent(self.ptr, &mut event_ptr, timeout_ms.unwrap_or(0))
        };

        if rc != 0 {
            return Err(BlpError::Timeout);
        }

        if event_ptr.is_null() {
            return Err(BlpError::Internal {
                detail: "nextEvent returned null event".into(),
            });
        }

        // SAFETY: event_ptr is guaranteed non-null and valid from blpapi_Session_nextEvent
        Ok(unsafe { Event::from_raw(event_ptr) })
    }

    /// Try to get the next event without blocking.
    ///
    /// Non-blocking version of `next_event()`. Returns immediately.
    ///
    /// # Returns
    /// Some(Event) if an event is available, None if no event is ready
    pub fn try_next_event(&self) -> Option<Event> {
        let mut event_ptr: *mut crate::ffi::blpapi_Event_t = std::ptr::null_mut();

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe { crate::ffi::blpapi_Session_tryNextEvent(self.ptr, &mut event_ptr) };

        if rc == 0 && !event_ptr.is_null() {
            // SAFETY: event_ptr is guaranteed non-null and valid from blpapi_Session_tryNextEvent
            Some(unsafe { Event::from_raw(event_ptr) })
        } else {
            None
        }
    }

    /// Open a service
    ///
    /// This must be called before you can get the service and create requests.
    /// You should wait for a ServiceOpened event before calling get_service().
    ///
    /// # Arguments
    /// * `name` - The service name (e.g., "//blp/refdata")
    ///
    /// # Returns
    /// Ok(()) on success, Err on failure
    pub fn open_service(&self, name: &str) -> Result<()> {
        let c_name = CString::new(name).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid service name: {}", e),
        })?;

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe { crate::ffi::blpapi_Session_openService(self.ptr, c_name.as_ptr()) };

        if rc != 0 {
            return Err(BlpError::OpenService {
                service: name.to_string(),
                source: None,
                label: None,
            });
        }

        Ok(())
    }

    /// Get a service handle
    ///
    /// The service must have been opened with open_service() first.
    ///
    /// # Arguments
    /// * `name` - The service name (e.g., "//blp/refdata")
    ///
    /// # Returns
    /// A Service handle on success, or an error if the service is not open
    pub fn get_service(&self, name: &str) -> Result<Service> {
        let c_name = CString::new(name).map_err(|e| BlpError::InvalidArgument {
            detail: format!("invalid service name: {}", e),
        })?;

        let mut service_ptr: *mut crate::ffi::blpapi_Service_t = std::ptr::null_mut();

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Session_getService(self.ptr, &mut service_ptr, c_name.as_ptr())
        };

        if rc != 0 {
            return Err(BlpError::OpenService {
                service: name.to_string(),
                source: None,
                label: None,
            });
        }

        Service::from_raw(service_ptr)
    }

    /// Send a request
    ///
    /// # Arguments
    /// * `req` - The request to send
    /// * `identity` - Optional identity for authorization
    /// * `cid` - Optional correlation ID for tracking the response
    ///
    /// # Returns
    /// Ok(()) on success, Err on failure
    pub fn send_request(
        &self,
        req: &Request,
        identity: Option<&Identity>,
        cid: Option<&CorrelationId>,
    ) -> Result<()> {
        // Prepare correlation ID
        let mut cid_ffi = match cid {
            Some(c) => c.to_ffi(),
            None => CorrelationId::default().to_ffi(),
        };

        // Get identity pointer
        let identity_ptr = match identity {
            Some(id) => id.as_ptr(),
            None => std::ptr::null_mut(),
        };

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Session_sendRequest(
                self.ptr,
                req.as_ptr(),
                &mut cid_ffi,
                identity_ptr,
                std::ptr::null_mut(), // eventQueue (null = use session's queue)
                std::ptr::null(),     // requestLabel
                0,                    // requestLabelLen
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Session_sendRequest failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Subscribe to market data
    ///
    /// # Arguments
    /// * `subs` - The subscription list
    /// * `label` - Optional label for the subscription
    ///
    /// # Returns
    /// Ok(()) on success, Err on failure
    pub fn subscribe(&self, subs: &SubscriptionList, label: Option<&str>) -> Result<()> {
        let (label_ptr, label_len, _label_cstring) = match label {
            Some(l) => {
                let cs = CString::new(l).map_err(|e| BlpError::InvalidArgument {
                    detail: format!("invalid label: {}", e),
                })?;
                let len = l.len() as i32;
                (cs.as_ptr(), len, Some(cs))
            }
            None => (std::ptr::null(), 0, None),
        };

        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Session_subscribe(
                self.ptr,
                subs.as_ptr(),
                std::ptr::null(), // identity
                label_ptr,
                label_len,
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Session_subscribe failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Unsubscribe from market data
    ///
    /// # Arguments
    /// * `subs` - The subscription list to unsubscribe
    ///
    /// # Returns
    /// Ok(()) on success, Err on failure
    pub fn unsubscribe(&self, subs: &SubscriptionList) -> Result<()> {
        // SAFETY: We're calling the Bloomberg API with valid pointers
        let rc = unsafe {
            crate::ffi::blpapi_Session_unsubscribe(
                self.ptr,
                subs.as_ptr(),
                std::ptr::null(), // requestLabel
                0,                // requestLabelLen
            )
        };

        if rc != 0 {
            return Err(BlpError::Internal {
                detail: format!("blpapi_Session_unsubscribe failed with rc={}", rc),
            });
        }

        Ok(())
    }

    /// Create an identity for authorization
    ///
    /// # Returns
    /// A new Identity on success, or an error if creation fails
    pub fn create_identity(&self) -> Result<Identity> {
        // SAFETY: We're calling the Bloomberg API with a valid pointer
        let identity_ptr = unsafe { crate::ffi::blpapi_Session_createIdentity(self.ptr) };

        Identity::from_raw(identity_ptr)
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // SAFETY: We're calling the Bloomberg API to clean up the session
            // First stop the session, then destroy it
            unsafe {
                crate::ffi::blpapi_Session_stop(self.ptr);
                crate::ffi::blpapi_Session_destroy(self.ptr);
            }
            self.ptr = std::ptr::null_mut();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Compile-time verification that Session is Send but NOT Sync
    fn assert_send<T: Send>() {}
    fn assert_not_sync<T: Send>() {
        // This function compiles only if T is NOT Sync
        // If T were Sync, we could add `T: Sync` bound and it would still compile
    }

    #[test]
    fn session_is_send() {
        assert_send::<Session>();
    }

    #[test]
    fn session_is_not_sync() {
        assert_not_sync::<Session>();
        // If you uncomment the next line, it should NOT compile:
        // fn assert_sync<T: Sync>() {}
        // assert_sync::<Session>();
    }
}

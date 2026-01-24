//! Message type for Bloomberg BLPAPI
//!
//! Messages are the primary data containers in Bloomberg responses.
//! Each message contains a root element with field data.
//!
//! **Zero allocation**: Messages are borrowed from Events and provide
//! zero-cost access to their contents.

use crate::{ffi, Element, Name};
use std::ffi::CStr;
use std::marker::PhantomData;
use std::ptr::NonNull;
use std::rc::Rc;

/// Bloomberg message wrapper.
///
/// Borrowed from Event, valid only while Event is alive.
/// NOT thread-safe - must be consumed on receiving thread.
///
/// # Lifetime
/// The lifetime `'a` ties this Message to its parent Event.
/// Do not store Messages - extract data immediately.
///
/// # Thread Safety
/// Messages are `!Send + !Sync` because:
/// - Bloomberg's API is not thread-safe
/// - Messages must be processed on the thread that received them
///
/// # Performance
/// All methods are `#[inline(always)]` for zero-cost abstraction.
#[repr(transparent)]
pub struct Message<'a> {
    ptr: *mut ffi::blpapi_Message_t,
    _life: PhantomData<&'a ()>,
    _marker: PhantomData<Rc<()>>, // Makes !Send + !Sync
}

impl<'a> Message<'a> {
    /// Construct from raw pointer (internal use only).
    ///
    /// # Safety
    /// Caller must ensure:
    /// - `ptr` is a valid `blpapi_Message_t` pointer
    /// - The lifetime `'a` does not outlive the parent Event
    /// - The pointer remains valid for the lifetime `'a`
    #[inline]
    pub(crate) unsafe fn from_raw(ptr: *mut ffi::blpapi_Message_t) -> Self {
        Self {
            ptr,
            _life: PhantomData,
            _marker: PhantomData,
        }
    }

    /// Get root element of this message.
    ///
    /// The root element contains all field data for this message.
    /// Use this to navigate the message structure.
    ///
    /// # Performance
    /// This is a hot path method - returns immediately with no allocation.
    #[inline(always)]
    pub fn elements(&self) -> Element<'a> {
        // SAFETY: blpapi_Message_elements returns a valid Element pointer.
        // The Element borrows from this Message, so lifetime 'a is correct.
        // Bloomberg guarantees the element pointer is valid for the message's lifetime.
        // Element::new is safe to call with a valid pointer.
        let ptr = unsafe { ffi::blpapi_Message_elements(self.ptr) };
        Element::new(ptr)
    }

    /// Message type name.
    ///
    /// Returns the schema type of this message (e.g., "ReferenceDataResponse").
    /// This is an owned Name because it's duplicated from Bloomberg's internal storage.
    ///
    /// # Performance
    /// This allocates a new Name (increments refcount). Cache if called repeatedly.
    #[inline(always)]
    pub fn message_type(&self) -> Name {
        self.name()
    }

    /// Message name (alias for `message_type()`).
    ///
    /// Returns the schema type of this message (e.g., "ReferenceDataResponse").
    /// This is an owned Name because it's duplicated from Bloomberg's internal storage.
    ///
    /// # Performance
    /// This allocates a new Name (increments refcount). Cache if called repeatedly.
    #[inline(always)]
    pub fn name(&self) -> Name {
        // SAFETY: blpapi_Message_messageType returns a valid Name pointer.
        // We duplicate it to get an owned Name that we can return.
        // The duplicate increments Bloomberg's internal refcount.
        let ptr = unsafe { ffi::blpapi_Message_messageType(self.ptr) };
        // SAFETY: blpapi_Name_duplicate returns a valid pointer
        unsafe { Name::from_raw(NonNull::new(ffi::blpapi_Name_duplicate(ptr)).unwrap()) }
    }

    /// Topic name (for subscription messages).
    ///
    /// Returns the topic string for subscription data messages.
    /// Returns `None` for request/response messages.
    ///
    /// # Performance
    /// Zero allocation - returns a reference to Bloomberg's internal buffer.
    ///
    /// # Example
    /// ```ignore
    /// if let Some(topic) = msg.topic_name() {
    ///     println!("Received data for: {}", topic);
    /// }
    /// ```
    #[inline]
    pub fn topic_name(&self) -> Option<&str> {
        // SAFETY: blpapi_Message_topicName returns a pointer to an internal
        // null-terminated C string, or null if this is not a subscription message.
        // The string is valid for the lifetime of the message.
        let ptr = unsafe { ffi::blpapi_Message_topicName(self.ptr) };
        if ptr.is_null() {
            None
        } else {
            // SAFETY: Bloomberg guarantees valid UTF-8 in topic names.
            // Topic names are always ASCII/UTF-8 strings.
            // The string lives as long as the message (lifetime 'a).
            Some(unsafe { CStr::from_ptr(ptr).to_str().unwrap_unchecked() })
        }
    }

    /// Get raw pointer for FFI calls (internal use).
    ///
    /// This is used internally by other xbbg-core types that need to call
    /// Bloomberg C API functions.
    #[inline(always)]
    #[allow(dead_code)] // Used in integration, not unit tests
    pub(crate) fn as_ptr(&self) -> *mut ffi::blpapi_Message_t {
        self.ptr
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_size() {
        // Message should be pointer-sized (transparent wrapper)
        assert_eq!(
            std::mem::size_of::<Message>(),
            std::mem::size_of::<*mut ()>()
        );
    }

    #[test]
    fn test_message_alignment() {
        // Message should have pointer alignment
        assert_eq!(
            std::mem::align_of::<Message>(),
            std::mem::align_of::<*mut ()>()
        );
    }
}

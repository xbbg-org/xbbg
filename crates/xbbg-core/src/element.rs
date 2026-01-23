//! Element type for Bloomberg BLPAPI
//!
//! Elements are the core data structure in Bloomberg messages.
//! They contain field values and can be nested (sequences/choices).
//!
//! **Zero allocation**: All getters return borrowed data or copy primitives.
//! No heap allocations in hot path.

use crate::{ffi, DataType, HighPrecisionDatetime, Name};
use std::ffi::CStr;
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::ptr::NonNull;

/// Element in a Bloomberg message. Zero-cost wrapper.
///
/// Lifetime tied to parent Message/Event - do not store.
///
/// # Hot Path Pattern (Recommended)
///
/// For streaming data / high-performance code, pre-intern Names at setup:
///
/// ```ignore
/// // SETUP (once, before processing loop)
/// let security_data = Name::get_or_intern("securityData");
/// let field_data = Name::get_or_intern("fieldData");
/// let px_last = Name::get_or_intern("PX_LAST");
///
/// // HOT LOOP (millions of messages)
/// for msg in messages {
///     let root = msg.elements();
///     if let Some(sd) = root.get(&security_data) {
///         if let Some(fd) = sd.get(&field_data) {
///             let price = fd.get(&px_last).and_then(|e| e.get_f64(0));
///         }
///     }
/// }
/// ```
///
/// # Casual Use
///
/// For scripts and non-performance-critical code, `get_by_str()` is fine:
///
/// ```ignore
/// let price = element.get_by_str("PX_LAST").and_then(|e| e.get_f64(0));
/// ```
///
/// # Performance
/// All methods are `#[inline(always)]` for zero-cost abstraction.
/// Getters use `MaybeUninit` to avoid zero-initialization overhead.
#[repr(transparent)]
pub struct Element<'a> {
    ptr: *mut ffi::blpapi_Element_t,
    _life: PhantomData<&'a ()>,
}

impl<'a> Element<'a> {
    /// Create element from raw pointer.
    ///
    /// # Safety
    /// Pointer must be valid and the lifetime must not outlive the parent message/event.
    #[inline(always)]
    pub(crate) fn new(ptr: *mut ffi::blpapi_Element_t) -> Self {
        Self {
            ptr,
            _life: PhantomData,
        }
    }

    /// Get child by name. Single call = existence check + retrieval.
    ///
    /// This is the optimal Bloomberg pattern: no separate `hasElement` call.
    ///
    /// # Performance
    /// Target: < 100ns per call.
    #[inline(always)]
    pub fn get(&self, name: &Name) -> Option<Element<'a>> {
        let mut out = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getElement writes a valid pointer on success (rc==0).
        // MaybeUninit avoids zero-initialization overhead.
        let rc = unsafe {
            ffi::blpapi_Element_getElement(
                self.ptr,
                out.as_mut_ptr(),
                std::ptr::null(),
                name.as_ptr(),
            )
        };
        (rc == 0).then(|| Element::new(unsafe { out.assume_init() }))
    }

    /// Get child by string name (convenience method, NOT for hot paths).
    ///
    /// Uses a thread-local cache to avoid repeated FFI calls, but still has
    /// HashMap lookup + clone overhead on every call.
    ///
    /// # Performance
    /// **For hot paths (streaming data), use `get(&Name)` instead:**
    /// ```ignore
    /// // Setup (once, before hot loop)
    /// let px_last = Name::get_or_intern("PX_LAST");
    ///
    /// // Hot loop (millions of times) - fastest
    /// element.get(&px_last)
    /// ```
    ///
    /// This method is fine for one-off lookups, scripts, and non-performance-critical code.
    ///
    /// # Example
    /// ```ignore
    /// // OK for casual use
    /// let px = element.get_by_str("PX_LAST");
    /// ```
    #[inline(always)]
    pub fn get_by_str(&self, name: &str) -> Option<Element<'a>> {
        let interned = Name::get_or_intern(name);
        self.get(&interned)
    }

    /// Get child by index.
    ///
    /// Use for iterating through arrays or sequences.
    #[inline(always)]
    pub fn get_at(&self, i: usize) -> Option<Element<'a>> {
        let mut out = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getElementAt writes a valid pointer on success (rc==0).
        let rc = unsafe { ffi::blpapi_Element_getElementAt(self.ptr, out.as_mut_ptr(), i) };
        (rc == 0).then(|| Element::new(unsafe { out.assume_init() }))
    }

    /// Element name.
    #[inline(always)]
    pub fn name(&self) -> Name {
        // SAFETY: blpapi_Element_name returns a valid Name pointer.
        // We duplicate it to get an owned Name.
        let ptr = unsafe { ffi::blpapi_Element_name(self.ptr) };
        // SAFETY: blpapi_Name_duplicate returns a valid pointer
        unsafe { Name::from_raw(NonNull::new(ffi::blpapi_Name_duplicate(ptr)).unwrap()) }
    }

    /// Data type.
    #[inline(always)]
    pub fn datatype(&self) -> DataType {
        // SAFETY: blpapi_Element_datatype returns a valid type code.
        DataType::from_raw(unsafe { ffi::blpapi_Element_datatype(self.ptr) })
    }

    /// Number of values (for arrays).
    #[inline(always)]
    pub fn len(&self) -> usize {
        // SAFETY: blpapi_Element_numValues returns a valid count.
        unsafe { ffi::blpapi_Element_numValues(self.ptr) }
    }

    /// Check if element is empty (has no values).
    #[inline(always)]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Number of child elements (for sequences).
    #[inline(always)]
    pub fn num_children(&self) -> usize {
        // SAFETY: blpapi_Element_numElements returns a valid count.
        unsafe { ffi::blpapi_Element_numElements(self.ptr) }
    }

    /// Check if element is null.
    #[inline(always)]
    pub fn is_null(&self) -> bool {
        // SAFETY: blpapi_Element_isNull returns 0 (false) or non-zero (true).
        unsafe { ffi::blpapi_Element_isNull(self.ptr) != 0 }
    }

    /// Check if element is an array.
    #[inline(always)]
    pub fn is_array(&self) -> bool {
        // SAFETY: blpapi_Element_isArray returns 0 (false) or non-zero (true).
        unsafe { ffi::blpapi_Element_isArray(self.ptr) != 0 }
    }

    // ===== Typed Getters =====
    // All getters return None for:
    // - Null values
    // - Type mismatch
    // - Index out of bounds
    // We do NOT distinguish between these cases (per plan).

    /// Get float64 value at index.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    ///
    /// # Performance
    /// Target: < 30ns per call.
    #[must_use]
    #[inline(always)]
    pub fn get_f64(&self, i: usize) -> Option<f64> {
        let mut v = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getValueAsFloat64 writes to the pointer on success.
        // MaybeUninit avoids zero-init overhead.
        let rc = unsafe { ffi::blpapi_Element_getValueAsFloat64(self.ptr, v.as_mut_ptr(), i) };
        (rc == 0).then(|| unsafe { v.assume_init() })
    }

    /// Get int64 value at index.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[must_use]
    #[inline(always)]
    pub fn get_i64(&self, i: usize) -> Option<i64> {
        let mut v = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getValueAsInt64 writes to the pointer on success.
        let rc = unsafe { ffi::blpapi_Element_getValueAsInt64(self.ptr, v.as_mut_ptr(), i) };
        (rc == 0).then(|| unsafe { v.assume_init() })
    }

    /// Get int32 value at index.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[must_use]
    #[inline(always)]
    pub fn get_i32(&self, i: usize) -> Option<i32> {
        let mut v = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getValueAsInt32 writes to the pointer on success.
        let rc = unsafe { ffi::blpapi_Element_getValueAsInt32(self.ptr, v.as_mut_ptr(), i) };
        (rc == 0).then(|| unsafe { v.assume_init() })
    }

    /// Get bool value at index.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[must_use]
    #[inline(always)]
    pub fn get_bool(&self, i: usize) -> Option<bool> {
        let mut v = MaybeUninit::<i32>::uninit();
        // SAFETY: blpapi_Element_getValueAsBool writes to the pointer on success.
        // Bloomberg returns 0 for false, non-zero for true.
        let rc = unsafe { ffi::blpapi_Element_getValueAsBool(self.ptr, v.as_mut_ptr(), i) };
        (rc == 0).then(|| unsafe { v.assume_init() != 0 })
    }

    /// Get string value at index. Returns reference to Bloomberg's internal buffer.
    ///
    /// **Zero allocation**: Returns a borrowed reference, no copy.
    ///
    /// Returns `None` if null, type mismatch, out of bounds, or invalid UTF-8.
    ///
    /// # Performance
    /// Target: < 50ns per call.
    #[must_use]
    #[inline(always)]
    pub fn get_str(&self, i: usize) -> Option<&'a str> {
        let mut ptr = MaybeUninit::<*const i8>::uninit();
        // SAFETY: blpapi_Element_getValueAsString writes a C string pointer on success.
        // The string is valid for the lifetime of the message/event.
        let rc = unsafe { ffi::blpapi_Element_getValueAsString(self.ptr, ptr.as_mut_ptr(), i) };
        if rc == 0 {
            let ptr = unsafe { ptr.assume_init() };
            if ptr.is_null() {
                return None;
            }
            // SAFETY: Bloomberg guarantees null-terminated strings.
            // Use checked UTF-8 conversion in case of legacy encodings.
            unsafe { CStr::from_ptr(ptr) }.to_str().ok()
        } else {
            None
        }
    }

    /// Get datetime value at index.
    ///
    /// Returns raw datetime struct (not converted to timestamp yet).
    /// Use `get_timestamp_us()` for direct microsecond conversion.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[must_use]
    #[inline(always)]
    pub fn get_datetime(&self, i: usize) -> Option<HighPrecisionDatetime> {
        let mut v = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getValueAsHighPrecisionDatetime writes the datetime struct on success.
        let rc = unsafe {
            ffi::blpapi_Element_getValueAsHighPrecisionDatetime(self.ptr, v.as_mut_ptr(), i)
        };
        (rc == 0).then(|| HighPrecisionDatetime(unsafe { v.assume_init() }))
    }

    /// Get datetime as microseconds since Unix epoch.
    ///
    /// Convenience method combining `get_datetime()` + `to_micros()`.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[must_use]
    #[inline(always)]
    pub fn get_timestamp_us(&self, i: usize) -> Option<i64> {
        self.get_datetime(i).map(|dt| dt.to_micros())
    }

    /// Get child element as value (for element arrays).
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[inline(always)]
    pub fn get_element(&self, i: usize) -> Option<Element<'a>> {
        let mut out = MaybeUninit::uninit();
        // SAFETY: blpapi_Element_getValueAsElement writes a valid pointer on success.
        let rc = unsafe { ffi::blpapi_Element_getValueAsElement(self.ptr, out.as_mut_ptr(), i) };
        (rc == 0).then(|| Element::new(unsafe { out.assume_init() }))
    }

    /// Iterator over child elements.
    ///
    /// Use for sequences (structured types with named children).
    #[inline]
    pub fn children(&'a self) -> impl Iterator<Item = Element<'a>> + 'a {
        let n = self.num_children();
        (0..n).filter_map(move |i| self.get_at(i))
    }

    /// Iterator over array values as elements.
    ///
    /// Use for arrays of complex types.
    #[inline]
    pub fn values(&'a self) -> impl Iterator<Item = Element<'a>> + 'a {
        let n = self.len();
        (0..n).filter_map(move |i| self.get_element(i))
    }

    /// Get raw pointer for FFI calls.
    #[inline(always)]
    pub(crate) fn as_ptr(&self) -> *mut ffi::blpapi_Element_t {
        self.ptr
    }

    // ===== Dynamic Value Extraction =====

    /// Get value at index with dynamic type dispatch.
    ///
    /// This method examines the element's `datatype()` and extracts the value
    /// into the appropriate `Value` variant. Use this when you don't know the
    /// type at compile time, or when building generic extraction code.
    ///
    /// # Boolean Coercion
    ///
    /// Bloomberg often stores boolean fields as `Char` type with 'Y'/'N' values.
    /// This method automatically coerces such fields to `Value::Bool`:
    /// - 'Y' → `Bool(true)`
    /// - 'N' → `Bool(false)`
    /// - Other char values → `Byte(value)`
    ///
    /// If you need the raw char/byte value without coercion, use `get_i32(i)`
    /// and cast to `u8`.
    ///
    /// # Complex Types
    ///
    /// For `Sequence` and `Choice` types, this returns `Value::Null`. Use the
    /// `children()` or `values()` iterators to access nested elements.
    ///
    /// # Performance
    ///
    /// This is slightly slower than direct typed getters (`get_f64`, `get_str`, etc.)
    /// due to the type dispatch, but avoids JSON serialization entirely.
    /// For hot paths with known types, prefer the direct getters.
    ///
    /// # Example
    ///
    /// ```ignore
    /// use xbbg_core::{Element, Value};
    ///
    /// fn extract_field(elem: &Element) -> Option<f64> {
    ///     match elem.get_value(0)? {
    ///         Value::Float64(v) => Some(v),
    ///         Value::Int64(v) => Some(v as f64),
    ///         Value::Int32(v) => Some(v as f64),
    ///         _ => None,
    ///     }
    /// }
    /// ```
    #[inline]
    pub fn get_value(&self, i: usize) -> Option<crate::Value<'a>> {
        use crate::{DataType, Value};

        // Check null first
        if self.is_null() {
            return Some(Value::Null);
        }

        // Check bounds
        if i >= self.len() {
            return None;
        }

        // Dispatch based on datatype
        match self.datatype() {
            DataType::Bool => self.get_bool(i).map(Value::Bool),
            DataType::Char | DataType::Byte => {
                // Bloomberg often stores boolean fields as Char ('Y'/'N').
                // Try get_bool() first - Bloomberg's API coerces 'Y'/'N' to true/false.
                if let Some(b) = self.get_bool(i) {
                    return Some(Value::Bool(b));
                }
                // Fall back to byte if get_bool() fails
                self.get_i32(i).map(|v| Value::Byte(v as u8))
            }
            DataType::Int32 => self.get_i32(i).map(Value::Int32),
            DataType::Int64 => self.get_i64(i).map(Value::Int64),
            DataType::Float32 | DataType::Float64 | DataType::Decimal => {
                self.get_f64(i).map(Value::Float64)
            }
            DataType::String => self.get_str(i).map(Value::String),
            DataType::Date => {
                // Extract as datetime, convert to days since epoch
                self.get_datetime(i).map(|dt| {
                    let micros = dt.to_micros();
                    let days = (micros / 86_400_000_000) as i32;
                    Value::Date32(days)
                })
            }
            DataType::Time => {
                // Time-only: store as microseconds from midnight
                self.get_datetime(i).map(|dt| {
                    // to_micros returns full timestamp, we want just the time portion
                    // For time-only, the date parts are typically zeroed
                    Value::TimestampMicros(dt.to_micros())
                })
            }
            DataType::Datetime => self
                .get_datetime(i)
                .map(|dt| Value::TimestampMicros(dt.to_micros())),
            DataType::Enumeration => {
                // Enums are stored as strings in Bloomberg
                self.get_str(i).map(Value::Enum)
            }
            DataType::Sequence | DataType::Choice => {
                // Complex types - return null, caller should iterate children
                Some(Value::Null)
            }
            DataType::ByteArray | DataType::CorrelationId => {
                // Not commonly used, return null
                Some(Value::Null)
            }
        }
    }

    /// Get date value as days since Unix epoch (for Arrow Date32).
    ///
    /// Extracts a Date element and converts to days since 1970-01-01.
    /// This is the format Arrow uses for Date32 columns.
    ///
    /// Returns `None` if null, type mismatch, or out of bounds.
    #[must_use]
    #[inline(always)]
    pub fn get_date32(&self, i: usize) -> Option<i32> {
        self.get_datetime(i).map(|dt| {
            let micros = dt.to_micros();
            (micros / 86_400_000_000) as i32
        })
    }
}

impl<'a> std::fmt::Debug for Element<'a> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Element")
            .field("name", &self.name().as_str())
            .field("datatype", &self.datatype())
            .field("len", &self.len())
            .field("is_null", &self.is_null())
            .finish()
    }
}

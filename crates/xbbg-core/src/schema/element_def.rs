//! Schema element definition wrapper.

use std::ffi::CStr;
use std::ptr::NonNull;

use crate::ffi;
use crate::name::Name;

use super::type_def::SchemaTypeDefinition;
use super::SchemaStatus;

/// Definition of a schema element (field).
///
/// Defines a field within a schema type, including its name, type,
/// cardinality (min/max values), and metadata.
///
/// This is a non-owning view into session-managed data.
#[derive(Clone, Copy)]
pub struct SchemaElementDefinition {
    ptr: *mut ffi::blpapi_SchemaElementDefinition_t,
}

// SAFETY: SchemaElementDefinition is a read-only view into session data
unsafe impl Send for SchemaElementDefinition {}
unsafe impl Sync for SchemaElementDefinition {}

impl SchemaElementDefinition {
    /// Create from raw pointer without null check.
    ///
    /// # Safety
    /// The pointer must be valid and non-null.
    pub(crate) unsafe fn from_raw_unchecked(
        ptr: *mut ffi::blpapi_SchemaElementDefinition_t,
    ) -> Self {
        debug_assert!(!ptr.is_null());
        Self { ptr }
    }

    /// Create from raw pointer with null check.
    pub(crate) fn from_raw(ptr: *mut ffi::blpapi_SchemaElementDefinition_t) -> Option<Self> {
        if ptr.is_null() {
            None
        } else {
            Some(Self { ptr })
        }
    }

    /// Get the element name.
    ///
    /// Returns the Name identifying this element within its containing type.
    /// Returns None if the name pointer is null.
    pub fn name(&self) -> Option<Name> {
        unsafe {
            let name_ptr = ffi::blpapi_SchemaElementDefinition_name(self.ptr);
            NonNull::new(name_ptr).map(|ptr| Name::from_raw(ptr))
        }
    }

    /// Get the element name as a string.
    ///
    /// Returns an empty string if the name is not available.
    pub fn name_str(&self) -> &str {
        unsafe {
            let name_ptr = ffi::blpapi_SchemaElementDefinition_name(self.ptr);
            if name_ptr.is_null() {
                return "";
            }
            let str_ptr = ffi::blpapi_Name_string(name_ptr);
            if str_ptr.is_null() {
                return "";
            }
            CStr::from_ptr(str_ptr).to_str().unwrap_or("")
        }
    }

    /// Get a human-readable description of this element.
    pub fn description(&self) -> &str {
        unsafe {
            let desc_ptr = ffi::blpapi_SchemaElementDefinition_description(self.ptr);
            if desc_ptr.is_null() {
                return "";
            }
            CStr::from_ptr(desc_ptr).to_str().unwrap_or("")
        }
    }

    /// Get the type definition for this element's values.
    pub fn type_definition(&self) -> SchemaTypeDefinition {
        unsafe {
            let type_ptr = ffi::blpapi_SchemaElementDefinition_type(self.ptr);
            SchemaTypeDefinition::from_raw_unchecked(type_ptr)
        }
    }

    /// Get the minimum number of values for this element.
    ///
    /// - 0 means the element is optional
    /// - 1+ means the element is required
    pub fn min_values(&self) -> usize {
        unsafe { ffi::blpapi_SchemaElementDefinition_minValues(self.ptr) }
    }

    /// Get the maximum number of values for this element.
    ///
    /// - 1 means a single value
    /// - > 1 means an array
    /// - UNBOUNDED means no upper limit
    pub fn max_values(&self) -> usize {
        unsafe { ffi::blpapi_SchemaElementDefinition_maxValues(self.ptr) }
    }

    /// Check if this element is optional (min_values == 0).
    pub fn is_optional(&self) -> bool {
        self.min_values() == 0
    }

    /// Check if this element is required (min_values >= 1).
    pub fn is_required(&self) -> bool {
        self.min_values() >= 1
    }

    /// Check if this element is an array (max_values > 1).
    pub fn is_array(&self) -> bool {
        self.max_values() > 1
    }

    /// Check if this element is a single value (min == max == 1).
    pub fn is_single_value(&self) -> bool {
        self.min_values() == 1 && self.max_values() == 1
    }

    /// Get the deprecation status of this element.
    #[cfg(feature = "live")]
    pub fn status(&self) -> SchemaStatus {
        unsafe {
            let status = ffi::blpapi_SchemaElementDefinition_status(self.ptr);
            SchemaStatus::from_raw(status)
        }
    }

    /// Get the deprecation status of this element.
    ///
    /// Note: In mock mode, always returns Active.
    #[cfg(not(feature = "live"))]
    pub fn status(&self) -> SchemaStatus {
        SchemaStatus::Active
    }
}

impl std::fmt::Debug for SchemaElementDefinition {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SchemaElementDefinition")
            .field("name", &self.name_str())
            .field("min_values", &self.min_values())
            .field("max_values", &self.max_values())
            .finish()
    }
}

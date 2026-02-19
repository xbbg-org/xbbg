//! Schema type definition wrapper.

use std::ffi::CStr;
use std::ptr::NonNull;

use crate::datatype::DataType;
use crate::ffi;
use crate::name::Name;

use super::constant::ConstantList;
use super::element_def::SchemaElementDefinition;
use super::SchemaStatus;

/// Definition of a schema type.
///
/// Types can be:
/// - **Simple**: Atomic types like Int32, String, Float64, etc.
/// - **Complex**: Sequence or choice of named child elements
/// - **Enumeration**: A set of named constant values
///
/// This is a non-owning view into session-managed data.
#[derive(Clone, Copy)]
pub struct SchemaTypeDefinition {
    ptr: *mut ffi::blpapi_SchemaTypeDefinition_t,
}

// SAFETY: SchemaTypeDefinition is a read-only view into session data
unsafe impl Send for SchemaTypeDefinition {}
unsafe impl Sync for SchemaTypeDefinition {}

impl SchemaTypeDefinition {
    /// Create from raw pointer without null check.
    ///
    /// # Safety
    /// The pointer must be valid and non-null.
    pub(crate) unsafe fn from_raw_unchecked(ptr: *mut ffi::blpapi_SchemaTypeDefinition_t) -> Self {
        debug_assert!(!ptr.is_null());
        Self { ptr }
    }

    /// Get the type name.
    ///
    /// Returns None if the name pointer is null.
    pub fn name(&self) -> Option<Name> {
        unsafe {
            let name_ptr = ffi::blpapi_SchemaTypeDefinition_name(self.ptr);
            NonNull::new(name_ptr).map(|ptr| Name::from_raw(ptr))
        }
    }

    /// Get the type name as a string.
    ///
    /// Returns an empty string if the name is not available.
    pub fn name_str(&self) -> &str {
        unsafe {
            let name_ptr = ffi::blpapi_SchemaTypeDefinition_name(self.ptr);
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

    /// Get a human-readable description of this type.
    pub fn description(&self) -> &str {
        unsafe {
            let desc_ptr = ffi::blpapi_SchemaTypeDefinition_description(self.ptr);
            if desc_ptr.is_null() {
                return "";
            }
            CStr::from_ptr(desc_ptr).to_str().unwrap_or("")
        }
    }

    /// Get the underlying data type.
    ///
    /// For simple types, this is the actual data type (Int32, String, etc.).
    /// For complex types, this returns SEQUENCE or CHOICE.
    pub fn datatype(&self) -> DataType {
        unsafe {
            let dt = ffi::blpapi_SchemaTypeDefinition_datatype(self.ptr);
            DataType::from_raw(dt)
        }
    }

    /// Check if this is a complex type (sequence or choice).
    ///
    /// Complex types contain child element definitions.
    pub fn is_complex_type(&self) -> bool {
        unsafe { ffi::blpapi_SchemaTypeDefinition_isComplexType(self.ptr) != 0 }
    }

    /// Check if this is a simple type.
    ///
    /// Simple types are atomic values (Int32, String, Float64, etc.).
    pub fn is_simple_type(&self) -> bool {
        unsafe { ffi::blpapi_SchemaTypeDefinition_isSimpleType(self.ptr) != 0 }
    }

    /// Check if this is an enumeration type.
    ///
    /// Enumeration types have a fixed set of valid constant values.
    pub fn is_enumeration_type(&self) -> bool {
        unsafe { ffi::blpapi_SchemaTypeDefinition_isEnumerationType(self.ptr) != 0 }
    }

    /// Get the number of child element definitions.
    ///
    /// Returns 0 for non-complex types.
    pub fn num_element_definitions(&self) -> usize {
        unsafe { ffi::blpapi_SchemaTypeDefinition_numElementDefinitions(self.ptr) }
    }

    /// Get a child element definition by index.
    ///
    /// # Arguments
    /// * `index` - The index of the element (0 to num_element_definitions - 1)
    ///
    /// # Returns
    /// The element definition, or None if index is out of bounds.
    pub fn get_element_definition(&self, index: usize) -> Option<SchemaElementDefinition> {
        if index >= self.num_element_definitions() {
            return None;
        }

        unsafe {
            let elem_ptr = ffi::blpapi_SchemaTypeDefinition_getElementDefinitionAt(self.ptr, index);
            SchemaElementDefinition::from_raw(elem_ptr)
        }
    }

    /// Get the enumeration values for this type.
    ///
    /// # Panics
    /// Panics if this is not an enumeration type. Check `is_enumeration_type()` first.
    pub fn enumeration(&self) -> Option<ConstantList> {
        if !self.is_enumeration_type() {
            return None;
        }

        unsafe {
            let list_ptr = ffi::blpapi_SchemaTypeDefinition_enumeration(self.ptr);
            ConstantList::from_raw(list_ptr)
        }
    }

    /// Iterate over all child element definitions.
    pub fn element_definitions(&self) -> ElementDefinitionIter {
        ElementDefinitionIter {
            type_def: *self,
            index: 0,
            count: self.num_element_definitions(),
        }
    }

    /// Get the deprecation status of this type.
    #[cfg(feature = "live")]
    pub fn status(&self) -> SchemaStatus {
        unsafe {
            let status = ffi::blpapi_SchemaTypeDefinition_status(self.ptr);
            SchemaStatus::from_raw(status)
        }
    }

    /// Get the deprecation status of this type.
    ///
    /// Note: In mock mode, always returns Active.
    #[cfg(not(feature = "live"))]
    pub fn status(&self) -> SchemaStatus {
        SchemaStatus::Active
    }
}

impl std::fmt::Debug for SchemaTypeDefinition {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SchemaTypeDefinition")
            .field("name", &self.name_str())
            .field("datatype", &self.datatype())
            .field("is_complex", &self.is_complex_type())
            .field("is_enumeration", &self.is_enumeration_type())
            .field("num_elements", &self.num_element_definitions())
            .finish()
    }
}

/// Iterator over element definitions in a complex type.
pub struct ElementDefinitionIter {
    type_def: SchemaTypeDefinition,
    index: usize,
    count: usize,
}

impl Iterator for ElementDefinitionIter {
    type Item = SchemaElementDefinition;

    fn next(&mut self) -> Option<Self::Item> {
        if self.index >= self.count {
            return None;
        }

        let elem = self.type_def.get_element_definition(self.index);
        self.index += 1;
        elem
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let remaining = self.count - self.index;
        (remaining, Some(remaining))
    }
}

impl ExactSizeIterator for ElementDefinitionIter {}

//! Schema enumeration constant types.

use std::ffi::CStr;
use std::ptr::NonNull;

use crate::ffi;
use crate::name::Name;

/// A list of enumeration constants.
///
/// Used to represent valid values for enumeration-type schema elements.
///
/// This is a non-owning view into session-managed data.
#[derive(Clone, Copy)]
pub struct ConstantList {
    ptr: *mut ffi::blpapi_ConstantList_t,
}

// SAFETY: ConstantList is a read-only view into session data
unsafe impl Send for ConstantList {}
unsafe impl Sync for ConstantList {}

impl ConstantList {
    /// Create from raw pointer with null check.
    pub(crate) fn from_raw(ptr: *mut ffi::blpapi_ConstantList_t) -> Option<Self> {
        if ptr.is_null() {
            None
        } else {
            Some(Self { ptr })
        }
    }

    /// Get the number of constants in this list.
    pub fn len(&self) -> usize {
        let count = unsafe { ffi::blpapi_ConstantList_numConstants(self.ptr) };
        count.max(0) as usize
    }

    /// Check if the list is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Get a constant by index.
    ///
    /// # Arguments
    /// * `index` - The index of the constant (0 to len - 1)
    pub fn get(&self, index: usize) -> Option<Constant> {
        if index >= self.len() {
            return None;
        }

        unsafe {
            let const_ptr = ffi::blpapi_ConstantList_getConstantAt(self.ptr, index);
            Constant::from_raw(const_ptr)
        }
    }

    /// Iterate over all constants in this list.
    pub fn iter(&self) -> ConstantIter {
        ConstantIter {
            list: *self,
            index: 0,
            count: self.len(),
        }
    }
}

impl std::fmt::Debug for ConstantList {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ConstantList")
            .field("len", &self.len())
            .finish()
    }
}

impl IntoIterator for &ConstantList {
    type Item = Constant;
    type IntoIter = ConstantIter;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

/// A single enumeration constant value.
///
/// Represents one valid value in an enumeration type.
///
/// This is a non-owning view into session-managed data.
#[derive(Clone, Copy)]
pub struct Constant {
    ptr: *mut ffi::blpapi_Constant_t,
}

// SAFETY: Constant is a read-only view into session data
unsafe impl Send for Constant {}
unsafe impl Sync for Constant {}

impl Constant {
    /// Create from raw pointer with null check.
    pub(crate) fn from_raw(ptr: *mut ffi::blpapi_Constant_t) -> Option<Self> {
        if ptr.is_null() {
            None
        } else {
            Some(Self { ptr })
        }
    }

    /// Get the constant's symbolic name.
    ///
    /// Returns None if the name pointer is null.
    pub fn name(&self) -> Option<Name> {
        unsafe {
            let name_ptr = ffi::blpapi_Constant_name(self.ptr);
            NonNull::new(name_ptr).map(|ptr| Name::from_raw(ptr))
        }
    }

    /// Get the constant's name as a string.
    ///
    /// Returns an empty string if the name is not available.
    pub fn name_str(&self) -> &str {
        unsafe {
            let name_ptr = ffi::blpapi_Constant_name(self.ptr);
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

    /// Get a human-readable description of this constant.
    pub fn description(&self) -> &str {
        unsafe {
            let desc_ptr = ffi::blpapi_Constant_description(self.ptr);
            if desc_ptr.is_null() {
                return "";
            }
            CStr::from_ptr(desc_ptr).to_str().unwrap_or("")
        }
    }
}

impl std::fmt::Debug for Constant {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Constant")
            .field("name", &self.name_str())
            .finish()
    }
}

impl std::fmt::Display for Constant {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.name_str())
    }
}

/// Iterator over constants in a ConstantList.
pub struct ConstantIter {
    list: ConstantList,
    index: usize,
    count: usize,
}

impl Iterator for ConstantIter {
    type Item = Constant;

    fn next(&mut self) -> Option<Self::Item> {
        if self.index >= self.count {
            return None;
        }

        let constant = self.list.get(self.index);
        self.index += 1;
        constant
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let remaining = self.count - self.index;
        (remaining, Some(remaining))
    }
}

impl ExactSizeIterator for ConstantIter {}

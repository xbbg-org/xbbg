use crate::errors::{BlpError, Result};
use crate::name::Name;

#[derive(Copy, Clone, Debug, Eq, PartialEq)]
pub enum DataType {
    Bool,
    Char,
    Byte,
    Int32,
    Int64,
    Float32,
    Float64,
    String,
    Date,
    Time,
    Decimal,
    Datetime,
    Enumeration,
    ByteArray,
    Name,
    Sequence,
    Choice,
    CorrelationId,
    Unknown(i32),
}

impl From<i32> for DataType {
    fn from(v: i32) -> Self {
        match v {
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_BOOL as i32 => DataType::Bool,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_CHAR as i32 => DataType::Char,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_BYTE as i32 => DataType::Byte,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_INT32 as i32 => DataType::Int32,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_INT64 as i32 => DataType::Int64,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_FLOAT32 as i32 => DataType::Float32,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_FLOAT64 as i32 => DataType::Float64,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_STRING as i32 => DataType::String,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_BYTEARRAY as i32 => DataType::ByteArray,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_DATE as i32 => DataType::Date,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_TIME as i32 => DataType::Time,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_DECIMAL as i32 => DataType::Decimal,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_DATETIME as i32 => DataType::Datetime,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_ENUMERATION as i32 => DataType::Enumeration,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_SEQUENCE as i32 => DataType::Sequence,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_CHOICE as i32 => DataType::Choice,
            x if x == blpapi_sys::blpapi_DataType_t_BLPAPI_DATATYPE_CORRELATION_ID as i32 => DataType::CorrelationId,
            other => DataType::Unknown(other as i32),
        }
    }
}

pub struct SchemaElementDefinition {
    ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t,
}

unsafe impl Send for SchemaElementDefinition {}
unsafe impl Sync for SchemaElementDefinition {}

impl SchemaElementDefinition {
    pub(crate) fn from_raw(ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t) -> Result<Self> {
        if ptr.is_null() {
            return Err(BlpError::Internal { detail: "null schema element definition".into() });
        }
        Ok(Self { ptr })
    }

    pub fn name(&self) -> Name {
        let out = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_name(self.ptr) };
        Name::from_raw(out)
    }

    pub fn description(&self) -> &str {
        let c = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_description(self.ptr) };
        if c.is_null() { "" } else { unsafe { std::ffi::CStr::from_ptr(c) }.to_str().unwrap_or_default() }
    }

    pub fn data_type(&self) -> DataType {
        let type_ptr = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_type(self.ptr) };
        let t = unsafe { blpapi_sys::blpapi_SchemaTypeDefinition_datatype(type_ptr) };
        DataType::from(t)
    }

    pub fn is_array(&self) -> bool {
        let maxv = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_maxValues(self.ptr) };
        maxv > 1
    }

    pub fn is_optional(&self) -> bool {
        let minv = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_minValues(self.ptr) };
        minv == 0
    }

    pub fn num_children(&self) -> usize {
        let type_ptr = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_type(self.ptr) };
        unsafe { blpapi_sys::blpapi_SchemaTypeDefinition_numElementDefinitions(type_ptr) as usize }
    }

    pub fn child_at(&self, i: usize) -> Result<SchemaElementDefinition> {
        let type_ptr = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_type(self.ptr) };
        let out = unsafe { blpapi_sys::blpapi_SchemaTypeDefinition_getElementDefinitionAt(type_ptr, i) };
        if out.is_null() {
            return Err(BlpError::Internal { detail: "getElementDefinitionAt null".into() });
        }
        Self::from_raw(out)
    }

    pub fn child_by_name(&self, name: &Name) -> Option<SchemaElementDefinition> {
        let type_ptr = unsafe { blpapi_sys::blpapi_SchemaElementDefinition_type(self.ptr) };
        let out = unsafe { blpapi_sys::blpapi_SchemaTypeDefinition_getElementDefinition(type_ptr, std::ptr::null(), name.as_raw()) };
        if out.is_null() {
            None
        } else {
            Self::from_raw(out).ok()
        }
    }
}

pub struct Operation {
    pub(crate) ptr: *mut blpapi_sys::blpapi_Operation_t,
}

unsafe impl Send for Operation {}
unsafe impl Sync for Operation {}

impl Operation {
    pub fn name(&self) -> &str {
        let c = unsafe { blpapi_sys::blpapi_Operation_name(self.ptr) };
        if c.is_null() { "" } else { unsafe { std::ffi::CStr::from_ptr(c) }.to_str().unwrap_or_default() }
    }

    pub fn description(&self) -> &str {
        let c = unsafe { blpapi_sys::blpapi_Operation_description(self.ptr) };
        if c.is_null() { "" } else { unsafe { std::ffi::CStr::from_ptr(c) }.to_str().unwrap_or_default() }
    }

    pub fn request_definition(&self) -> Result<SchemaElementDefinition> {
        let mut def_ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t = std::ptr::null_mut();
        let rc = unsafe { blpapi_sys::blpapi_Operation_requestDefinition(self.ptr, &mut def_ptr) };
        if rc != 0 || def_ptr.is_null() {
            return Err(BlpError::Internal { detail: format!("requestDefinition rc={rc}") });
        }
        SchemaElementDefinition::from_raw(def_ptr)
    }

    pub fn num_response_definitions(&self) -> usize {
        unsafe { blpapi_sys::blpapi_Operation_numResponseDefinitions(self.ptr) as usize }
    }

    pub fn response_definition(&self, index: usize) -> Result<SchemaElementDefinition> {
        let mut def_ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t = std::ptr::null_mut();
        let rc = unsafe { blpapi_sys::blpapi_Operation_responseDefinition(self.ptr, &mut def_ptr, index) };
        if rc != 0 || def_ptr.is_null() {
            return Err(BlpError::Internal { detail: format!("responseDefinition rc={rc}") });
        }
        SchemaElementDefinition::from_raw(def_ptr)
    }

    pub fn response_definition_by_name(&self, name: &Name) -> Result<SchemaElementDefinition> {
        let mut def_ptr: *mut blpapi_sys::blpapi_SchemaElementDefinition_t = std::ptr::null_mut();
        let rc = unsafe { blpapi_sys::blpapi_Operation_responseDefinitionFromName(self.ptr, &mut def_ptr, name.as_raw()) };
        if rc != 0 || def_ptr.is_null() {
            return Err(BlpError::Internal { detail: format!("responseDefinitionFromName rc={rc}") });
        }
        SchemaElementDefinition::from_raw(def_ptr)
    }
}


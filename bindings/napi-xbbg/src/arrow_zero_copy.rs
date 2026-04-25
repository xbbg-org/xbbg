use std::sync::Arc;

use arrow::array::{
    Array, BooleanArray, Date32Array, Float64Array, Int32Array, Int64Array, NullArray, StringArray,
    Time64MicrosecondArray, TimestampMicrosecondArray,
};
use arrow::buffer::Buffer as ArrowBuffer;
use arrow::datatypes::{DataType, TimeUnit};
use arrow::record_batch::RecordBatch;
use napi::bindgen_prelude::{
    Buffer, BufferSlice, Env, JsObjectValue, JsValue, Object, ToNapiValue,
};
use napi::{Error, Result, Status};

pub struct NativeArrowBatch {
    num_rows: usize,
    columns: Vec<NativeArrowColumn>,
}

struct NativeArrowColumn {
    batch: Arc<RecordBatch>,
    name: String,
    arrow_type: NativeArrowType,
    nullable: bool,
    length: usize,
    null_count: usize,
    data: Option<ArrowBuffer>,
    offsets: Option<ArrowBuffer>,
    null_bitmap: Option<ArrowBuffer>,
}

#[derive(Clone)]
enum NativeArrowType {
    Bool,
    Date32,
    Float64,
    Int32,
    Int64,
    Null,
    Time64Microsecond,
    TimestampMicrosecond { timezone: Option<String> },
    Utf8,
}

struct ExternalBufferOwner {
    _batch: Arc<RecordBatch>,
    _buffer: ArrowBuffer,
}

impl NativeArrowBatch {
    pub fn from_record_batch(batch: RecordBatch) -> Result<Self> {
        let unsupported = unsupported_columns(&batch);
        if !unsupported.is_empty() {
            return Err(Error::new(
                Status::GenericFailure,
                format!(
                    "zero-copy subscription transfer does not support this Arrow schema. \
                     Unsupported columns: {}. Supported subscription column types are: \
                     bool, date32, float64, int32, int64, null, time64[us], timestamp[us], utf8. \
                     Sliced Arrow arrays are not supported.",
                    unsupported.join("; ")
                ),
            ));
        }

        let batch = Arc::new(batch);
        let schema = batch.schema();
        let columns = batch
            .columns()
            .iter()
            .enumerate()
            .map(|(idx, array)| {
                let field = schema.field(idx);
                NativeArrowColumn::from_array(
                    batch.clone(),
                    field.name().clone(),
                    field.is_nullable(),
                    array.as_ref(),
                )
            })
            .collect();

        Ok(Self {
            num_rows: batch.num_rows(),
            columns,
        })
    }
}

impl NativeArrowColumn {
    fn from_array(
        batch: Arc<RecordBatch>,
        name: String,
        nullable: bool,
        array: &dyn Array,
    ) -> Self {
        let null_bitmap = array.nulls().map(|nulls| nulls.inner().inner().clone());
        let null_count = array.null_count();
        let length = array.len();

        match array.data_type() {
            DataType::Boolean => {
                let values = array
                    .as_any()
                    .downcast_ref::<BooleanArray>()
                    .expect("supported boolean array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Bool,
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Date32 => {
                let values = array
                    .as_any()
                    .downcast_ref::<Date32Array>()
                    .expect("supported date32 array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Date32,
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Float64 => {
                let values = array
                    .as_any()
                    .downcast_ref::<Float64Array>()
                    .expect("supported float64 array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Float64,
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Int32 => {
                let values = array
                    .as_any()
                    .downcast_ref::<Int32Array>()
                    .expect("supported int32 array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Int32,
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Int64 => {
                let values = array
                    .as_any()
                    .downcast_ref::<Int64Array>()
                    .expect("supported int64 array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Int64,
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Null => {
                let _ = array
                    .as_any()
                    .downcast_ref::<NullArray>()
                    .expect("supported null array");
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Null,
                    nullable,
                    length,
                    null_count,
                    data: None,
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Time64(TimeUnit::Microsecond) => {
                let values = array
                    .as_any()
                    .downcast_ref::<Time64MicrosecondArray>()
                    .expect("supported time64[us] array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Time64Microsecond,
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Timestamp(TimeUnit::Microsecond, timezone) => {
                let values = array
                    .as_any()
                    .downcast_ref::<TimestampMicrosecondArray>()
                    .expect("supported timestamp[us] array")
                    .values()
                    .inner()
                    .clone();
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::TimestampMicrosecond {
                        timezone: timezone.as_ref().map(|tz| tz.to_string()),
                    },
                    nullable,
                    length,
                    null_count,
                    data: Some(values),
                    offsets: None,
                    null_bitmap,
                }
            }
            DataType::Utf8 => {
                let array = array
                    .as_any()
                    .downcast_ref::<StringArray>()
                    .expect("supported utf8 array");
                Self {
                    batch,
                    name,
                    arrow_type: NativeArrowType::Utf8,
                    nullable,
                    length,
                    null_count,
                    data: Some(array.values().clone()),
                    offsets: Some(array.offsets().inner().inner().clone()),
                    null_bitmap,
                }
            }
            _ => unreachable!("unsupported array checked before conversion"),
        }
    }
}

impl NativeArrowType {
    fn label(&self) -> &'static str {
        match self {
            Self::Bool => "bool",
            Self::Date32 => "date32",
            Self::Float64 => "float64",
            Self::Int32 => "int32",
            Self::Int64 => "int64",
            Self::Null => "null",
            Self::Time64Microsecond => "time64_us",
            Self::TimestampMicrosecond { .. } => "timestamp_us",
            Self::Utf8 => "utf8",
        }
    }

    fn timezone(&self) -> Option<&str> {
        match self {
            Self::TimestampMicrosecond { timezone } => timezone.as_deref(),
            _ => None,
        }
    }
}

fn unsupported_columns(batch: &RecordBatch) -> Vec<String> {
    let schema = batch.schema();
    batch
        .columns()
        .iter()
        .enumerate()
        .filter_map(|(idx, array)| {
            unsupported_array_reason(array.as_ref()).map(|reason| {
                let field = schema.field(idx);
                format!("#{idx} '{}' ({reason})", field.name())
            })
        })
        .collect()
}

fn unsupported_array_reason(array: &dyn Array) -> Option<String> {
    if array.offset() != 0 {
        return Some(format!(
            "sliced array offset={} type={:?}",
            array.offset(),
            array.data_type()
        ));
    }

    match array.data_type() {
        DataType::Boolean
        | DataType::Date32
        | DataType::Float64
        | DataType::Int32
        | DataType::Int64
        | DataType::Null
        | DataType::Time64(TimeUnit::Microsecond)
        | DataType::Timestamp(TimeUnit::Microsecond, _)
        | DataType::Utf8 => None,
        data_type => Some(format!("unsupported type={data_type:?}")),
    }
}

fn external_buffer(env: &Env, batch: Arc<RecordBatch>, buffer: ArrowBuffer) -> Result<Buffer> {
    let len = buffer.len();
    if len == 0 {
        return Ok(Buffer::from(Vec::<u8>::new()));
    }

    let data = buffer.as_ptr() as *mut u8;
    let owner = ExternalBufferOwner {
        _batch: batch,
        _buffer: buffer,
    };
    let slice = unsafe {
        BufferSlice::from_external(env, data, len, owner, |_env, _owner| {
            // Dropping the owner releases the Arrow buffer/RecordBatch once V8 is done.
        })?
    };
    slice.into_buffer(env)
}

impl ToNapiValue for NativeArrowBatch {
    unsafe fn to_napi_value(
        env: napi::sys::napi_env,
        value: Self,
    ) -> Result<napi::sys::napi_value> {
        let env = Env::from_raw(env);
        let mut obj = Object::new(&env)?;
        obj.set_named_property("kind", "zeroCopy")?;
        obj.set_named_property("numRows", value.num_rows as u32)?;
        obj.set_named_property("columns", value.columns)?;
        Ok(obj.raw())
    }
}

impl ToNapiValue for NativeArrowColumn {
    unsafe fn to_napi_value(
        env: napi::sys::napi_env,
        value: Self,
    ) -> Result<napi::sys::napi_value> {
        let env = Env::from_raw(env);
        let mut obj = Object::new(&env)?;
        obj.set_named_property("name", value.name)?;
        obj.set_named_property("type", value.arrow_type.label())?;
        obj.set_named_property("nullable", value.nullable)?;
        obj.set_named_property("length", value.length as u32)?;
        obj.set_named_property("nullCount", value.null_count as u32)?;
        if let Some(timezone) = value.arrow_type.timezone() {
            obj.set_named_property("timezone", timezone)?;
        }
        if let Some(buffer) = value.data {
            obj.set_named_property(
                "data",
                external_buffer(&env, value.batch.clone(), buffer).map_err(|e| {
                    Error::new(
                        Status::GenericFailure,
                        format!("failed to expose Arrow data buffer: {e}"),
                    )
                })?,
            )?;
        }
        if let Some(buffer) = value.offsets {
            obj.set_named_property(
                "offsets",
                external_buffer(&env, value.batch.clone(), buffer).map_err(|e| {
                    Error::new(
                        Status::GenericFailure,
                        format!("failed to expose Arrow offsets buffer: {e}"),
                    )
                })?,
            )?;
        }
        if let Some(buffer) = value.null_bitmap {
            obj.set_named_property(
                "nullBitmap",
                external_buffer(&env, value.batch, buffer).map_err(|e| {
                    Error::new(
                        Status::GenericFailure,
                        format!("failed to expose Arrow null bitmap: {e}"),
                    )
                })?,
            )?;
        }
        Ok(obj.raw())
    }
}

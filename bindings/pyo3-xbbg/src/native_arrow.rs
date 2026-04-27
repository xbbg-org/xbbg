use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_void};
use std::ptr::addr_of;
use std::sync::Arc;

use arrow_array::ffi::{FFI_ArrowArray, FFI_ArrowSchema};
use arrow_array::ffi_stream::FFI_ArrowArrayStream;
use arrow_array::{
    Array, ArrayRef, BooleanArray, Date32Array, Float32Array, Float64Array, Int32Array, Int64Array,
    RecordBatch, RecordBatchOptions, StringArray, StructArray, Time64MicrosecondArray,
    TimestampMicrosecondArray, TimestampMillisecondArray, UInt32Array, UInt64Array,
};
use arrow_cast::{can_cast_types, cast};
use arrow_ord::sort::{lexsort_to_indices, SortColumn, SortOptions};
use arrow_schema::{ArrowError, DataType, Field, FieldRef, Schema, SchemaRef, TimeUnit};
use arrow_select::concat::concat_batches;
use arrow_select::filter::filter_record_batch;
use arrow_select::take::take_record_batch;
use chrono::{DateTime, Datelike, NaiveDate, Timelike};
use pyo3::exceptions::{PyIndexError, PyKeyError, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{
    PyAny, PyCapsule, PyDate, PyDateTime, PyDict, PyIterator, PyList, PyTime, PyTuple, PyType,
    PyTzInfo,
};
use pyo3::IntoPyObjectExt;
#[cfg(feature = "stub-gen")]
use pyo3_stub_gen::derive::*;

const ARROW_SCHEMA_CAPSULE_NAME: &CStr = c"arrow_schema";
const ENOMEM: i32 = 12;
const EIO: i32 = 5;
const EINVAL: i32 = 22;
const ENOSYS: i32 = 78;

fn import_schema_pycapsule<'py>(
    capsule: &'py Bound<'py, PyCapsule>,
) -> PyResult<&'py FFI_ArrowSchema> {
    let schema_ptr = capsule
        .pointer_checked(Some(ARROW_SCHEMA_CAPSULE_NAME))?
        .cast::<FFI_ArrowSchema>();
    Ok(unsafe { schema_ptr.as_ref() })
}

fn to_schema_pycapsule<'py>(
    py: Python<'py>,
    field: impl TryInto<FFI_ArrowSchema, Error = ArrowError>,
) -> PyResult<Bound<'py, PyCapsule>> {
    let ffi_schema = field
        .try_into()
        .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema export failed: {e}")))?;
    let capsule_name = CString::new("arrow_schema").expect("static capsule name is valid");
    PyCapsule::new(py, ffi_schema, Some(capsule_name))
}

fn to_array_pycapsules<'py>(
    py: Python<'py>,
    field: FieldRef,
    array: &dyn Array,
    requested_schema: Option<Bound<'py, PyCapsule>>,
) -> PyResult<Bound<'py, PyTuple>> {
    let (array_data, field) = if let Some(capsule) = requested_schema {
        let schema_ptr = import_schema_pycapsule(&capsule)?;
        let output_field = Arc::new(
            Field::try_from(schema_ptr)
                .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema import failed: {e}")))?
                .with_metadata(field.metadata().clone()),
        );

        if can_cast_types(field.data_type(), output_field.data_type()) {
            let casted_array = cast(array, output_field.data_type())
                .map_err(|e| PyRuntimeError::new_err(format!("Arrow array cast failed: {e}")))?;
            (casted_array.to_data(), output_field)
        } else {
            (array.to_data(), field)
        }
    } else {
        (array.to_data(), field)
    };

    let ffi_schema = FFI_ArrowSchema::try_from(&field)
        .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema export failed: {e}")))?;
    let ffi_array = FFI_ArrowArray::new(&array_data);
    let schema_capsule_name = CString::new("arrow_schema").expect("static capsule name is valid");
    let array_capsule_name = CString::new("arrow_array").expect("static capsule name is valid");

    let schema_capsule = PyCapsule::new(py, ffi_schema, Some(schema_capsule_name))?;
    let array_capsule = PyCapsule::new(py, ffi_array, Some(array_capsule_name))?;
    PyTuple::new(py, [schema_capsule, array_capsule])
}

trait ArrayReader: Iterator<Item = Result<ArrayRef, ArrowError>> {
    fn field(&self) -> FieldRef;
}

impl<R: ArrayReader + ?Sized> ArrayReader for Box<R> {
    fn field(&self) -> FieldRef {
        self.as_ref().field()
    }
}

struct ArrayIterator<I>
where
    I: IntoIterator<Item = Result<ArrayRef, ArrowError>>,
{
    inner: I::IntoIter,
    inner_field: FieldRef,
}

impl<I> ArrayIterator<I>
where
    I: IntoIterator<Item = Result<ArrayRef, ArrowError>>,
{
    fn new(iter: I, field: FieldRef) -> Self {
        Self {
            inner: iter.into_iter(),
            inner_field: field,
        }
    }
}

impl<I> Iterator for ArrayIterator<I>
where
    I: IntoIterator<Item = Result<ArrayRef, ArrowError>>,
{
    type Item = I::Item;

    fn next(&mut self) -> Option<Self::Item> {
        self.inner.next()
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        self.inner.size_hint()
    }
}

impl<I> ArrayReader for ArrayIterator<I>
where
    I: IntoIterator<Item = Result<ArrayRef, ArrowError>>,
{
    fn field(&self) -> FieldRef {
        self.inner_field.clone()
    }
}

struct ArrayStreamPrivateData {
    array_reader: Box<dyn ArrayReader + Send>,
    last_error: Option<CString>,
}

fn new_stream(array_reader: Box<dyn ArrayReader + Send>) -> FFI_ArrowArrayStream {
    let private_data = Box::new(ArrayStreamPrivateData {
        array_reader,
        last_error: None,
    });

    FFI_ArrowArrayStream {
        get_schema: Some(get_schema),
        get_next: Some(get_next),
        get_last_error: Some(get_last_error),
        release: Some(release_stream),
        private_data: Box::into_raw(private_data) as *mut c_void,
    }
}

unsafe extern "C" fn release_stream(stream: *mut FFI_ArrowArrayStream) {
    if stream.is_null() {
        return;
    }
    let stream = unsafe { &mut *stream };
    stream.get_schema = None;
    stream.get_next = None;
    stream.get_last_error = None;

    let private_data = unsafe { Box::from_raw(stream.private_data as *mut ArrayStreamPrivateData) };
    drop(private_data);

    stream.release = None;
}

unsafe extern "C" fn get_schema(
    stream: *mut FFI_ArrowArrayStream,
    schema: *mut FFI_ArrowSchema,
) -> c_int {
    ExportedArrayStream { stream }.get_schema(schema)
}

unsafe extern "C" fn get_next(
    stream: *mut FFI_ArrowArrayStream,
    array: *mut FFI_ArrowArray,
) -> c_int {
    ExportedArrayStream { stream }.get_next(array)
}

unsafe extern "C" fn get_last_error(stream: *mut FFI_ArrowArrayStream) -> *const c_char {
    let mut ffi_stream = ExportedArrayStream { stream };
    match ffi_stream.get_last_error() {
        Some(err_string) => err_string.as_ptr(),
        None => std::ptr::null(),
    }
}

struct ExportedArrayStream {
    stream: *mut FFI_ArrowArrayStream,
}

impl ExportedArrayStream {
    fn get_private_data(&mut self) -> &mut ArrayStreamPrivateData {
        unsafe { &mut *((*self.stream).private_data as *mut ArrayStreamPrivateData) }
    }

    fn get_schema(&mut self, out: *mut FFI_ArrowSchema) -> i32 {
        let private_data = self.get_private_data();
        let reader = &private_data.array_reader;

        match FFI_ArrowSchema::try_from(reader.field().as_ref()) {
            Ok(schema) => {
                unsafe { std::ptr::copy(addr_of!(schema), out, 1) };
                std::mem::forget(schema);
                0
            }
            Err(err) => {
                private_data.last_error = Some(
                    CString::new(err.to_string())
                        .expect("error strings must not contain NUL bytes"),
                );
                get_error_code(&err)
            }
        }
    }

    fn get_next(&mut self, out: *mut FFI_ArrowArray) -> i32 {
        let private_data = self.get_private_data();
        let reader = &mut private_data.array_reader;

        match reader.next() {
            None => {
                unsafe { std::ptr::write(out, FFI_ArrowArray::empty()) }
                0
            }
            Some(Ok(array)) => {
                let array = FFI_ArrowArray::new(&array.to_data());
                unsafe { std::ptr::write_unaligned(out, array) };
                0
            }
            Some(Err(err)) => {
                private_data.last_error = Some(
                    CString::new(err.to_string())
                        .expect("error strings must not contain NUL bytes"),
                );
                get_error_code(&err)
            }
        }
    }

    fn get_last_error(&mut self) -> Option<&CString> {
        self.get_private_data().last_error.as_ref()
    }
}

fn get_error_code(err: &ArrowError) -> i32 {
    match err {
        ArrowError::NotYetImplemented(_) => ENOSYS,
        ArrowError::MemoryError(_) => ENOMEM,
        ArrowError::IoError(_, _) => EIO,
        _ => EINVAL,
    }
}

fn to_stream_pycapsule<'py>(
    py: Python<'py>,
    mut array_reader: Box<dyn ArrayReader + Send>,
    requested_schema: Option<Bound<'py, PyCapsule>>,
) -> PyResult<Bound<'py, PyCapsule>> {
    if let Some(capsule) = requested_schema {
        let schema_ptr = import_schema_pycapsule(&capsule)?;
        let existing_field = array_reader.field();
        let output_field = Arc::new(
            Field::try_from(schema_ptr)
                .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema import failed: {e}")))?
                .with_metadata(existing_field.metadata().clone()),
        );
        let iter_field = output_field.clone();

        if can_cast_types(existing_field.data_type(), output_field.data_type()) {
            let array_iter = array_reader.map(move |array| {
                let out = cast(array?.as_ref(), output_field.data_type())?;
                Ok(out)
            });
            array_reader = Box::new(ArrayIterator::new(array_iter, iter_field));
        }
    }

    let ffi_stream = new_stream(array_reader);
    let stream_capsule_name =
        CString::new("arrow_array_stream").expect("static capsule name is valid");
    PyCapsule::new(py, ffi_stream, Some(stream_capsule_name))
}

#[derive(Clone, Debug)]
enum CellValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Date(NaiveDate),
    Text(String),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum InferredKind {
    Bool,
    Int,
    Float,
    Date,
    Text,
}

fn py_value_to_cell(value: &Bound<'_, PyAny>) -> PyResult<CellValue> {
    if value.is_none() {
        return Ok(CellValue::Null);
    }
    if let Ok(v) = value.extract::<bool>() {
        return Ok(CellValue::Bool(v));
    }
    if let Ok(v) = value.extract::<i64>() {
        return Ok(CellValue::Int(v));
    }
    if let Ok(v) = value.extract::<f64>() {
        return Ok(CellValue::Float(v));
    }
    if let Ok(v) = value.extract::<String>() {
        return Ok(CellValue::Text(v));
    }
    if let Ok(isoformat) = value.getattr("isoformat") {
        if let Ok(text) = isoformat.call0()?.extract::<String>() {
            if text.len() == 10 {
                if let Ok(date) = NaiveDate::parse_from_str(&text, "%Y-%m-%d") {
                    return Ok(CellValue::Date(date));
                }
            }
            return Ok(CellValue::Text(text));
        }
    }
    Ok(CellValue::Text(value.str()?.to_string()))
}

fn merge_kind(current: Option<InferredKind>, value: &CellValue) -> Option<InferredKind> {
    let next = match value {
        CellValue::Null => return current,
        CellValue::Bool(_) => InferredKind::Bool,
        CellValue::Int(_) => InferredKind::Int,
        CellValue::Float(_) => InferredKind::Float,
        CellValue::Date(_) => InferredKind::Date,
        CellValue::Text(_) => InferredKind::Text,
    };
    Some(match (current, next) {
        (None, kind) => kind,
        (Some(InferredKind::Text), _) | (_, InferredKind::Text) => InferredKind::Text,
        (Some(InferredKind::Date), InferredKind::Date) => InferredKind::Date,
        (Some(InferredKind::Date), _) | (_, InferredKind::Date) => InferredKind::Text,
        (
            Some(InferredKind::Float),
            InferredKind::Int | InferredKind::Bool | InferredKind::Float,
        )
        | (Some(InferredKind::Int | InferredKind::Bool), InferredKind::Float) => {
            InferredKind::Float
        }
        (Some(InferredKind::Int), InferredKind::Bool | InferredKind::Int)
        | (Some(InferredKind::Bool), InferredKind::Int) => InferredKind::Int,
        (Some(InferredKind::Bool), InferredKind::Bool) => InferredKind::Bool,
    })
}

fn cell_to_string(value: &CellValue) -> Option<String> {
    match value {
        CellValue::Null => None,
        CellValue::Bool(v) => Some(v.to_string()),
        CellValue::Int(v) => Some(v.to_string()),
        CellValue::Float(v) => Some(v.to_string()),
        CellValue::Date(v) => Some(v.to_string()),
        CellValue::Text(v) => Some(v.clone()),
    }
}

fn build_array(name: &str, cells: &[CellValue]) -> (Field, ArrayRef) {
    let kind = cells
        .iter()
        .fold(None, merge_kind)
        .unwrap_or(InferredKind::Text);
    match kind {
        InferredKind::Bool => {
            let values: Vec<Option<bool>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Bool(v) => Some(*v),
                    CellValue::Int(v) => Some(*v != 0),
                    CellValue::Float(v) => Some(*v != 0.0),
                    CellValue::Date(_) | CellValue::Text(_) => None,
                })
                .collect();
            (
                Field::new(name, DataType::Boolean, true),
                Arc::new(BooleanArray::from(values)),
            )
        }
        InferredKind::Int => {
            let values: Vec<Option<i64>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Bool(v) => Some(i64::from(*v)),
                    CellValue::Int(v) => Some(*v),
                    CellValue::Float(v) => Some(*v as i64),
                    CellValue::Date(_) | CellValue::Text(_) => None,
                })
                .collect();
            (
                Field::new(name, DataType::Int64, true),
                Arc::new(Int64Array::from(values)),
            )
        }
        InferredKind::Float => {
            let values: Vec<Option<f64>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Bool(v) => Some(if *v { 1.0 } else { 0.0 }),
                    CellValue::Int(v) => Some(*v as f64),
                    CellValue::Float(v) => Some(*v),
                    CellValue::Date(_) | CellValue::Text(_) => None,
                })
                .collect();
            (
                Field::new(name, DataType::Float64, true),
                Arc::new(Float64Array::from(values)),
            )
        }
        InferredKind::Date => {
            let epoch = NaiveDate::from_ymd_opt(1970, 1, 1).expect("valid epoch date");
            let values: Vec<Option<i32>> = cells
                .iter()
                .map(|cell| match cell {
                    CellValue::Null => None,
                    CellValue::Date(v) => Some(v.signed_duration_since(epoch).num_days() as i32),
                    _ => None,
                })
                .collect();
            (
                Field::new(name, DataType::Date32, true),
                Arc::new(Date32Array::from(values)),
            )
        }
        InferredKind::Text => {
            let values: Vec<Option<String>> = cells.iter().map(cell_to_string).collect();
            (
                Field::new(name, DataType::Utf8, true),
                Arc::new(StringArray::from(values)),
            )
        }
    }
}

fn empty_batch_from_columns(columns: Vec<String>) -> PyResult<RecordBatch> {
    let fields = columns
        .iter()
        .map(|name| Field::new(name, DataType::Utf8, true))
        .collect::<Vec<_>>();
    let arrays = columns
        .iter()
        .map(|_| Arc::new(StringArray::from(Vec::<Option<String>>::new())) as ArrayRef)
        .collect::<Vec<_>>();
    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

fn rows_to_batch(rows: &Bound<'_, PyAny>) -> PyResult<RecordBatch> {
    let iterator = PyIterator::from_object(rows)?;
    let mut column_names: Vec<String> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    let mut raw_rows: Vec<HashMap<String, CellValue>> = Vec::new();

    for item in iterator {
        let item = item?;
        let dict = item.cast::<PyDict>().map_err(|_| {
            PyTypeError::new_err("ArrowTable.from_pylist expects an iterable of dict rows")
        })?;
        let mut row = HashMap::new();
        for (key, value) in dict.iter() {
            let name = key.extract::<String>()?;
            if seen.insert(name.clone()) {
                column_names.push(name.clone());
            }
            row.insert(name, py_value_to_cell(&value)?);
        }
        raw_rows.push(row);
    }

    if raw_rows.is_empty() {
        return RecordBatch::try_new(Arc::new(Schema::empty()), vec![])
            .map_err(|e| PyValueError::new_err(e.to_string()));
    }

    let mut fields = Vec::with_capacity(column_names.len());
    let mut arrays = Vec::with_capacity(column_names.len());
    for name in &column_names {
        let cells = raw_rows
            .iter()
            .map(|row| row.get(name).cloned().unwrap_or(CellValue::Null))
            .collect::<Vec<_>>();
        let (field, array) = build_array(name, &cells);
        fields.push(field);
        arrays.push(array);
    }

    RecordBatch::try_new(Arc::new(Schema::new(fields)), arrays)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

fn py_sequence_to_cells(values: &Bound<'_, PyAny>) -> PyResult<Vec<CellValue>> {
    let iterator = PyIterator::from_object(values)?;
    iterator
        .map(|item| item.and_then(|value| py_value_to_cell(&value)))
        .collect()
}

fn split_cells_for_batches(
    cells: &[CellValue],
    batches: &[RecordBatch],
) -> PyResult<Vec<Vec<CellValue>>> {
    let expected = batches.iter().map(RecordBatch::num_rows).sum::<usize>();
    if cells.len() != expected {
        return Err(PyValueError::new_err(format!(
            "column length {} does not match table row count {}",
            cells.len(),
            expected
        )));
    }
    let mut offset = 0;
    Ok(batches
        .iter()
        .map(|batch| {
            let end = offset + batch.num_rows();
            let chunk = cells[offset..end].to_vec();
            offset = end;
            chunk
        })
        .collect())
}

fn date32_to_py(py: Python<'_>, days: i32) -> PyResult<Py<PyAny>> {
    let Some(epoch) = NaiveDate::from_ymd_opt(1970, 1, 1) else {
        return Ok(py.None());
    };
    let Some(date) = epoch.checked_add_signed(chrono::Duration::days(days as i64)) else {
        return Ok(py.None());
    };
    Ok(
        PyDate::new(py, date.year(), date.month() as u8, date.day() as u8)?
            .into_any()
            .unbind(),
    )
}

fn timestamp_to_py(py: Python<'_>, micros: i64) -> PyResult<Py<PyAny>> {
    let Some(dt) = DateTime::from_timestamp_micros(micros) else {
        return Ok(py.None());
    };
    let utc = PyTzInfo::utc(py)?;
    Ok(PyDateTime::new(
        py,
        dt.year(),
        dt.month() as u8,
        dt.day() as u8,
        dt.hour() as u8,
        dt.minute() as u8,
        dt.second() as u8,
        dt.timestamp_subsec_micros(),
        Some(&utc),
    )?
    .into_any()
    .unbind())
}

fn time64_micros_to_py(py: Python<'_>, micros: i64) -> PyResult<Py<PyAny>> {
    if !(0..86_400_000_000).contains(&micros) {
        return Ok(py.None());
    }
    let seconds = micros / 1_000_000;
    let microsecond = (micros % 1_000_000) as u32;
    let hour = (seconds / 3_600) as u8;
    let minute = ((seconds % 3_600) / 60) as u8;
    let second = (seconds % 60) as u8;
    Ok(PyTime::new(py, hour, minute, second, microsecond, None)?
        .into_any()
        .unbind())
}

fn scalar_to_py(py: Python<'_>, array: &dyn Array, row: usize) -> PyResult<Py<PyAny>> {
    if array.is_null(row) {
        return Ok(py.None());
    }
    match array.data_type() {
        DataType::Boolean => array
            .as_any()
            .downcast_ref::<BooleanArray>()
            .expect("BooleanArray")
            .value(row)
            .into_py_any(py),
        DataType::Int32 => array
            .as_any()
            .downcast_ref::<Int32Array>()
            .expect("Int32Array")
            .value(row)
            .into_py_any(py),
        DataType::Int64 => array
            .as_any()
            .downcast_ref::<Int64Array>()
            .expect("Int64Array")
            .value(row)
            .into_py_any(py),
        DataType::UInt32 => array
            .as_any()
            .downcast_ref::<UInt32Array>()
            .expect("UInt32Array")
            .value(row)
            .into_py_any(py),
        DataType::UInt64 => array
            .as_any()
            .downcast_ref::<UInt64Array>()
            .expect("UInt64Array")
            .value(row)
            .into_py_any(py),
        DataType::Float32 => (array
            .as_any()
            .downcast_ref::<Float32Array>()
            .expect("Float32Array")
            .value(row) as f64)
            .into_py_any(py),
        DataType::Float64 => array
            .as_any()
            .downcast_ref::<Float64Array>()
            .expect("Float64Array")
            .value(row)
            .into_py_any(py),
        DataType::Utf8 => array
            .as_any()
            .downcast_ref::<StringArray>()
            .expect("StringArray")
            .value(row)
            .into_py_any(py),
        DataType::Date32 => date32_to_py(
            py,
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        ),
        DataType::Timestamp(TimeUnit::Microsecond, _) => timestamp_to_py(
            py,
            array
                .as_any()
                .downcast_ref::<TimestampMicrosecondArray>()
                .expect("TimestampMicrosecondArray")
                .value(row),
        ),
        DataType::Time64(TimeUnit::Microsecond) => time64_micros_to_py(
            py,
            array
                .as_any()
                .downcast_ref::<Time64MicrosecondArray>()
                .expect("Time64MicrosecondArray")
                .value(row),
        ),
        DataType::Timestamp(TimeUnit::Millisecond, _) => timestamp_to_py(
            py,
            array
                .as_any()
                .downcast_ref::<TimestampMillisecondArray>()
                .expect("TimestampMillisecondArray")
                .value(row)
                * 1_000,
        ),
        _ => format!("{array:?}").into_py_any(py),
    }
}

fn batch_to_pylist(py: Python<'_>, batch: &RecordBatch) -> PyResult<Vec<Py<PyAny>>> {
    let mut rows = Vec::with_capacity(batch.num_rows());
    for row_idx in 0..batch.num_rows() {
        let dict = PyDict::new(py);
        for (column_idx, field) in batch.schema().fields().iter().enumerate() {
            dict.set_item(
                field.name(),
                scalar_to_py(py, batch.column(column_idx).as_ref(), row_idx)?,
            )?;
        }
        rows.push(dict.into_any().unbind());
    }
    Ok(rows)
}

fn table_to_pylist(py: Python<'_>, batches: &[RecordBatch]) -> PyResult<Vec<Py<PyAny>>> {
    let mut rows = Vec::new();
    for batch in batches {
        rows.extend(batch_to_pylist(py, batch)?);
    }
    Ok(rows)
}

fn column_values(py: Python<'_>, batch: &RecordBatch, idx: usize) -> PyResult<Vec<Py<PyAny>>> {
    let array = batch.column(idx);
    (0..array.len())
        .map(|row| scalar_to_py(py, array.as_ref(), row))
        .collect()
}

fn table_column_values(
    py: Python<'_>,
    batches: &[RecordBatch],
    idx: usize,
    capacity: usize,
) -> PyResult<Vec<Py<PyAny>>> {
    let mut values = Vec::with_capacity(capacity);
    for batch in batches {
        values.extend(column_values(py, batch, idx)?);
    }
    Ok(values)
}

fn select_batch(batch: &RecordBatch, names: &[String]) -> PyResult<RecordBatch> {
    let schema = batch.schema();
    let mut fields = Vec::with_capacity(names.len());
    let mut columns = Vec::with_capacity(names.len());
    for name in names {
        let idx = schema
            .index_of(name)
            .map_err(|_| PyKeyError::new_err(format!("unknown column: {name}")))?;
        fields.push(schema.field(idx).clone());
        columns.push(batch.column(idx).clone());
    }
    let projected_schema = Arc::new(Schema::new_with_metadata(fields, schema.metadata().clone()));
    let options = RecordBatchOptions::new().with_row_count(Some(batch.num_rows()));
    RecordBatch::try_new_with_options(projected_schema, columns, &options)
        .map_err(|e| PyValueError::new_err(e.to_string()))
}

fn rename_batch(batch: &RecordBatch, mapping: &HashMap<String, String>) -> PyResult<RecordBatch> {
    let schema = batch.schema();
    let fields = schema
        .fields()
        .iter()
        .map(|field| {
            mapping
                .get(field.name().as_str())
                .map(|new_name| field.as_ref().clone().with_name(new_name))
                .unwrap_or_else(|| field.as_ref().clone())
        })
        .collect::<Vec<_>>();
    RecordBatch::try_new(
        Arc::new(Schema::new_with_metadata(fields, schema.metadata().clone())),
        batch.columns().to_vec(),
    )
    .map_err(|e| PyValueError::new_err(e.to_string()))
}

fn cell_from_array(array: &dyn Array, row: usize) -> CellValue {
    if array.is_null(row) {
        return CellValue::Null;
    }
    match array.data_type() {
        DataType::Boolean => CellValue::Bool(
            array
                .as_any()
                .downcast_ref::<BooleanArray>()
                .expect("BooleanArray")
                .value(row),
        ),
        DataType::Int32 => CellValue::Int(i64::from(
            array
                .as_any()
                .downcast_ref::<Int32Array>()
                .expect("Int32Array")
                .value(row),
        )),
        DataType::Int64 => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<Int64Array>()
                .expect("Int64Array")
                .value(row),
        ),
        DataType::UInt32 => CellValue::Int(i64::from(
            array
                .as_any()
                .downcast_ref::<UInt32Array>()
                .expect("UInt32Array")
                .value(row),
        )),
        DataType::UInt64 => CellValue::Text(
            array
                .as_any()
                .downcast_ref::<UInt64Array>()
                .expect("UInt64Array")
                .value(row)
                .to_string(),
        ),
        DataType::Float32 => CellValue::Float(
            array
                .as_any()
                .downcast_ref::<Float32Array>()
                .expect("Float32Array")
                .value(row) as f64,
        ),
        DataType::Float64 => CellValue::Float(
            array
                .as_any()
                .downcast_ref::<Float64Array>()
                .expect("Float64Array")
                .value(row),
        ),
        DataType::Utf8 => CellValue::Text(
            array
                .as_any()
                .downcast_ref::<StringArray>()
                .expect("StringArray")
                .value(row)
                .to_string(),
        ),
        DataType::Date32 => date_from_days(
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        )
        .map(CellValue::Date)
        .unwrap_or(CellValue::Null),
        DataType::Time64(TimeUnit::Microsecond) => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<Time64MicrosecondArray>()
                .expect("Time64MicrosecondArray")
                .value(row),
        ),
        DataType::Timestamp(TimeUnit::Microsecond, _) => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<TimestampMicrosecondArray>()
                .expect("TimestampMicrosecondArray")
                .value(row),
        ),
        DataType::Timestamp(TimeUnit::Millisecond, _) => CellValue::Int(
            array
                .as_any()
                .downcast_ref::<TimestampMillisecondArray>()
                .expect("TimestampMillisecondArray")
                .value(row),
        ),
        _ => CellValue::Text(format!("{array:?}")),
    }
}

fn cell_has_value(cell: &CellValue) -> bool {
    match cell {
        CellValue::Null => false,
        CellValue::Text(text) => !text.is_empty(),
        _ => true,
    }
}

fn date_from_days(days: i32) -> Option<NaiveDate> {
    NaiveDate::from_ymd_opt(1970, 1, 1)?.checked_add_signed(chrono::Duration::days(days as i64))
}

fn date_from_cell(cell: &CellValue) -> Option<NaiveDate> {
    match cell {
        CellValue::Date(value) => Some(*value),
        CellValue::Text(value) if value.len() >= 10 => {
            NaiveDate::parse_from_str(&value[..10], "%Y-%m-%d").ok()
        }
        CellValue::Text(value) if value.len() == 8 => {
            NaiveDate::parse_from_str(value, "%Y%m%d").ok()
        }
        _ => None,
    }
}

fn date_from_array(array: &dyn Array, row: usize) -> Option<NaiveDate> {
    if array.is_null(row) {
        return None;
    }
    match array.data_type() {
        DataType::Date32 => date_from_days(
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        ),
        _ => date_from_cell(&cell_from_array(array, row)),
    }
}

fn period_label(array: &dyn Array, row: usize, periodicity: Option<&str>) -> String {
    let Some(parsed) = date_from_array(array, row) else {
        return cell_to_string(&cell_from_array(array, row)).unwrap_or_default();
    };
    match periodicity.unwrap_or("DAILY").to_ascii_uppercase().as_str() {
        "YEARLY" | "Y" => format!("{:04}", parsed.year()),
        "SEMI_ANNUALLY" | "SEMIANNUALLY" | "S" => {
            let half = if parsed.month() <= 6 { 1 } else { 2 };
            format!("{:04}H{}", parsed.year(), half)
        }
        "QUARTERLY" | "Q" => {
            let quarter = ((parsed.month() - 1) / 3) + 1;
            format!("{:04}Q{}", parsed.year(), quarter)
        }
        "MONTHLY" | "M" => format!("{:04}-{:02}", parsed.year(), parsed.month()),
        "WEEKLY" | "W" => {
            let iso = parsed.iso_week();
            format!("{:04}-W{:02}", iso.year(), iso.week())
        }
        _ => parsed.to_string(),
    }
}

fn table_with_cells_column(
    table: &ArrowTable,
    index: usize,
    name: &str,
    cells: &[CellValue],
    replace: bool,
    force_text: bool,
) -> PyResult<ArrowTable> {
    let max_index = table.num_columns();
    if replace {
        if index >= max_index {
            return Err(PyIndexError::new_err("column index out of range"));
        }
    } else if index > max_index {
        return Err(PyIndexError::new_err("column index out of range"));
    }
    let chunks = split_cells_for_batches(cells, &table.batches)?;
    let mut out = Vec::with_capacity(table.batches.len());
    for (batch, chunk) in table.batches.iter().zip(chunks.iter()) {
        let (field, array) = if force_text {
            let values: Vec<Option<String>> = chunk.iter().map(cell_to_string).collect();
            (
                Field::new(name, DataType::Utf8, true),
                Arc::new(StringArray::from(values)) as ArrayRef,
            )
        } else {
            build_array(name, chunk)
        };
        let mut fields = batch
            .schema()
            .fields()
            .iter()
            .map(|field| field.as_ref().clone())
            .collect::<Vec<_>>();
        let mut columns = batch.columns().to_vec();
        if replace {
            fields[index] = field;
            columns[index] = array;
        } else {
            fields.insert(index, field);
            columns.insert(index, array);
        }
        out.push(
            RecordBatch::try_new(
                Arc::new(Schema::new_with_metadata(
                    fields,
                    batch.schema().metadata().clone(),
                )),
                columns,
            )
            .map_err(|e| PyValueError::new_err(e.to_string()))?,
        );
    }
    ArrowTable::try_new(out)
}

fn parse_bqr_path(path: &str) -> Option<(usize, String)> {
    let start = path.find("tickData[")? + "tickData[".len();
    let rest = &path[start..];
    let end = rest.find(']')?;
    let idx = rest[..end].parse::<usize>().ok()?;
    let after = rest.get(end + 1..)?;
    let field_start = after.strip_prefix('.')?;
    let field = field_start
        .chars()
        .take_while(|ch| ch.is_ascii_alphanumeric() || *ch == '_')
        .collect::<String>();
    if field.is_empty() {
        None
    } else {
        Some((idx, field))
    }
}

fn table_schema(batches: &[RecordBatch]) -> SchemaRef {
    batches
        .first()
        .map(|batch| batch.schema())
        .unwrap_or_else(|| Arc::new(Schema::empty()))
}

fn ensure_compatible_schema(expected: &SchemaRef, batch: &RecordBatch) -> PyResult<()> {
    if batch.schema_ref() != expected {
        return Err(PyValueError::new_err(
            "all batches must have identical schemas",
        ));
    }
    Ok(())
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass)]
#[pyclass(module = "xbbg._core", frozen, skip_from_py_object)]
#[derive(Clone)]
pub struct ArrowField {
    field: FieldRef,
}

#[pymethods]
impl ArrowField {
    #[getter]
    fn name(&self) -> String {
        self.field.name().clone()
    }

    #[getter]
    fn data_type(&self) -> String {
        self.field.data_type().to_string()
    }

    #[getter]
    fn nullable(&self) -> bool {
        self.field.is_nullable()
    }

    fn __repr__(&self) -> String {
        format!(
            "xbbg.ArrowField(name={:?}, data_type={:?}, nullable={})",
            self.field.name(),
            self.field.data_type(),
            self.field.is_nullable()
        )
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass)]
#[pyclass(module = "xbbg._core", frozen, skip_from_py_object)]
#[derive(Clone)]
pub struct ArrowSchema {
    schema: SchemaRef,
}

#[pymethods]
impl ArrowSchema {
    #[getter]
    fn names(&self) -> Vec<String> {
        self.schema
            .fields()
            .iter()
            .map(|field| field.name().clone())
            .collect()
    }

    #[getter]
    fn fields(&self) -> Vec<ArrowField> {
        self.schema
            .fields()
            .iter()
            .map(|field| ArrowField {
                field: field.clone(),
            })
            .collect()
    }

    fn __arrow_c_schema__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyCapsule>> {
        to_schema_pycapsule(py, self.schema.as_ref())
            .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema export failed: {e}")))
    }

    fn __repr__(&self) -> String {
        format!("xbbg.ArrowSchema(names={:?})", self.names())
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass)]
#[pyclass(module = "xbbg._core", frozen, skip_from_py_object)]
pub struct ArrowColumn {
    name: String,
    values: Vec<Py<PyAny>>,
}

#[pymethods]
impl ArrowColumn {
    #[getter]
    fn name(&self) -> String {
        self.name.clone()
    }

    fn to_pylist(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let values = PyList::empty(py);
        for value in &self.values {
            values.append(value.bind(py))?;
        }
        Ok(values.into_any().unbind())
    }

    fn __len__(&self) -> usize {
        self.values.len()
    }

    fn __getitem__(&self, py: Python<'_>, index: isize) -> PyResult<Py<PyAny>> {
        let len = self.values.len() as isize;
        let idx = if index < 0 { len + index } else { index };
        if !(0..len).contains(&idx) {
            return Err(PyIndexError::new_err("column index out of range"));
        }
        Ok(self.values[idx as usize].clone_ref(py))
    }

    fn __repr__(&self) -> String {
        format!(
            "xbbg.ArrowColumn(name={:?}, len={})",
            self.name,
            self.values.len()
        )
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass)]
#[pyclass(module = "xbbg._core", frozen, skip_from_py_object)]
#[derive(Clone)]
pub struct ArrowRecordBatch {
    batch: RecordBatch,
}

impl ArrowRecordBatch {
    pub fn new(batch: RecordBatch) -> Self {
        Self { batch }
    }

    pub(crate) fn batch(&self) -> &RecordBatch {
        &self.batch
    }

    fn to_array_pycapsules<'py>(
        py: Python<'py>,
        record_batch: RecordBatch,
        requested_schema: Option<Bound<'py, PyCapsule>>,
    ) -> PyResult<Bound<'py, pyo3::types::PyTuple>> {
        let field = Field::new_struct("", record_batch.schema_ref().fields().clone(), false)
            .with_metadata(record_batch.schema_ref().metadata().clone());
        let array: ArrayRef = Arc::new(StructArray::from(record_batch));
        to_array_pycapsules(py, field.into(), &array, requested_schema)
            .map_err(|e| PyRuntimeError::new_err(format!("Arrow array export failed: {e}")))
    }
}

#[pymethods]
impl ArrowRecordBatch {
    #[getter]
    fn column_names(&self) -> Vec<String> {
        self.batch
            .schema()
            .fields()
            .iter()
            .map(|field| field.name().clone())
            .collect()
    }

    #[getter]
    fn num_rows(&self) -> usize {
        self.batch.num_rows()
    }

    #[getter]
    fn num_columns(&self) -> usize {
        self.batch.num_columns()
    }

    #[getter]
    fn schema(&self) -> ArrowSchema {
        ArrowSchema {
            schema: self.batch.schema(),
        }
    }

    #[pyo3(signature = (requested_schema=None))]
    fn __arrow_c_array__<'py>(
        &self,
        py: Python<'py>,
        requested_schema: Option<Bound<'py, PyCapsule>>,
    ) -> PyResult<Bound<'py, pyo3::types::PyTuple>> {
        Self::to_array_pycapsules(py, self.batch.clone(), requested_schema)
    }

    fn __arrow_c_schema__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyCapsule>> {
        to_schema_pycapsule(py, self.batch.schema_ref().as_ref())
            .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema export failed: {e}")))
    }

    fn to_pylist(&self, py: Python<'_>) -> PyResult<Vec<Py<PyAny>>> {
        batch_to_pylist(py, &self.batch)
    }

    fn to_table(&self) -> ArrowTable {
        ArrowTable {
            batches: vec![self.batch.clone()],
            schema: self.batch.schema(),
        }
    }

    fn column(&self, py: Python<'_>, name: &str) -> PyResult<ArrowColumn> {
        let idx = self
            .batch
            .schema()
            .index_of(name)
            .map_err(|_| PyKeyError::new_err(format!("unknown column: {name}")))?;
        Ok(ArrowColumn {
            name: name.to_string(),
            values: column_values(py, &self.batch, idx)?,
        })
    }

    fn get_column(&self, py: Python<'_>, name: &str) -> PyResult<ArrowColumn> {
        self.column(py, name)
    }

    fn __getitem__(&self, py: Python<'_>, name: &str) -> PyResult<ArrowColumn> {
        self.column(py, name)
    }

    fn __len__(&self) -> usize {
        self.batch.num_rows()
    }

    fn __repr__(&self) -> String {
        format!(
            "xbbg.ArrowRecordBatch(num_rows={}, num_columns={}, columns={:?})",
            self.batch.num_rows(),
            self.batch.num_columns(),
            self.column_names()
        )
    }
}

#[cfg_attr(feature = "stub-gen", gen_stub_pyclass)]
#[pyclass(module = "xbbg._core", frozen, skip_from_py_object)]
#[derive(Clone)]
pub struct ArrowTable {
    batches: Vec<RecordBatch>,
    schema: SchemaRef,
}

impl ArrowTable {
    pub fn try_new(batches: Vec<RecordBatch>) -> PyResult<Self> {
        let schema = table_schema(&batches);
        for batch in &batches {
            ensure_compatible_schema(&schema, batch)?;
        }
        Ok(Self { batches, schema })
    }

    fn to_stream_pycapsule<'py>(
        py: Python<'py>,
        batches: Vec<RecordBatch>,
        schema: SchemaRef,
        requested_schema: Option<Bound<'py, PyCapsule>>,
    ) -> PyResult<Bound<'py, PyCapsule>> {
        let fields = schema.fields();
        let array_reader = batches.into_iter().map(|batch| {
            let arr: ArrayRef = Arc::new(StructArray::from(batch));
            Ok(arr)
        });
        let field =
            Field::new_struct("", fields.clone(), false).with_metadata(schema.metadata().clone());
        let array_reader = Box::new(ArrayIterator::new(array_reader, field.into()));
        to_stream_pycapsule(py, array_reader, requested_schema)
            .map_err(|e| PyRuntimeError::new_err(format!("Arrow stream export failed: {e}")))
    }

    fn combined_batch(&self) -> PyResult<RecordBatch> {
        if self.batches.len() == 1 {
            return Ok(self.batches[0].clone());
        }
        concat_batches(&self.schema, self.batches.iter())
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}

#[pymethods]
impl ArrowTable {
    #[classmethod]
    #[pyo3(signature = (rows, schema=None))]
    fn from_pylist(
        _cls: &Bound<'_, PyType>,
        rows: &Bound<'_, PyAny>,
        schema: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        if schema.is_some() {
            return Err(PyValueError::new_err(
                "ArrowTable.from_pylist schema override is not implemented; pass dict rows with desired keys",
            ));
        }
        Self::try_new(vec![rows_to_batch(rows)?])
    }

    #[classmethod]
    fn empty(_cls: &Bound<'_, PyType>, schema_or_columns: &Bound<'_, PyAny>) -> PyResult<Self> {
        if let Ok(names) = schema_or_columns.extract::<Vec<String>>() {
            return Self::try_new(vec![empty_batch_from_columns(names)?]);
        }
        if let Ok(schema) = schema_or_columns.extract::<PyRef<'_, ArrowSchema>>() {
            return Self::try_new(vec![RecordBatch::new_empty(schema.schema.clone())]);
        }
        Err(PyTypeError::new_err(
            "ArrowTable.empty expects a sequence of column names or ArrowSchema",
        ))
    }

    #[classmethod]
    fn from_batches(_cls: &Bound<'_, PyType>, batches: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut rust_batches = Vec::new();
        for item in PyIterator::from_object(batches)? {
            let item = item?;
            let batch = item.extract::<PyRef<'_, ArrowRecordBatch>>()?;
            rust_batches.push(batch.batch.clone());
        }
        Self::try_new(rust_batches)
    }

    #[classmethod]
    fn concat_tables(_cls: &Bound<'_, PyType>, tables: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut batches = Vec::new();
        let mut expected_schema: Option<SchemaRef> = None;
        for item in PyIterator::from_object(tables)? {
            let item = item?;
            let table = item.extract::<PyRef<'_, ArrowTable>>()?;
            if let Some(schema) = &expected_schema {
                if table.schema != *schema {
                    return Err(PyValueError::new_err(
                        "all tables must have identical schemas",
                    ));
                }
            } else {
                expected_schema = Some(table.schema.clone());
            }
            batches.extend(table.batches.iter().cloned());
        }
        Self::try_new(batches)
    }

    #[getter]
    fn column_names(&self) -> Vec<String> {
        self.schema
            .fields()
            .iter()
            .map(|field| field.name().clone())
            .collect()
    }

    #[getter]
    fn num_rows(&self) -> usize {
        self.batches.iter().map(RecordBatch::num_rows).sum()
    }

    #[getter]
    fn num_columns(&self) -> usize {
        self.schema.fields().len()
    }

    #[getter]
    fn schema(&self) -> ArrowSchema {
        ArrowSchema {
            schema: self.schema.clone(),
        }
    }

    #[pyo3(signature = (requested_schema=None))]
    fn __arrow_c_stream__<'py>(
        &self,
        py: Python<'py>,
        requested_schema: Option<Bound<'py, PyCapsule>>,
    ) -> PyResult<Bound<'py, PyCapsule>> {
        Self::to_stream_pycapsule(
            py,
            self.batches.clone(),
            self.schema.clone(),
            requested_schema,
        )
    }

    fn __arrow_c_schema__<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyCapsule>> {
        to_schema_pycapsule(py, self.schema.as_ref())
            .map_err(|e| PyRuntimeError::new_err(format!("Arrow schema export failed: {e}")))
    }

    fn to_batches(&self, py: Python<'_>) -> PyResult<Vec<Py<ArrowRecordBatch>>> {
        self.batches
            .iter()
            .cloned()
            .map(|batch| Py::new(py, ArrowRecordBatch::new(batch)))
            .collect()
    }

    fn to_pylist(&self, py: Python<'_>) -> PyResult<Vec<Py<PyAny>>> {
        table_to_pylist(py, &self.batches)
    }

    fn column(&self, py: Python<'_>, name: &str) -> PyResult<Py<PyAny>> {
        let idx = self
            .schema
            .index_of(name)
            .map_err(|_| PyKeyError::new_err(format!("unknown column: {name}")))?;
        let values = PyList::empty(py);
        for batch in &self.batches {
            let array = batch.column(idx);
            for row in 0..array.len() {
                values.append(scalar_to_py(py, array.as_ref(), row)?)?;
            }
        }
        Ok(values.into_any().unbind())
    }

    fn __getitem__(&self, py: Python<'_>, name: &str) -> PyResult<ArrowColumn> {
        let idx = self
            .schema
            .index_of(name)
            .map_err(|_| PyKeyError::new_err(format!("unknown column: {name}")))?;
        Ok(ArrowColumn {
            name: name.to_string(),
            values: table_column_values(py, &self.batches, idx, self.num_rows())?,
        })
    }

    fn __len__(&self) -> usize {
        self.num_rows()
    }

    fn get_column(&self, py: Python<'_>, name: &str) -> PyResult<Py<PyAny>> {
        self.column(py, name)
    }

    fn select_columns(&self, names: Vec<String>) -> PyResult<Self> {
        Self::try_new(
            self.batches
                .iter()
                .map(|batch| select_batch(batch, &names))
                .collect::<PyResult<Vec<_>>>()?,
        )
    }

    fn drop_columns(&self, names: Vec<String>) -> PyResult<Self> {
        let drop = names.into_iter().collect::<HashSet<_>>();
        let keep = self
            .column_names()
            .into_iter()
            .filter(|name| !drop.contains(name))
            .collect::<Vec<_>>();
        self.select_columns(keep)
    }

    fn rename_columns(&self, mapping: HashMap<String, String>) -> PyResult<Self> {
        Self::try_new(
            self.batches
                .iter()
                .map(|batch| rename_batch(batch, &mapping))
                .collect::<PyResult<Vec<_>>>()?,
        )
    }

    fn sort_by(&self, sort_keys: Vec<(String, String)>) -> PyResult<Self> {
        if sort_keys.is_empty() || self.num_rows() == 0 {
            return Ok(self.clone());
        }
        let batch = self.combined_batch()?;
        let schema = batch.schema();
        let columns = sort_keys
            .iter()
            .map(|(name, direction)| {
                let idx = schema
                    .index_of(name)
                    .map_err(|_| PyKeyError::new_err(format!("unknown sort column: {name}")))?;
                let descending = matches!(
                    direction.to_ascii_lowercase().as_str(),
                    "desc" | "descending"
                );
                Ok(SortColumn {
                    values: batch.column(idx).clone(),
                    options: Some(SortOptions {
                        descending,
                        nulls_first: false,
                    }),
                })
            })
            .collect::<PyResult<Vec<_>>>()?;
        let indices =
            lexsort_to_indices(&columns, None).map_err(|e| PyValueError::new_err(e.to_string()))?;
        let sorted = take_record_batch(&batch, &indices)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Self::try_new(vec![sorted])
    }

    fn filter_eq(&self, column: &str, value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let needle = py_value_to_cell(value)?;
        let idx = self
            .schema
            .index_of(column)
            .map_err(|_| PyKeyError::new_err(format!("unknown filter column: {column}")))?;
        let filtered = self
            .batches
            .iter()
            .map(|batch| {
                let mask_values = (0..batch.num_rows())
                    .map(|row| cell_matches(batch.column(idx).as_ref(), row, &needle))
                    .collect::<PyResult<Vec<_>>>()?;
                let mask = BooleanArray::from(mask_values);
                filter_record_batch(batch, &mask).map_err(|e| PyValueError::new_err(e.to_string()))
            })
            .collect::<PyResult<Vec<_>>>()?;
        Self::try_new(filtered)
    }

    fn add_column(&self, index: usize, name: &str, values: &Bound<'_, PyAny>) -> PyResult<Self> {
        if index > self.num_columns() {
            return Err(PyIndexError::new_err("column index out of range"));
        }
        let cells = py_sequence_to_cells(values)?;
        let chunks = split_cells_for_batches(&cells, &self.batches)?;
        let mut out = Vec::with_capacity(self.batches.len());
        for (batch, chunk) in self.batches.iter().zip(chunks.iter()) {
            let (field, array) = build_array(name, chunk);
            let mut fields = batch
                .schema()
                .fields()
                .iter()
                .map(|field| field.as_ref().clone())
                .collect::<Vec<_>>();
            let mut columns = batch.columns().to_vec();
            fields.insert(index, field);
            columns.insert(index, array);
            out.push(
                RecordBatch::try_new(
                    Arc::new(Schema::new_with_metadata(
                        fields,
                        batch.schema().metadata().clone(),
                    )),
                    columns,
                )
                .map_err(|e| PyValueError::new_err(e.to_string()))?,
            );
        }
        Self::try_new(out)
    }

    fn set_column(&self, index: usize, name: &str, values: &Bound<'_, PyAny>) -> PyResult<Self> {
        if index >= self.num_columns() {
            return Err(PyIndexError::new_err("column index out of range"));
        }
        let cells = py_sequence_to_cells(values)?;
        let chunks = split_cells_for_batches(&cells, &self.batches)?;
        let mut out = Vec::with_capacity(self.batches.len());
        for (batch, chunk) in self.batches.iter().zip(chunks.iter()) {
            let (field, array) = build_array(name, chunk);
            let mut fields = batch
                .schema()
                .fields()
                .iter()
                .map(|field| field.as_ref().clone())
                .collect::<Vec<_>>();
            let mut columns = batch.columns().to_vec();
            fields[index] = field;
            columns[index] = array;
            out.push(
                RecordBatch::try_new(
                    Arc::new(Schema::new_with_metadata(
                        fields,
                        batch.schema().metadata().clone(),
                    )),
                    columns,
                )
                .map_err(|e| PyValueError::new_err(e.to_string()))?,
            );
        }
        Self::try_new(out)
    }

    fn head(&self, n: usize) -> PyResult<Self> {
        if n == 0 {
            return Self::try_new(vec![RecordBatch::new_empty(self.schema.clone())]);
        }
        if n >= self.num_rows() {
            return Ok(self.clone());
        }
        let mut remaining = n;
        let mut out = Vec::new();
        for batch in &self.batches {
            if remaining == 0 {
                break;
            }
            let take = remaining.min(batch.num_rows());
            out.push(batch.slice(0, take));
            remaining -= take;
        }
        Self::try_new(out)
    }

    fn has_any_value(&self, names: Vec<String>) -> PyResult<bool> {
        for name in names {
            let Ok(idx) = self.schema.index_of(&name) else {
                continue;
            };
            for batch in &self.batches {
                let array = batch.column(idx);
                for row in 0..array.len() {
                    if cell_has_value(&cell_from_array(array.as_ref(), row)) {
                        return Ok(true);
                    }
                }
            }
        }
        Ok(false)
    }

    fn apply_historical_presentation(
        &self,
        show_date: Option<bool>,
        date_format: Option<String>,
        sort: Option<String>,
        periodicity: Option<String>,
    ) -> PyResult<Self> {
        let mut result = self.clone();

        if let Some(sort) = sort {
            if result.schema.index_of("date").is_ok() {
                let date_order = if sort.eq_ignore_ascii_case("DESCENDING") {
                    "descending"
                } else {
                    "ascending"
                };
                let mut sort_keys = Vec::new();
                if result.schema.index_of("ticker").is_ok() {
                    sort_keys.push(("ticker".to_string(), "ascending".to_string()));
                }
                sort_keys.push(("date".to_string(), date_order.to_string()));
                if result.schema.index_of("field").is_ok() {
                    sort_keys.push(("field".to_string(), "ascending".to_string()));
                }
                result = result.sort_by(sort_keys)?;
            }
        }

        if let Some(date_format) = date_format {
            let normalized = date_format.to_ascii_uppercase();
            if matches!(normalized.as_str(), "PERIODIC" | "BOTH") {
                if let Ok(date_idx) = result.schema.index_of("date") {
                    let mut period_cells = Vec::with_capacity(result.num_rows());
                    for batch in &result.batches {
                        let date_array = batch.column(date_idx);
                        for row in 0..date_array.len() {
                            period_cells.push(CellValue::Text(period_label(
                                date_array.as_ref(),
                                row,
                                periodicity.as_deref(),
                            )));
                        }
                    }
                    if normalized == "PERIODIC" {
                        result = table_with_cells_column(
                            &result,
                            date_idx,
                            "period",
                            &period_cells,
                            true,
                            true,
                        )?;
                    } else {
                        result = table_with_cells_column(
                            &result,
                            date_idx + 1,
                            "period",
                            &period_cells,
                            false,
                            true,
                        )?;
                    }
                }
            }
        }

        if show_date == Some(false) {
            result = result.drop_columns(vec!["date".to_string(), "period".to_string()])?;
        }

        Ok(result)
    }

    fn reshape_bqr_generic(&self, ticker: &str) -> PyResult<Self> {
        let Ok(path_idx) = self.schema.index_of("path") else {
            return Self::try_new(vec![empty_batch_from_columns(vec![
                "ticker".to_string(),
                "time".to_string(),
                "type".to_string(),
                "value".to_string(),
                "size".to_string(),
            ])?]);
        };
        let value_str_idx = self.schema.index_of("value_str").ok();
        let value_num_idx = self.schema.index_of("value_num").ok();
        let batch = self.combined_batch()?;
        let mut fields = BTreeSet::new();
        let mut records: BTreeMap<usize, HashMap<String, CellValue>> = BTreeMap::new();

        for row in 0..batch.num_rows() {
            let Some(path) = cell_to_string(&cell_from_array(batch.column(path_idx).as_ref(), row))
            else {
                continue;
            };
            let Some((idx, field)) = parse_bqr_path(&path) else {
                continue;
            };
            fields.insert(field.clone());
            let value_str = value_str_idx
                .map(|idx| cell_from_array(batch.column(idx).as_ref(), row))
                .unwrap_or(CellValue::Null);
            let value_num = value_num_idx
                .map(|idx| cell_from_array(batch.column(idx).as_ref(), row))
                .unwrap_or(CellValue::Null);
            let value = if cell_has_value(&value_str) {
                value_str
            } else {
                value_num
            };
            records.entry(idx).or_default().insert(field, value);
        }

        if records.is_empty() {
            return Self::try_new(vec![empty_batch_from_columns(vec![
                "ticker".to_string(),
                "time".to_string(),
                "type".to_string(),
                "value".to_string(),
                "size".to_string(),
            ])?]);
        }

        let priority = ["ticker", "time", "type", "value", "size"];
        let mut columns = vec!["ticker".to_string()];
        for name in priority.iter().skip(1) {
            if fields.contains(*name) {
                columns.push((*name).to_string());
            }
        }
        for name in fields {
            if !priority.contains(&name.as_str()) {
                columns.push(name);
            }
        }

        let mut out_fields = Vec::with_capacity(columns.len());
        let mut out_arrays = Vec::with_capacity(columns.len());
        for column in &columns {
            let cells = records
                .values()
                .map(|record| {
                    if column == "ticker" {
                        CellValue::Text(ticker.to_string())
                    } else {
                        record.get(column).cloned().unwrap_or(CellValue::Null)
                    }
                })
                .collect::<Vec<_>>();
            let (field, array) = build_array(column, &cells);
            out_fields.push(field);
            out_arrays.push(array);
        }

        let batch = RecordBatch::try_new(Arc::new(Schema::new(out_fields)), out_arrays)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Self::try_new(vec![batch])
    }

    fn __repr__(&self) -> String {
        format!(
            "xbbg.ArrowTable(num_rows={}, num_columns={}, columns={:?})",
            self.num_rows(),
            self.num_columns(),
            self.column_names()
        )
    }
}

fn cell_matches(array: &dyn Array, row: usize, needle: &CellValue) -> PyResult<bool> {
    if array.is_null(row) {
        return Ok(matches!(needle, CellValue::Null));
    }
    Ok(match (array.data_type(), needle) {
        (DataType::Boolean, CellValue::Bool(expected)) => {
            array
                .as_any()
                .downcast_ref::<BooleanArray>()
                .expect("BooleanArray")
                .value(row)
                == *expected
        }
        (DataType::Int64, CellValue::Int(expected)) => {
            array
                .as_any()
                .downcast_ref::<Int64Array>()
                .expect("Int64Array")
                .value(row)
                == *expected
        }
        (DataType::Int32, CellValue::Int(expected)) => {
            i64::from(
                array
                    .as_any()
                    .downcast_ref::<Int32Array>()
                    .expect("Int32Array")
                    .value(row),
            ) == *expected
        }
        (DataType::Float64, CellValue::Float(expected)) => {
            array
                .as_any()
                .downcast_ref::<Float64Array>()
                .expect("Float64Array")
                .value(row)
                == *expected
        }
        (DataType::Time64(TimeUnit::Microsecond), CellValue::Int(expected)) => {
            array
                .as_any()
                .downcast_ref::<Time64MicrosecondArray>()
                .expect("Time64MicrosecondArray")
                .value(row)
                == *expected
        }
        (DataType::Date32, CellValue::Date(expected)) => date_from_days(
            array
                .as_any()
                .downcast_ref::<Date32Array>()
                .expect("Date32Array")
                .value(row),
        )
        .map(|value| value == *expected)
        .unwrap_or(false),
        (DataType::Utf8, CellValue::Text(expected)) => {
            array
                .as_any()
                .downcast_ref::<StringArray>()
                .expect("StringArray")
                .value(row)
                == expected
        }
        _ => false,
    })
}

pub(crate) fn record_batch_to_arrow_record_batch(
    py: Python<'_>,
    batch: RecordBatch,
) -> PyResult<Py<PyAny>> {
    Py::new(py, ArrowRecordBatch::new(batch)).map(|obj| obj.into_any())
}

pub(crate) fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ArrowField>()?;
    m.add_class::<ArrowSchema>()?;
    m.add_class::<ArrowColumn>()?;
    m.add_class::<ArrowRecordBatch>()?;
    m.add_class::<ArrowTable>()?;
    Ok(())
}

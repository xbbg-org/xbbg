//! Arrow builders for reference data (BDP/BDS).

use crate::requests::ReferenceDataRequest;
use crate::{Result, RequestBuilder, Event, EventType};
use crate::session::Session;
use std::ffi::CString;
use std::sync::Arc;
use arrow::array::{Int32Array, StringArray, Float64Array, TimestampMillisecondArray};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;

/// Execute a reference-data style request (BDP/BDS) and return a
/// long-format Arrow table.
///
/// Schema:
/// - ticker: utf8
/// - field: utf8
/// - row_index: int32
/// - value_str: utf8
/// - value_num: float64
/// - value_date: timestamp[ms, tz="UTC"]
/// - currency: utf8 (optional)
/// - source: utf8 (optional)
pub fn execute_refdata_arrow(
    session: &Session,
    req: &ReferenceDataRequest,
) -> Result<RecordBatch> {
    req.validate().map_err(|e| crate::BlpError::InvalidArgument {
        detail: e.to_string(),
    })?;

    // Open service and create request
    session.open_service("//blp/refdata")?;
    let service = session.get_service("//blp/refdata")?;
    
    let blp_request = RequestBuilder::new()
        .securities(req.tickers.clone())
        .fields(req.fields.clone())
        .build(&service, "ReferenceDataRequest")?;

    // Add overrides if present
    if !req.overrides.is_empty() {
        let root_el = unsafe { blpapi_sys::blpapi_Request_elements(blp_request.as_raw()) };
        let mut el_ovs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let k_ovs = CString::new("overrides").unwrap();
        let rc = unsafe {
            blpapi_sys::blpapi_Element_getElement(root_el, &mut el_ovs, k_ovs.as_ptr(), std::ptr::null())
        };
        if rc == 0 && !el_ovs.is_null() {
            for (name, value) in &req.overrides {
                let mut ov_seq: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
                let rc = unsafe { blpapi_sys::blpapi_Element_appendElement(el_ovs, &mut ov_seq) };
                if rc == 0 && !ov_seq.is_null() {
                    let k_field_id = CString::new("fieldId").unwrap();
                    let k_value = CString::new("value").unwrap();
                    let c_name = CString::new(name.as_str()).unwrap();
                    let c_val = CString::new(value.as_str()).unwrap();
                    unsafe {
                        blpapi_sys::blpapi_Element_setElementString(ov_seq, k_field_id.as_ptr(), std::ptr::null(), c_name.as_ptr());
                        blpapi_sys::blpapi_Element_setElementString(ov_seq, k_value.as_ptr(), std::ptr::null(), c_val.as_ptr());
                    }
                }
            }
        }
    }

    // Send request
    session.send_request(&blp_request, None, None)?;

    // Collect response data
    let mut tickers = Vec::new();
    let mut fields = Vec::new();
    let mut row_indices = Vec::new();
    let mut value_strs = Vec::new();
    let mut value_nums = Vec::new();
    let mut value_dates = Vec::new();
    let mut currencies = Vec::new();
    let mut sources = Vec::new();

    // Store requested fields for fallback access
    let requested_fields = req.fields.clone();

    // Process events until we get a RESPONSE (not PARTIAL_RESPONSE)
    loop {
        let event = session.next_event(Some(60000))?; // 60s timeout
        match event.event_type() {
            EventType::Response => {
                process_refdata_response(&event, &requested_fields, &mut tickers, &mut fields, &mut row_indices,
                    &mut value_strs, &mut value_nums, &mut value_dates, &mut currencies, &mut sources)?;
                break;
            }
            EventType::PartialResponse => {
                process_refdata_response(&event, &requested_fields, &mut tickers, &mut fields, &mut row_indices,
                    &mut value_strs, &mut value_nums, &mut value_dates, &mut currencies, &mut sources)?;
                // Continue to wait for final RESPONSE
            }
            EventType::RequestStatus => {
                // Check for errors
                for msg in event.iter() {
                    let msg_type = msg.message_type();
                    if msg_type.as_str() == "RequestFailure" {
                        return Err(crate::BlpError::Internal {
                            detail: format!("Request failed: {}", msg.print_to_string()),
                        });
                    }
                }
            }
            _ => {
                // Ignore other event types
            }
        }
    }

    // Build Arrow arrays
    let schema = Arc::new(Schema::new(vec![
        Field::new("ticker", DataType::Utf8, false),
        Field::new("field", DataType::Utf8, false),
        Field::new("row_index", DataType::Int32, false),
        Field::new("value_str", DataType::Utf8, true),
        Field::new("value_num", DataType::Float64, true),
        Field::new(
            "value_date",
            DataType::Timestamp(TimeUnit::Millisecond, Some(Arc::from("UTC"))),
            true,
        ),
        Field::new("currency", DataType::Utf8, true),
        Field::new("source", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(tickers)),
            Arc::new(StringArray::from(fields)),
            Arc::new(Int32Array::from(row_indices)),
            Arc::new(StringArray::from(value_strs)),
            Arc::new(Float64Array::from(value_nums)),
            Arc::new(TimestampMillisecondArray::from(value_dates.clone()).with_timezone("UTC")),
            Arc::new(StringArray::from(currencies)),
            Arc::new(StringArray::from(sources)),
        ],
    )
    .map_err(|e| crate::BlpError::Internal {
        detail: format!("failed to build refdata RecordBatch: {e}"),
    })?;

    Ok(batch)
}

fn process_refdata_response(
    event: &Event,
    requested_fields: &[String],
    tickers: &mut Vec<String>,
    fields: &mut Vec<String>,
    row_indices: &mut Vec<i32>,
    value_strs: &mut Vec<Option<String>>,
    value_nums: &mut Vec<Option<f64>>,
    value_dates: &mut Vec<Option<i64>>,
    currencies: &mut Vec<Option<String>>,
    sources: &mut Vec<Option<String>>,
) -> Result<()> {
    for msg in event.iter() {
        let msg_type = msg.message_type();
        if msg_type.as_str() != "ReferenceDataResponse" {
            continue;
        }

        let root = msg.elements();
        if let Some(security_data_array) = root.get_element("securityData") {
            // securityData is an array of SecurityData sequences
            // Use get_value_as_element() for arrays, not get_element_at()
            let num_securities = security_data_array.num_values();
            for sec_idx in 0..num_securities {
                if let Some(sec_data) = security_data_array.get_value_as_element(sec_idx) {
                    // Get security (ticker)
                    let ticker = sec_data.get_element("security")
                        .and_then(|el| el.get_value_as_string(0))
                        .unwrap_or_default();

                    // Skip if there's a securityError
                    if sec_data.has("securityError", false) {
                        continue;
                    }

                    // Get fieldData
                    if let Some(field_data) = sec_data.get_element("fieldData") {
                        // fieldData is a sequence element with named child elements (the fields)
                        // Iterate over child elements by index
                        let num_field_elements = field_data.num_elements();
                        
                        if num_field_elements > 0 {
                            // Standard path: iterate over child elements by index
                            for field_idx in 0..num_field_elements {
                                if let Some(field_el) = field_data.get_element_at(field_idx) {
                                    let field_name = field_el.name_string().unwrap_or_default();
                                    
                                    // Check if this field is an array (BDS) or single value (BDP)
                                    let num_values = field_el.num_values();
                                    
                                    if num_values > 1 {
                                        // BDS: multiple rows per field
                                        for row_idx in 0..num_values {
                                            extract_field_value(&field_el, row_idx, &ticker, &field_name,
                                                row_idx as i32, tickers, fields, row_indices,
                                                value_strs, value_nums, value_dates, currencies, sources);
                                        }
                                    } else if num_values == 1 {
                                        // BDP: single value per field
                                        extract_field_value(&field_el, 0, &ticker, &field_name, 0,
                                            tickers, fields, row_indices,
                                            value_strs, value_nums, value_dates, currencies, sources);
                                    } else {
                                        // num_values == 0: Try to extract anyway (might be a scalar)
                                        if !field_el.is_null() {
                                            extract_field_value(&field_el, 0, &ticker, &field_name, 0,
                                                tickers, fields, row_indices,
                                                value_strs, value_nums, value_dates, currencies, sources);
                                        }
                                    }
                                }
                            }
                        } else {
                            // Fallback: if num_elements is 0, try accessing fields by name
                            // This can happen if fieldData is a sequence that doesn't report element count correctly
                            for field_name in requested_fields {
                                if let Some(field_el) = field_data.get_element(field_name) {
                                    let num_values = field_el.num_values();
                                    
                                    if num_values > 1 {
                                        // BDS: multiple rows per field
                                        for row_idx in 0..num_values {
                                            extract_field_value(&field_el, row_idx, &ticker, field_name.as_str(),
                                                row_idx as i32, tickers, fields, row_indices,
                                                value_strs, value_nums, value_dates, currencies, sources);
                                        }
                                    } else if num_values == 1 {
                                        // BDP: single value per field
                                        extract_field_value(&field_el, 0, &ticker, field_name.as_str(), 0,
                                            tickers, fields, row_indices,
                                            value_strs, value_nums, value_dates, currencies, sources);
                                    } else {
                                        // Try to extract anyway
                                        if !field_el.is_null() {
                                            extract_field_value(&field_el, 0, &ticker, field_name.as_str(), 0,
                                                tickers, fields, row_indices,
                                                value_strs, value_nums, value_dates, currencies, sources);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    Ok(())
}

fn extract_field_value(
    field_el: &crate::element::ElementRef,
    value_idx: usize,
    ticker: &str,
    field_name: &str,
    row_idx: i32,
    tickers: &mut Vec<String>,
    fields: &mut Vec<String>,
    row_indices: &mut Vec<i32>,
    value_strs: &mut Vec<Option<String>>,
    value_nums: &mut Vec<Option<f64>>,
    value_dates: &mut Vec<Option<i64>>,
    currencies: &mut Vec<Option<String>>,
    sources: &mut Vec<Option<String>>,
) {
    tickers.push(ticker.to_string());
    fields.push(field_name.to_string());
    row_indices.push(row_idx);

    // Try to extract value based on data type
    let def = field_el.definition();
    let data_type = def.data_type();
    
    let mut value_str = None;
    let mut value_num = None;
    let mut value_date = None;

    match data_type {
        crate::schema::DataType::String | crate::schema::DataType::Enumeration => {
            value_str = field_el.get_value_as_string(value_idx);
        }
        crate::schema::DataType::Float64 | crate::schema::DataType::Float32 => {
            value_num = field_el.get_value_as_float64(value_idx);
        }
        crate::schema::DataType::Int64 | crate::schema::DataType::Int32 => {
            if let Some(i64_val) = field_el.get_value_as_int64(value_idx) {
                value_num = Some(i64_val as f64);
            }
        }
        crate::schema::DataType::Date | crate::schema::DataType::Datetime => {
            if let Ok(Some(dt)) = field_el.get_value_as_datetime(value_idx) {
                value_date = Some(dt.timestamp_millis());
            }
        }
        _ => {
            // Fallback to string representation
            value_str = field_el.get_value_as_string(value_idx);
        }
    }

    value_strs.push(value_str);
    value_nums.push(value_num);
    value_dates.push(value_date);

    // Extract currency and source if present (these are typically metadata fields)
    currencies.push(None); // TODO: extract from field metadata if available
    sources.push(None); // TODO: extract from field metadata if available
}



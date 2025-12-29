//! Arrow builders for historical data (BDH).

use crate::requests::HistoricalDataRequest;
use crate::session::Session;
use crate::{CorrelationId, Event, EventType, RequestBuilder, Result};
use arrow::array::{Date32Array, Float64Array, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use std::ffi::CString;
use std::sync::Arc;

/// Execute a historical data request and return a long-format Arrow batch.
///
/// Schema:
/// - ticker: utf8
/// - date: date32
/// - field: utf8
/// - value_num: float64
/// - currency: utf8 (optional)
/// - adjustment_flag: utf8 (optional)
pub fn execute_histdata_arrow(
    session: &Session,
    req: &HistoricalDataRequest,
) -> Result<RecordBatch> {
    req.validate()
        .map_err(|e| crate::BlpError::InvalidArgument {
            detail: e.to_string(),
        })?;

    // Open service and create request
    session.open_service("//blp/refdata")?;
    let service = session.get_service("//blp/refdata")?;

    let blp_request = RequestBuilder::new()
        .securities(req.tickers.clone())
        .fields(req.fields.clone())
        .build(&service, "HistoricalDataRequest")?;

    // Set start and end dates
    // Bloomberg expects dates in YYYYMMDD format, convert if needed
    let start_date_fmt = if req.start_date.contains('-') {
        req.start_date.replace("-", "")
    } else {
        req.start_date.clone()
    };
    let end_date_fmt = if req.end_date.contains('-') {
        req.end_date.replace("-", "")
    } else {
        req.end_date.clone()
    };

    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        let k_start = CString::new("startDate").unwrap();
        let k_end = CString::new("endDate").unwrap();
        let c_start = CString::new(start_date_fmt.as_str()).unwrap();
        let c_end = CString::new(end_date_fmt.as_str()).unwrap();

        let rc1 = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k_start.as_ptr(),
            std::ptr::null(),
            c_start.as_ptr(),
        );
        let rc2 = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k_end.as_ptr(),
            std::ptr::null(),
            c_end.as_ptr(),
        );
        if rc1 != 0 || rc2 != 0 {
            return Err(crate::BlpError::InvalidArgument {
                detail: format!("failed to set dates: rc1={rc1} rc2={rc2}"),
            });
        }

        // Add overrides if present
        if !req.overrides.is_empty() {
            let mut el_ovs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
            let k_ovs = CString::new("overrides").unwrap();
            let rc = blpapi_sys::blpapi_Element_getElement(
                root_el,
                &mut el_ovs,
                k_ovs.as_ptr(),
                std::ptr::null(),
            );
            if rc == 0 && !el_ovs.is_null() {
                for (name, value) in &req.overrides {
                    let mut ov_seq: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
                    let rc = blpapi_sys::blpapi_Element_appendElement(el_ovs, &mut ov_seq);
                    if rc == 0 && !ov_seq.is_null() {
                        let k_field_id = CString::new("fieldId").unwrap();
                        let k_value = CString::new("value").unwrap();
                        let c_name = CString::new(name.as_str()).unwrap();
                        let c_val = CString::new(value.as_str()).unwrap();
                        blpapi_sys::blpapi_Element_setElementString(
                            ov_seq,
                            k_field_id.as_ptr(),
                            std::ptr::null(),
                            c_name.as_ptr(),
                        );
                        blpapi_sys::blpapi_Element_setElementString(
                            ov_seq,
                            k_value.as_ptr(),
                            std::ptr::null(),
                            c_val.as_ptr(),
                        );
                    }
                }
            }
        }
    }

    // Send request with an explicit correlation id so we can safely multiplex
    // multiple in-flight requests on the same session.
    let cid = CorrelationId::next();
    session.send_request(&blp_request, None, Some(&cid))?;

    // Collect response data
    let mut tickers = Vec::new();
    let mut dates = Vec::new();
    let mut fields = Vec::new();
    let mut value_nums = Vec::new();
    let mut currencies = Vec::new();
    let mut adjustment_flags = Vec::new();

    // Process events until we get a RESPONSE (not PARTIAL_RESPONSE)
    // Bloomberg may send multiple messages for multiple securities
    loop {
        let event = session.next_event(Some(60000))?; // 60s timeout
        match event.event_type() {
            EventType::Response => {
                process_histdata_response(
                    &event,
                    &cid,
                    &mut tickers,
                    &mut dates,
                    &mut fields,
                    &mut value_nums,
                    &mut currencies,
                    &mut adjustment_flags,
                )?;
                break;
            }
            EventType::PartialResponse => {
                process_histdata_response(
                    &event,
                    &cid,
                    &mut tickers,
                    &mut dates,
                    &mut fields,
                    &mut value_nums,
                    &mut currencies,
                    &mut adjustment_flags,
                )?;
                // Continue to wait for final RESPONSE
            }
            EventType::RequestStatus => {
                // Check for errors
                for msg in event.iter() {
                    if !msg.matches_correlation_id(&cid) {
                        continue;
                    }
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
        Field::new("date", DataType::Date32, false),
        Field::new("field", DataType::Utf8, false),
        Field::new("value_num", DataType::Float64, true),
        Field::new("currency", DataType::Utf8, true),
        Field::new("adjustment_flag", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(tickers)),
            Arc::new(Date32Array::from(dates)),
            Arc::new(StringArray::from(fields)),
            Arc::new(Float64Array::from(value_nums)),
            Arc::new(StringArray::from(currencies)),
            Arc::new(StringArray::from(adjustment_flags)),
        ],
    )
    .map_err(|e| crate::BlpError::Internal {
        detail: format!("failed to build histdata RecordBatch: {e}"),
    })?;

    Ok(batch)
}

#[allow(clippy::too_many_arguments)]
fn process_histdata_response(
    event: &Event,
    cid: &CorrelationId,
    tickers: &mut Vec<String>,
    dates: &mut Vec<i32>,
    fields: &mut Vec<String>,
    value_nums: &mut Vec<Option<f64>>,
    currencies: &mut Vec<Option<String>>,
    adjustment_flags: &mut Vec<Option<String>>,
) -> Result<()> {
    for msg in event.iter() {
        // Only process messages for our correlation id.
        if !msg.matches_correlation_id(cid) {
            continue;
        }
        let msg_type = msg.message_type();
        if msg_type.as_str() != "HistoricalDataResponse" {
            continue;
        }

        let root = msg.elements();

        // From raw response: securityData is a sequence (not an array)
        // Bloomberg returns separate messages for each security, so we process each as a sequence
        if let Some(sec_data_container) = root.get_element("securityData") {
            let num_elements = sec_data_container.num_elements();

            // Process the security as a sequence
            if num_elements > 0 {
                process_security_data(
                    &sec_data_container,
                    tickers,
                    dates,
                    fields,
                    value_nums,
                    currencies,
                    adjustment_flags,
                );
            }
        }
    }
    Ok(())
}

fn process_security_data(
    sec_data: &crate::element::ElementRef,
    tickers: &mut Vec<String>,
    dates: &mut Vec<i32>,
    fields: &mut Vec<String>,
    value_nums: &mut Vec<Option<f64>>,
    currencies: &mut Vec<Option<String>>,
    adjustment_flags: &mut Vec<Option<String>>,
) {
    // Get security (ticker)
    let ticker = sec_data
        .get_element("security")
        .and_then(|el| el.get_value_as_string(0))
        .unwrap_or_default();

    // Skip if there's a securityError
    if sec_data.has("securityError", false) {
        return;
    }

    // Get fieldData array (each element is a date + field values)
    // fieldData[] = { fieldData = { date = 2024-01-02 PX_LAST = 161.5 VOLUME = 3825044 } ... }
    if let Some(field_data_array) = sec_data.get_element("fieldData") {
        let num_rows = field_data_array.num_values();
        for row_idx in 0..num_rows {
            if let Some(row_el) = field_data_array.get_value_as_element(row_idx) {
                // Extract date
                let date_opt = row_el.get_element("date").and_then(|el| {
                    // Date is typically a Date element
                    if let Ok(Some(dt)) = el.get_value_as_datetime(0) {
                        // Convert to date32 (days since epoch)
                        let epoch = chrono::NaiveDate::from_ymd_opt(1970, 1, 1).unwrap();
                        let date = dt.date_naive();
                        Some(date.signed_duration_since(epoch).num_days() as i32)
                    } else {
                        None
                    }
                });

                if let Some(date) = date_opt {
                    // Extract each field value (PX_LAST, VOLUME, etc.)
                    let num_field_elements = row_el.num_elements();
                    for field_idx in 0..num_field_elements {
                        if let Some(field_el) = row_el.get_element_at(field_idx) {
                            let field_name = field_el.name_string().unwrap_or_default();

                            // Skip the "date" field itself
                            if field_name == "date" {
                                continue;
                            }

                            tickers.push(ticker.clone());
                            dates.push(date);
                            fields.push(field_name.clone());

                            // Extract value based on data type
                            let def = field_el.definition();
                            let data_type = def.data_type();

                            let mut value_num = None;
                            match data_type {
                                crate::schema::DataType::Float64
                                | crate::schema::DataType::Float32 => {
                                    value_num = field_el.get_value_as_float64(0);
                                }
                                crate::schema::DataType::Int64 | crate::schema::DataType::Int32 => {
                                    if let Some(i64_val) = field_el.get_value_as_int64(0) {
                                        value_num = Some(i64_val as f64);
                                    }
                                }
                                _ => {
                                    // For non-numeric fields, try to parse as float if possible
                                    if let Some(s) = field_el.get_value_as_string(0) {
                                        if let Ok(f) = s.parse::<f64>() {
                                            value_num = Some(f);
                                        }
                                    }
                                }
                            }

                            value_nums.push(value_num);

                            // Currency and adjustment flags are not embedded in historical data responses.
                            // To get currency info, request the CRNCY field separately.
                            // Adjustment flags are request parameters (adjustmentNormal, etc.), not response data.
                            currencies.push(None);
                            adjustment_flags.push(None);
                        }
                    }
                }
            }
        }
    }
}

//! Arrow builders for intraday ticks (BDTICK).

use crate::requests::IntradayTickRequest;
use crate::{Result, Event, EventType};
use crate::session::Session;
use crate::correlation::CorrelationId;
use crate::request::Request;
use std::ffi::CString;
use std::sync::Arc;
use std::collections::HashMap;
use arrow::array::{Float64Array, StringArray, TimestampMillisecondArray};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;

/// Execute an intraday tick request and return a long-format Arrow batch.
///
/// Schema:
/// - ticker: utf8
/// - ts: timestamp[ms, tz="UTC"]
/// - field: utf8 (price, size, etc.)
/// - value_num: float64
/// - event_type: utf8 (TRADE, BID, ASK, etc.)
/// - condition_code: utf8 (nullable)
///
pub fn execute_intraday_ticks_arrow(
    session: &Session,
    req: &IntradayTickRequest,
) -> Result<RecordBatch> {
    req.validate().map_err(|e| crate::BlpError::InvalidArgument {
        detail: e.to_string(),
    })?;

    // Open service
    session.open_service("//blp/refdata")?;
    let service = session.get_service("//blp/refdata")?;
    
    // IntradayTickRequest only supports one security per request
    // Send separate requests for each ticker with correlation IDs
    let num_tickers = req.tickers.len();
    let mut correlation_map: HashMap<u64, String> = HashMap::new();
    
    // Send requests for all tickers
    for (idx, ticker) in req.tickers.iter().enumerate() {
        let blp_request = create_intraday_tick_request(&service, ticker, req)?;
        let cid = CorrelationId::U64(idx as u64);
        correlation_map.insert(idx as u64, ticker.clone());
        session.send_request(&blp_request, None, Some(&cid))?;
    }

    // Collect response data
    let mut tickers = Vec::new();
    let mut timestamps = Vec::new();
    let mut fields = Vec::new();
    let mut value_nums = Vec::new();
    let mut event_types = Vec::new();
    let mut condition_codes = Vec::new();
    
    // Track which tickers have completed (by index)
    let mut completed = std::collections::HashSet::<u64>::new();
    
    // Process events until we get RESPONSE for all tickers
    while completed.len() < num_tickers {
        let event = session.next_event(Some(60000))?; // 60s timeout
        match event.event_type() {
            EventType::Response => {
                // Process response and match by correlation ID
                for msg in event.iter() {
                    if let Some(cid) = msg.correlation_id(0) {
                        if let Some(idx) = cid.as_u64() {
                            if let Some(ticker) = correlation_map.get(&idx) {
                                process_intraday_ticks_response(&event, ticker, &mut tickers, &mut timestamps,
                                    &mut fields, &mut value_nums, &mut event_types, &mut condition_codes)?;
                                completed.insert(idx);
                            }
                        }
                    }
                }
            }
            EventType::PartialResponse => {
                // Process partial response
                for msg in event.iter() {
                    if let Some(cid) = msg.correlation_id(0) {
                        if let Some(idx) = cid.as_u64() {
                            if let Some(ticker) = correlation_map.get(&idx) {
                                process_intraday_ticks_response(&event, ticker, &mut tickers, &mut timestamps,
                                    &mut fields, &mut value_nums, &mut event_types, &mut condition_codes)?;
                            }
                        }
                    }
                }
            }
            EventType::RequestStatus => {
                // Check for errors
                for msg in event.iter() {
                    let msg_type = msg.message_type();
                    if msg_type.as_str() == "RequestFailure" {
                        // Try to identify which ticker failed
                        if let Some(cid) = msg.correlation_id(0) {
                            if let Some(idx) = cid.as_u64() {
                                if let Some(ticker) = correlation_map.get(&idx) {
                                    return Err(crate::BlpError::Internal {
                                        detail: format!("Request failed for {}: {}", ticker, msg.print_to_string()),
                                    });
                                }
                            }
                        }
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
        Field::new(
            "ts",
            DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
            false,
        ),
        Field::new("field", DataType::Utf8, false),
        Field::new("value_num", DataType::Float64, true),
        Field::new("event_type", DataType::Utf8, false),
        Field::new("condition_code", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(tickers)),
            Arc::new(TimestampMillisecondArray::from(timestamps).with_timezone("UTC")),
            Arc::new(StringArray::from(fields)),
            Arc::new(Float64Array::from(value_nums)),
            Arc::new(StringArray::from(event_types)),
            Arc::new(StringArray::from(condition_codes)),
        ],
    )
    .map_err(|e| crate::BlpError::Internal {
        detail: format!("failed to build intraday ticks RecordBatch: {e}"),
    })?;

    Ok(batch)
}

fn create_intraday_tick_request(
    service: &crate::service::Service,
    ticker: &str,
    req: &IntradayTickRequest,
) -> Result<Request> {
    let blp_request = service.create_request("IntradayTickRequest")?;
    
    // Set security
    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        let k_sec = CString::new("security").unwrap();
        let c_sec = CString::new(ticker).unwrap();
        blpapi_sys::blpapi_Element_setElementString(root_el, k_sec.as_ptr(), std::ptr::null(), c_sec.as_ptr());
    }

    // Set startDateTime, endDateTime, and eventTypes
    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        let k_start = CString::new("startDateTime").unwrap();
        let k_end = CString::new("endDateTime").unwrap();
        let k_event_types = CString::new("eventTypes").unwrap();
        let c_start = CString::new(req.start.as_str()).unwrap();
        let c_end = CString::new(req.end.as_str()).unwrap();
        
        let rc1 = blpapi_sys::blpapi_Element_setElementString(root_el, k_start.as_ptr(), std::ptr::null(), c_start.as_ptr());
        let rc2 = blpapi_sys::blpapi_Element_setElementString(root_el, k_end.as_ptr(), std::ptr::null(), c_end.as_ptr());
        if rc1 != 0 || rc2 != 0 {
            return Err(crate::BlpError::InvalidArgument {
                detail: format!("failed to set intraday tick parameters: rc1={rc1} rc2={rc2}"),
            });
        }

        // Set include flags (as per legacy code)
        let include_flags = [
            ("includeConditionCodes", true),
            ("includeExchangeCodes", true),
            ("includeNonPlottableEvents", true),
            ("includeBrokerCodes", true),
            ("includeRpsCodes", true),
            ("includeTradeTime", true),
            ("includeActionCodes", true),
            ("includeIndicatorCodes", true),
        ];
        for (flag_name, flag_value) in &include_flags {
            let k_flag = CString::new(*flag_name).unwrap();
            let rc = blpapi_sys::blpapi_Element_setElementBool(root_el, k_flag.as_ptr(), std::ptr::null(), if *flag_value { 1 } else { 0 });
            if rc != 0 {
                // Non-fatal, just log
                eprintln!("Warning: failed to set {}: rc={}", flag_name, rc);
            }
        }

        // Set event types
        let mut el_event_types: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let rc = blpapi_sys::blpapi_Element_getElement(root_el, &mut el_event_types, k_event_types.as_ptr(), std::ptr::null());
        if rc == 0 && !el_event_types.is_null() {
            for event_type in &req.event_types {
                let c_event_type = CString::new(event_type.as_str()).unwrap();
                let rc = blpapi_sys::blpapi_Element_setValueString(el_event_types, c_event_type.as_ptr(), blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize);
                if rc != 0 {
                    return Err(crate::BlpError::InvalidArgument {
                        detail: format!("failed to add event type: {event_type}"),
                    });
                }
            }
        } else {
            return Err(crate::BlpError::InvalidArgument {
                detail: format!("failed to get eventTypes element: rc={}", rc),
            });
        }

        // Add overrides if present
        if !req.overrides.is_empty() {
            let mut el_ovs: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
            let k_ovs = CString::new("overrides").unwrap();
            let rc = blpapi_sys::blpapi_Element_getElement(root_el, &mut el_ovs, k_ovs.as_ptr(), std::ptr::null());
            if rc == 0 && !el_ovs.is_null() {
                for (name, value) in &req.overrides {
                    let mut ov_seq: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
                    let rc = blpapi_sys::blpapi_Element_appendElement(el_ovs, &mut ov_seq);
                    if rc == 0 && !ov_seq.is_null() {
                        let k_field_id = CString::new("fieldId").unwrap();
                        let k_value = CString::new("value").unwrap();
                        let c_name = CString::new(name.as_str()).unwrap();
                        let c_val = CString::new(value.as_str()).unwrap();
                        blpapi_sys::blpapi_Element_setElementString(ov_seq, k_field_id.as_ptr(), std::ptr::null(), c_name.as_ptr());
                        blpapi_sys::blpapi_Element_setElementString(ov_seq, k_value.as_ptr(), std::ptr::null(), c_val.as_ptr());
                    }
                }
            }
        }
    }
    
    Ok(blp_request)
}

fn process_intraday_ticks_response(
    event: &Event,
    ticker: &str,
    tickers: &mut Vec<String>,
    timestamps: &mut Vec<i64>,
    fields: &mut Vec<String>,
    value_nums: &mut Vec<Option<f64>>,
    event_types: &mut Vec<String>,
    condition_codes: &mut Vec<Option<String>>,
) -> Result<()> {
    for msg in event.iter() {
        let msg_type = msg.message_type();
        if msg_type.as_str() != "IntradayTickResponse" {
            continue;
        }

        // Check for response errors
        let root = msg.elements();
        if let Some(error_el) = root.get_element("responseError") {
            let category = error_el.get_element("category")
                .and_then(|el| el.get_value_as_string(0))
                .unwrap_or_default();
            let message = error_el.get_element("message")
                .and_then(|el| el.get_value_as_string(0))
                .unwrap_or_default();
            return Err(crate::BlpError::Internal {
                detail: format!("Intraday Tick Error: {}: {}", category, message),
            });
        }

        // Structure: tickData.tickData[] - array of tick sequences
        if let Some(tick_data) = root.get_element("tickData") {
            if let Some(tick_data_array) = tick_data.get_element("tickData") {
                let num_ticks = tick_data_array.num_values();
                for tick_idx in 0..num_ticks {
                    if let Some(tick_el) = tick_data_array.get_value_as_element(tick_idx) {
                        process_tick_data(&tick_el, ticker, tickers, timestamps, fields, value_nums, event_types, condition_codes);
                    }
                }
            }
        }
    }
    Ok(())
}

fn process_tick_data(
    tick_el: &crate::element::ElementRef,
    ticker: &str,
    tickers: &mut Vec<String>,
    timestamps: &mut Vec<i64>,
    fields: &mut Vec<String>,
    value_nums: &mut Vec<Option<f64>>,
    event_types: &mut Vec<String>,
    condition_codes: &mut Vec<Option<String>>,
) {
    // Extract timestamp from tick element
    let ts_opt = tick_el.get_element("time")
        .and_then(|el| {
            el.get_value_as_datetime(0).ok().flatten()
                .map(|dt| dt.timestamp_millis())
        });

    if let Some(ts) = ts_opt {
        // Extract event type
        let event_type = tick_el.get_element("type")
            .and_then(|el| el.get_value_as_string(0))
            .unwrap_or_default();

        // Extract condition codes (Bloomberg uses conditionCodes, not conditionCode)
        let condition_code = tick_el.get_element("conditionCodes")
            .and_then(|el| el.get_value_as_string(0));

        // Extract price (Bloomberg uses "value", not "price") and size fields
        if let Some(value_el) = tick_el.get_element("value") {
            tickers.push(ticker.to_string());
            timestamps.push(ts);
            fields.push("price".to_string());
            value_nums.push(value_el.get_value_as_float64(0));
            event_types.push(event_type.clone());
            condition_codes.push(condition_code.clone());
        }

        if let Some(size_el) = tick_el.get_element("size") {
            tickers.push(ticker.to_string());
            timestamps.push(ts);
            fields.push("size".to_string());
            value_nums.push(size_el.get_value_as_float64(0));
            event_types.push(event_type.clone());
            condition_codes.push(condition_code.clone());
        }
    }
}

//! Arrow builders for intraday bars (BDIB).

use crate::correlation::CorrelationId;
use crate::request::Request;
use crate::requests::IntradayBarRequest;
use crate::session::Session;
use crate::{EventType, MessageRef, Result};
use arrow::array::{Float64Array, StringArray, TimestampMillisecondArray};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use std::collections::HashMap;
use std::ffi::CString;
use std::sync::Arc;

/// Execute an intraday bar request and return a long-format Arrow batch.
///
/// Schema:
/// - ticker: utf8
/// - ts: timestamp[ms, tz="UTC"]
/// - field: utf8 (open, high, low, close, volume, numEvents)
/// - value_num: float64
///
pub fn execute_intraday_bars_arrow(
    session: &Session,
    req: &IntradayBarRequest,
) -> Result<RecordBatch> {
    req.validate()
        .map_err(|e| crate::BlpError::InvalidArgument {
            detail: e.to_string(),
        })?;

    // Open service
    session.open_service("//blp/refdata")?;
    let service = session.get_service("//blp/refdata")?;

    // IntradayBarRequest only supports one security per request
    // Send separate requests for each ticker with correlation IDs
    let num_tickers = req.tickers.len();
    let mut correlation_map: HashMap<u64, String> = HashMap::new();

    // Send requests for all tickers
    for (idx, ticker) in req.tickers.iter().enumerate() {
        let blp_request = create_intraday_bar_request(&service, ticker, req)?;
        let cid = CorrelationId::U64(idx as u64);
        correlation_map.insert(idx as u64, ticker.clone());
        session.send_request(&blp_request, None, Some(&cid))?;
    }

    // Collect response data
    let mut tickers = Vec::new();
    let mut timestamps = Vec::new();
    let mut fields = Vec::new();
    let mut value_nums = Vec::new();

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
                                process_intraday_bars_response(
                                    &msg,
                                    ticker,
                                    &mut tickers,
                                    &mut timestamps,
                                    &mut fields,
                                    &mut value_nums,
                                )?;
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
                                process_intraday_bars_response(
                                    &msg,
                                    ticker,
                                    &mut tickers,
                                    &mut timestamps,
                                    &mut fields,
                                    &mut value_nums,
                                )?;
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
                            if let Some(ticker) = cid.as_u64().and_then(|u| correlation_map.get(&u))
                            {
                                return Err(crate::BlpError::Internal {
                                    detail: format!(
                                        "Request failed for {}: {}",
                                        ticker,
                                        msg.print_to_string()
                                    ),
                                });
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
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(tickers)),
            Arc::new(TimestampMillisecondArray::from(timestamps).with_timezone("UTC")),
            Arc::new(StringArray::from(fields)),
            Arc::new(Float64Array::from(value_nums)),
        ],
    )
    .map_err(|e| crate::BlpError::Internal {
        detail: format!("failed to build intraday bars RecordBatch: {e}"),
    })?;

    Ok(batch)
}

fn create_intraday_bar_request(
    service: &crate::service::Service,
    ticker: &str,
    req: &IntradayBarRequest,
) -> Result<Request> {
    let blp_request = service.create_request("IntradayBarRequest")?;

    // Set security
    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        let k_sec = CString::new("security").unwrap();
        let c_sec = CString::new(ticker).unwrap();
        blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k_sec.as_ptr(),
            std::ptr::null(),
            c_sec.as_ptr(),
        );
    }

    // Set startDateTime, endDateTime, interval, eventType, and optionally intervalHasSeconds
    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        let k_start = CString::new("startDateTime").unwrap();
        let k_end = CString::new("endDateTime").unwrap();
        let k_interval = CString::new("interval").unwrap();
        let k_event_type = CString::new("eventType").unwrap();
        let c_start = CString::new(req.start.as_str()).unwrap();
        let c_end = CString::new(req.end.as_str()).unwrap();
        let c_event_type = CString::new(req.event_type.as_str()).unwrap();

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
        let rc3 = blpapi_sys::blpapi_Element_setElementInt32(
            root_el,
            k_interval.as_ptr(),
            std::ptr::null(),
            req.interval as i32,
        );
        let rc4 = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k_event_type.as_ptr(),
            std::ptr::null(),
            c_event_type.as_ptr(),
        );
        if rc1 != 0 || rc2 != 0 || rc3 != 0 || rc4 != 0 {
            return Err(crate::BlpError::InvalidArgument {
                detail: format!("failed to set intraday bar parameters: rc1={rc1} rc2={rc2} rc3={rc3} rc4={rc4}"),
            });
        }

        // Set intervalHasSeconds if needed
        if req.interval_has_seconds {
            let k_interval_has_seconds = CString::new("intervalHasSeconds").unwrap();
            let rc5 = blpapi_sys::blpapi_Element_setElementBool(
                root_el,
                k_interval_has_seconds.as_ptr(),
                std::ptr::null(),
                1,
            );
            if rc5 != 0 {
                return Err(crate::BlpError::InvalidArgument {
                    detail: format!("failed to set intervalHasSeconds: rc5={rc5}"),
                });
            }
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

    Ok(blp_request)
}

fn process_intraday_bars_response(
    msg: &MessageRef,
    ticker: &str,
    tickers: &mut Vec<String>,
    timestamps: &mut Vec<i64>,
    fields: &mut Vec<String>,
    value_nums: &mut Vec<Option<f64>>,
) -> Result<()> {
    let msg_type = msg.message_type();
    if msg_type.as_str() != "IntradayBarResponse" {
        return Ok(());
    }

    // Check for response errors
    let root = msg.elements();
    if let Some(error_el) = root.get_element("responseError") {
        let category = error_el
            .get_element("category")
            .and_then(|el| el.get_value_as_string(0))
            .unwrap_or_default();
        let message = error_el
            .get_element("message")
            .and_then(|el| el.get_value_as_string(0))
            .unwrap_or_default();
        return Err(crate::BlpError::Internal {
            detail: format!("Intraday Bar Error: {}: {}", category, message),
        });
    }

    // Structure: barData.barTickData[] - array of bar sequences
    if let Some(bar_data) = root.get_element("barData") {
        if let Some(bar_tick_data_array) = bar_data.get_element("barTickData") {
            let num_bars = bar_tick_data_array.num_values();
            for bar_idx in 0..num_bars {
                if let Some(bar_el) = bar_tick_data_array.get_value_as_element(bar_idx) {
                    process_bar_element(&bar_el, ticker, tickers, timestamps, fields, value_nums);
                }
            }
        }
    }
    Ok(())
}

fn process_bar_element(
    bar_el: &crate::element::ElementRef,
    ticker: &str,
    tickers: &mut Vec<String>,
    timestamps: &mut Vec<i64>,
    fields: &mut Vec<String>,
    value_nums: &mut Vec<Option<f64>>,
) {
    // Extract timestamp from bar element
    let ts_opt = bar_el.get_element("time").and_then(|el| {
        el.get_value_as_datetime(0)
            .ok()
            .flatten()
            .map(|dt| dt.timestamp_millis())
    });

    if let Some(ts) = ts_opt {
        // Extract bar fields: open, high, low, close, volume, numEvents
        // Bloomberg uses numEvents, not numTrades
        let bar_fields = ["open", "high", "low", "close", "volume", "numEvents"];
        for field_name in &bar_fields {
            if let Some(field_el) = bar_el.get_element(field_name) {
                tickers.push(ticker.to_string());
                timestamps.push(ts);
                fields.push(field_name.to_string());
                value_nums.push(field_el.get_value_as_float64(0));
            }
        }
    }
}

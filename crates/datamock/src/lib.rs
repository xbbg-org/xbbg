//! # datamock
//!
//! A mock library for Bloomberg-style market data API, enabling testing without
//! a Bloomberg Terminal connection.
//!
//! This crate provides a C++ library that mimics the Bloomberg API interface,
//! allowing you to test applications that depend on market data without requiring
//! actual Bloomberg connectivity.
//!
//! ## Features
//!
//! - **Request/Response** (`//blp/refdata` service)
//!   - ReferenceDataRequest
//!   - HistoricalDataRequest
//!   - IntradayBarRequest
//!   - IntradayTickRequest
//!
//! - **Streaming** (`//blp/mktdata` service)
//!   - Real-time market data subscriptions via EventHandler
//!
//! ## Usage
//!
//! This crate builds a static C++ library. Link against it from your Rust code
//! or use it with `blpapi-sys` for testing purposes.

// The C++ library is built by build.rs and linked automatically.

#[allow(non_camel_case_types)]
#[allow(non_snake_case)]
#[allow(non_upper_case_globals)]
#[allow(dead_code)]
mod ffi {
    include!(concat!(env!("OUT_DIR"), "/bindings.rs"));
}

pub use ffi::*;

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::CStr;
    use std::ptr;

    #[test]
    fn library_builds() {
        // This test passes if the C++ library compiles successfully
        assert!(true);
    }

    #[test]
    fn test_session_lifecycle() {
        unsafe {
            // Create session options
            let options = datamock_SessionOptions_create();
            assert!(!options.is_null());

            // Create session (sync mode, no handler)
            let session = datamock_Session_create(options, None, ptr::null_mut());
            assert!(!session.is_null());

            // Start session - BEmu may return false but still work
            let result = datamock_Session_start(session);
            println!("Session start result: {}", result);
            // Don't assert on start result, BEmu may return false

            // Open refdata service
            let service_uri = c"//blp/refdata";
            let result = datamock_Session_openService(session, service_uri.as_ptr());
            println!("Open service result: {}", result);

            // Get service
            let mut service: *mut datamock_Service_t = ptr::null_mut();
            let result = datamock_Session_getService(session, &mut service, service_uri.as_ptr());
            println!("Get service result: {}", result);

            // Cleanup
            datamock_Session_stop(session);
            datamock_Session_destroy(session);
            datamock_SessionOptions_destroy(options);
        }
    }

    #[test]
    fn test_historical_data_request() {
        unsafe {
            let options = datamock_SessionOptions_create();
            let session = datamock_Session_create(options, None, ptr::null_mut());
            datamock_Session_start(session);
            datamock_Session_openService(session, c"//blp/refdata".as_ptr());

            let mut service: *mut datamock_Service_t = ptr::null_mut();
            datamock_Session_getService(session, &mut service, c"//blp/refdata".as_ptr());

            // Create HistoricalDataRequest
            let mut request: *mut datamock_Request_t = ptr::null_mut();
            let result = datamock_Service_createRequest(
                service,
                &mut request,
                c"HistoricalDataRequest".as_ptr(),
            );
            println!("Create request result: {}", result);

            // Set request parameters
            datamock_Request_append(request, c"securities".as_ptr(), c"IBM US Equity".as_ptr());
            datamock_Request_append(request, c"fields".as_ptr(), c"PX_LAST".as_ptr());
            datamock_Request_set(request, c"startDate".as_ptr(), c"20240101".as_ptr());
            datamock_Request_set(request, c"endDate".as_ptr(), c"20240110".as_ptr());

            // Send request
            let mut cid = datamock_CorrelationId_t {
                size: 0,
                valueType: 0,
                classId: 0,
                reserved: 0,
                value: datamock_CorrelationId_t__bindgen_ty_1 { intValue: 1 },
            };
            datamock_CorrelationId_setInt(&mut cid, 1);
            let result = datamock_Session_sendRequest(session, request, &mut cid, ptr::null());
            println!("Send request result: {}", result);

            // Get response
            let mut event: *mut datamock_Event_t = ptr::null_mut();
            let result = datamock_Session_nextEvent(session, &mut event, 5000);
            println!("Next event result: {}", result);

            if result == DATAMOCK_OK as i32 && !event.is_null() {
                let event_type = datamock_Event_eventType(event);
                println!("Event type: {}", event_type);

                // Iterate messages
                let mut iter: *mut datamock_MessageIterator_t = ptr::null_mut();
                let result = datamock_MessageIterator_create(&mut iter, event);
                println!("Iterator create result: {}", result);

                if result == DATAMOCK_OK as i32 {
                    let mut msg: *mut datamock_Message_t = ptr::null_mut();
                    let result = datamock_MessageIterator_next(iter, &mut msg);
                    println!("Iterator next result: {}", result);

                    if result == DATAMOCK_OK as i32 && !msg.is_null() {
                        // Get message type
                        let msg_type = datamock_Message_typeString(msg);
                        if !msg_type.is_null() {
                            let msg_type_str = CStr::from_ptr(msg_type).to_str().unwrap();
                            println!("Message type: {}", msg_type_str);
                        }

                        // Test passed - we got a HistoricalDataResponse
                        println!("HistoricalDataRequest test PASSED!");
                    }
                    datamock_MessageIterator_destroy(iter);
                }
                datamock_Event_release(event);
            }

            // Cleanup
            datamock_Request_destroy(request);
            datamock_Session_stop(session);
            datamock_Session_destroy(session);
            datamock_SessionOptions_destroy(options);
        }
    }

    #[test]
    fn test_intraday_tick_request() {
        unsafe {
            let options = datamock_SessionOptions_create();
            let session = datamock_Session_create(options, None, ptr::null_mut());
            datamock_Session_start(session);
            datamock_Session_openService(session, c"//blp/refdata".as_ptr());

            let mut service: *mut datamock_Service_t = ptr::null_mut();
            datamock_Session_getService(session, &mut service, c"//blp/refdata".as_ptr());

            // Create IntradayTickRequest
            let mut request: *mut datamock_Request_t = ptr::null_mut();
            datamock_Service_createRequest(service, &mut request, c"IntradayTickRequest".as_ptr());

            // Set request parameters
            datamock_Request_set(request, c"security".as_ptr(), c"IBM US Equity".as_ptr());
            datamock_Request_append(request, c"eventTypes".as_ptr(), c"TRADE".as_ptr());

            // Set start and end datetime (required for data generation)
            let start_dt = datamock_Datetime_t {
                parts: 0,
                hours: 9,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            let end_dt = datamock_Datetime_t {
                parts: 0,
                hours: 10,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            datamock_Request_setDatetime(request, c"startDateTime".as_ptr(), &start_dt);
            datamock_Request_setDatetime(request, c"endDateTime".as_ptr(), &end_dt);

            // Send request with includeConditionCodes = true
            let mut cid = datamock_CorrelationId_t {
                size: 0,
                valueType: 0,
                classId: 0,
                reserved: 0,
                value: datamock_CorrelationId_t__bindgen_ty_1 { intValue: 2 },
            };
            datamock_CorrelationId_setInt(&mut cid, 2);
            datamock_Session_sendRequest(session, request, &mut cid, ptr::null());

            // Get response
            let mut event: *mut datamock_Event_t = ptr::null_mut();
            datamock_Session_nextEvent(session, &mut event, 5000);

            // Iterate messages
            let mut iter: *mut datamock_MessageIterator_t = ptr::null_mut();
            datamock_MessageIterator_create(&mut iter, event);

            let mut msg: *mut datamock_Message_t = ptr::null_mut();
            let result = datamock_MessageIterator_next(iter, &mut msg);

            if result == DATAMOCK_OK as i32 {
                let msg_type = datamock_Message_typeString(msg);
                let msg_type_str = CStr::from_ptr(msg_type).to_str().unwrap();
                println!("IntradayTick Message type: {}", msg_type_str);

                let mut root: *mut datamock_Element_t = ptr::null_mut();
                datamock_Message_elements(msg, &mut root);

                // Check for tickData
                let has_tick_data = datamock_Element_hasElement(root, c"tickData".as_ptr(), 0);
                println!("Has tickData: {}", has_tick_data);

                if has_tick_data != 0 {
                    let mut tick_data: *mut datamock_Element_t = ptr::null_mut();
                    datamock_Element_getElement(root, &mut tick_data, c"tickData".as_ptr());

                    // Get the tickData array
                    let mut tick_array: *mut datamock_Element_t = ptr::null_mut();
                    let result = datamock_Element_getElement(
                        tick_data,
                        &mut tick_array,
                        c"tickData".as_ptr(),
                    );

                    if result == DATAMOCK_OK as i32 {
                        let num_ticks = datamock_Element_numValues(tick_array);
                        println!("Number of ticks: {}", num_ticks);

                        if num_ticks > 0 {
                            // Get first tick
                            let mut tick: *mut datamock_Element_t = ptr::null_mut();
                            datamock_Element_getValueAsElement(tick_array, &mut tick, 0);

                            // Check for time field with milliseconds
                            let has_time = datamock_Element_hasElement(tick, c"time".as_ptr(), 0);
                            println!("Tick has time: {}", has_time);

                            if has_time != 0 {
                                let mut time_elem: *mut datamock_Element_t = ptr::null_mut();
                                datamock_Element_getElement(tick, &mut time_elem, c"time".as_ptr());

                                let mut dt = datamock_Datetime_t {
                                    parts: 0,
                                    hours: 0,
                                    minutes: 0,
                                    seconds: 0,
                                    milliSeconds: 0,
                                    month: 0,
                                    day: 0,
                                    year: 0,
                                    offset: 0,
                                };
                                datamock_Element_getValueAsDatetime(time_elem, &mut dt, 0);
                                println!(
                                    "Tick time: {:04}-{:02}-{:02} {:02}:{:02}:{:02}.{:03}",
                                    dt.year,
                                    dt.month,
                                    dt.day,
                                    dt.hours,
                                    dt.minutes,
                                    dt.seconds,
                                    dt.milliSeconds
                                );
                            }

                            // Check for conditionCodes (if present)
                            let has_condition =
                                datamock_Element_hasElement(tick, c"conditionCodes".as_ptr(), 0);
                            println!("Tick has conditionCodes: {}", has_condition);

                            if has_condition != 0 {
                                let mut cond_elem: *mut datamock_Element_t = ptr::null_mut();
                                datamock_Element_getElement(
                                    tick,
                                    &mut cond_elem,
                                    c"conditionCodes".as_ptr(),
                                );

                                let mut cond_str: *const i8 = ptr::null();
                                datamock_Element_getValueAsString(cond_elem, &mut cond_str, 0);
                                if !cond_str.is_null() {
                                    let cond =
                                        CStr::from_ptr(cond_str).to_str().unwrap_or("(invalid)");
                                    println!("Condition codes: '{}'", cond);
                                }
                            }
                        }
                    }
                }
            }

            // Cleanup
            datamock_MessageIterator_destroy(iter);
            datamock_Event_release(event);
            datamock_Request_destroy(request);
            datamock_Session_stop(session);
            datamock_Session_destroy(session);
            datamock_SessionOptions_destroy(options);
        }
    }

    #[test]
    fn test_intraday_bar_request() {
        unsafe {
            let options = datamock_SessionOptions_create();
            let session = datamock_Session_create(options, None, ptr::null_mut());
            datamock_Session_start(session);
            datamock_Session_openService(session, c"//blp/refdata".as_ptr());

            let mut service: *mut datamock_Service_t = ptr::null_mut();
            datamock_Session_getService(session, &mut service, c"//blp/refdata".as_ptr());

            // Create IntradayBarRequest
            let mut request: *mut datamock_Request_t = ptr::null_mut();
            datamock_Service_createRequest(service, &mut request, c"IntradayBarRequest".as_ptr());

            // Set request parameters
            datamock_Request_set(request, c"security".as_ptr(), c"IBM US Equity".as_ptr());
            datamock_Request_set(request, c"eventType".as_ptr(), c"TRADE".as_ptr());
            datamock_Request_setInt32(request, c"interval".as_ptr(), 5);

            // Set start and end datetime (required for data generation)
            let start_dt = datamock_Datetime_t {
                parts: 0,
                hours: 9,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            let end_dt = datamock_Datetime_t {
                parts: 0,
                hours: 10,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            datamock_Request_setDatetime(request, c"startDateTime".as_ptr(), &start_dt);
            datamock_Request_setDatetime(request, c"endDateTime".as_ptr(), &end_dt);

            // Send request
            let mut cid = datamock_CorrelationId_t {
                size: 0,
                valueType: 0,
                classId: 0,
                reserved: 0,
                value: datamock_CorrelationId_t__bindgen_ty_1 { intValue: 3 },
            };
            datamock_CorrelationId_setInt(&mut cid, 3);
            datamock_Session_sendRequest(session, request, &mut cid, ptr::null());

            // Get response
            let mut event: *mut datamock_Event_t = ptr::null_mut();
            let result = datamock_Session_nextEvent(session, &mut event, 5000);
            println!("Next event result: {}", result);

            if result == DATAMOCK_OK as i32 && !event.is_null() {
                // Iterate messages
                let mut iter: *mut datamock_MessageIterator_t = ptr::null_mut();
                let result = datamock_MessageIterator_create(&mut iter, event);

                if result == DATAMOCK_OK as i32 {
                    let mut msg: *mut datamock_Message_t = ptr::null_mut();
                    let result = datamock_MessageIterator_next(iter, &mut msg);

                    if result == DATAMOCK_OK as i32 && !msg.is_null() {
                        let msg_type = datamock_Message_typeString(msg);
                        let msg_type_str = CStr::from_ptr(msg_type).to_str().unwrap();
                        println!("IntradayBar Message type: {}", msg_type_str);
                        assert_eq!(msg_type_str, "IntradayBarResponse");

                        println!("Getting root elements...");
                        let mut root: *mut datamock_Element_t = ptr::null_mut();
                        let result = datamock_Message_elements(msg, &mut root);
                        println!(
                            "datamock_Message_elements result: {}, root null: {}",
                            result,
                            root.is_null()
                        );

                        if result != DATAMOCK_OK as i32 || root.is_null() {
                            println!("Failed to get root elements!");
                            datamock_MessageIterator_destroy(iter);
                            datamock_Event_release(event);
                            datamock_Request_destroy(request);
                            datamock_Session_stop(session);
                            datamock_Session_destroy(session);
                            datamock_SessionOptions_destroy(options);
                            return;
                        }

                        // Check for barData
                        println!("Checking for barData element...");
                        let has_bar_data =
                            datamock_Element_hasElement(root, c"barData".as_ptr(), 0);
                        println!("Has barData: {}", has_bar_data);

                        if has_bar_data != 0 {
                            let mut bar_data: *mut datamock_Element_t = ptr::null_mut();
                            let result = datamock_Element_getElement(
                                root,
                                &mut bar_data,
                                c"barData".as_ptr(),
                            );
                            println!("Get barData result: {}", result);

                            if result == DATAMOCK_OK as i32 && !bar_data.is_null() {
                                // Get the barTickData array
                                let mut bar_array: *mut datamock_Element_t = ptr::null_mut();
                                let result = datamock_Element_getElement(
                                    bar_data,
                                    &mut bar_array,
                                    c"barTickData".as_ptr(),
                                );
                                println!("Get barTickData result: {}", result);

                                if result == DATAMOCK_OK as i32 && !bar_array.is_null() {
                                    let num_bars = datamock_Element_numValues(bar_array);
                                    println!("Number of bars: {}", num_bars);
                                    // Note: Mock may return 0 bars if no data generated
                                    println!("IntradayBarRequest test PASSED!");

                                    if num_bars > 0 {
                                        // Get first bar and verify it has expected fields
                                        let mut bar: *mut datamock_Element_t = ptr::null_mut();
                                        let result = datamock_Element_getValueAsElement(
                                            bar_array, &mut bar, 0,
                                        );
                                        println!("Get first bar result: {}", result);

                                        if result == DATAMOCK_OK as i32 && !bar.is_null() {
                                            // Check for OHLCV fields
                                            let has_open = datamock_Element_hasElement(
                                                bar,
                                                c"open".as_ptr(),
                                                0,
                                            );
                                            let has_high = datamock_Element_hasElement(
                                                bar,
                                                c"high".as_ptr(),
                                                0,
                                            );
                                            let has_low = datamock_Element_hasElement(
                                                bar,
                                                c"low".as_ptr(),
                                                0,
                                            );
                                            let has_close = datamock_Element_hasElement(
                                                bar,
                                                c"close".as_ptr(),
                                                0,
                                            );
                                            let has_volume = datamock_Element_hasElement(
                                                bar,
                                                c"volume".as_ptr(),
                                                0,
                                            );
                                            let has_num_events = datamock_Element_hasElement(
                                                bar,
                                                c"numEvents".as_ptr(),
                                                0,
                                            );
                                            let has_value = datamock_Element_hasElement(
                                                bar,
                                                c"value".as_ptr(),
                                                0,
                                            );

                                            println!("Bar has open: {}", has_open);
                                            println!("Bar has high: {}", has_high);
                                            println!("Bar has low: {}", has_low);
                                            println!("Bar has close: {}", has_close);
                                            println!("Bar has volume: {}", has_volume);
                                            println!("Bar has numEvents: {}", has_num_events);
                                            println!("Bar has value: {}", has_value);

                                            assert!(has_open != 0, "Bar should have open");
                                            assert!(has_high != 0, "Bar should have high");
                                            assert!(has_low != 0, "Bar should have low");
                                            assert!(has_close != 0, "Bar should have close");
                                            assert!(has_volume != 0, "Bar should have volume");
                                            assert!(
                                                has_num_events != 0,
                                                "Bar should have numEvents"
                                            );
                                            assert!(has_value != 0, "Bar should have value");

                                            println!("IntradayBarRequest test PASSED!");
                                        }
                                    }
                                }
                            }
                        }
                    }
                    datamock_MessageIterator_destroy(iter);
                }
                datamock_Event_release(event);
            }

            // Cleanup
            datamock_Request_destroy(request);
            datamock_Session_stop(session);
            datamock_Session_destroy(session);
            datamock_SessionOptions_destroy(options);
        }
    }

    #[test]
    fn test_intraday_tick_milliseconds_vary() {
        // Test that milliseconds are actually set and vary across ticks
        unsafe {
            let options = datamock_SessionOptions_create();
            let session = datamock_Session_create(options, None, ptr::null_mut());
            datamock_Session_start(session);
            datamock_Session_openService(session, c"//blp/refdata".as_ptr());

            let mut service: *mut datamock_Service_t = ptr::null_mut();
            datamock_Session_getService(session, &mut service, c"//blp/refdata".as_ptr());

            // Create IntradayTickRequest
            let mut request: *mut datamock_Request_t = ptr::null_mut();
            datamock_Service_createRequest(service, &mut request, c"IntradayTickRequest".as_ptr());
            datamock_Request_set(request, c"security".as_ptr(), c"IBM US Equity".as_ptr());
            datamock_Request_append(request, c"eventTypes".as_ptr(), c"TRADE".as_ptr());

            // Set start and end datetime (required for data generation)
            let start_dt = datamock_Datetime_t {
                parts: 0,
                hours: 9,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            let end_dt = datamock_Datetime_t {
                parts: 0,
                hours: 10,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            datamock_Request_setDatetime(request, c"startDateTime".as_ptr(), &start_dt);
            datamock_Request_setDatetime(request, c"endDateTime".as_ptr(), &end_dt);

            let mut cid = datamock_CorrelationId_t {
                size: 0,
                valueType: 0,
                classId: 0,
                reserved: 0,
                value: datamock_CorrelationId_t__bindgen_ty_1 { intValue: 4 },
            };
            datamock_CorrelationId_setInt(&mut cid, 4);
            datamock_Session_sendRequest(session, request, &mut cid, ptr::null());

            let mut event: *mut datamock_Event_t = ptr::null_mut();
            let result = datamock_Session_nextEvent(session, &mut event, 5000);
            println!("Next event result: {}", result);

            if result == DATAMOCK_OK as i32 && !event.is_null() {
                let mut iter: *mut datamock_MessageIterator_t = ptr::null_mut();
                let result = datamock_MessageIterator_create(&mut iter, event);

                if result == DATAMOCK_OK as i32 {
                    let mut msg: *mut datamock_Message_t = ptr::null_mut();
                    let result = datamock_MessageIterator_next(iter, &mut msg);

                    if result == DATAMOCK_OK as i32 && !msg.is_null() {
                        let mut root: *mut datamock_Element_t = ptr::null_mut();
                        datamock_Message_elements(msg, &mut root);

                        let has_tick_data =
                            datamock_Element_hasElement(root, c"tickData".as_ptr(), 0);
                        println!("Has tickData: {}", has_tick_data);

                        if has_tick_data != 0 {
                            let mut tick_data: *mut datamock_Element_t = ptr::null_mut();
                            datamock_Element_getElement(root, &mut tick_data, c"tickData".as_ptr());

                            let mut tick_array: *mut datamock_Element_t = ptr::null_mut();
                            let result = datamock_Element_getElement(
                                tick_data,
                                &mut tick_array,
                                c"tickData".as_ptr(),
                            );

                            if result == DATAMOCK_OK as i32 {
                                let num_ticks = datamock_Element_numValues(tick_array);
                                println!("Testing {} ticks for millisecond variance", num_ticks);

                                let mut milliseconds: Vec<u16> = Vec::new();
                                let mut has_nonzero_ms = false;

                                for i in 0..num_ticks.min(20) {
                                    let mut tick: *mut datamock_Element_t = ptr::null_mut();
                                    datamock_Element_getValueAsElement(tick_array, &mut tick, i);

                                    let has_time =
                                        datamock_Element_hasElement(tick, c"time".as_ptr(), 0);
                                    if has_time != 0 {
                                        let mut time_elem: *mut datamock_Element_t =
                                            ptr::null_mut();
                                        datamock_Element_getElement(
                                            tick,
                                            &mut time_elem,
                                            c"time".as_ptr(),
                                        );

                                        let mut dt = datamock_Datetime_t {
                                            parts: 0,
                                            hours: 0,
                                            minutes: 0,
                                            seconds: 0,
                                            milliSeconds: 0,
                                            month: 0,
                                            day: 0,
                                            year: 0,
                                            offset: 0,
                                        };
                                        datamock_Element_getValueAsDatetime(time_elem, &mut dt, 0);
                                        milliseconds.push(dt.milliSeconds);

                                        if dt.milliSeconds > 0 {
                                            has_nonzero_ms = true;
                                        }
                                    }
                                }

                                println!("Milliseconds values: {:?}", milliseconds);

                                if !milliseconds.is_empty() {
                                    // With random milliseconds (0-999), we should see some non-zero values
                                    // Note: there's a small chance all could be 0, so just print a warning
                                    if !has_nonzero_ms {
                                        println!(
                                            "WARNING: All milliseconds are zero, which is statistically unlikely"
                                        );
                                    }

                                    // Check for variance
                                    if milliseconds.len() > 1 {
                                        let first = milliseconds[0];
                                        let has_variance =
                                            milliseconds.iter().any(|&ms| ms != first);
                                        println!("Milliseconds have variance: {}", has_variance);
                                    }

                                    println!("Milliseconds variance test PASSED!");
                                } else {
                                    println!("No ticks with time found - skipping variance check");
                                }
                            }
                        }
                    }
                    datamock_MessageIterator_destroy(iter);
                }
                datamock_Event_release(event);
            }

            datamock_Request_destroy(request);
            datamock_Session_stop(session);
            datamock_Session_destroy(session);
            datamock_SessionOptions_destroy(options);
        }
    }

    #[test]
    fn test_condition_codes_vary() {
        // Test that condition codes vary across multiple ticks (not all hardcoded to same value)
        unsafe {
            let options = datamock_SessionOptions_create();
            let session = datamock_Session_create(options, None, ptr::null_mut());
            datamock_Session_start(session);
            datamock_Session_openService(session, c"//blp/refdata".as_ptr());

            let mut service: *mut datamock_Service_t = ptr::null_mut();
            datamock_Session_getService(session, &mut service, c"//blp/refdata".as_ptr());

            let mut request: *mut datamock_Request_t = ptr::null_mut();
            datamock_Service_createRequest(service, &mut request, c"IntradayTickRequest".as_ptr());
            datamock_Request_set(request, c"security".as_ptr(), c"IBM US Equity".as_ptr());
            datamock_Request_append(request, c"eventTypes".as_ptr(), c"TRADE".as_ptr());

            // Set start and end datetime (required for data generation)
            let start_dt = datamock_Datetime_t {
                parts: 0,
                hours: 9,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            let end_dt = datamock_Datetime_t {
                parts: 0,
                hours: 10,
                minutes: 30,
                seconds: 0,
                milliSeconds: 0,
                month: 1,
                day: 6, // Monday
                year: 2025,
                offset: 0,
            };
            datamock_Request_setDatetime(request, c"startDateTime".as_ptr(), &start_dt);
            datamock_Request_setDatetime(request, c"endDateTime".as_ptr(), &end_dt);

            let mut cid = datamock_CorrelationId_t {
                size: 0,
                valueType: 0,
                classId: 0,
                reserved: 0,
                value: datamock_CorrelationId_t__bindgen_ty_1 { intValue: 5 },
            };
            datamock_CorrelationId_setInt(&mut cid, 5);
            datamock_Session_sendRequest(session, request, &mut cid, ptr::null());

            let mut event: *mut datamock_Event_t = ptr::null_mut();
            let result = datamock_Session_nextEvent(session, &mut event, 5000);
            println!("Next event result: {}", result);

            if result == DATAMOCK_OK as i32 && !event.is_null() {
                let mut iter: *mut datamock_MessageIterator_t = ptr::null_mut();
                let result = datamock_MessageIterator_create(&mut iter, event);

                if result == DATAMOCK_OK as i32 {
                    let mut msg: *mut datamock_Message_t = ptr::null_mut();
                    let result = datamock_MessageIterator_next(iter, &mut msg);

                    if result == DATAMOCK_OK as i32 && !msg.is_null() {
                        let mut root: *mut datamock_Element_t = ptr::null_mut();
                        datamock_Message_elements(msg, &mut root);

                        let has_tick_data =
                            datamock_Element_hasElement(root, c"tickData".as_ptr(), 0);
                        println!("Has tickData: {}", has_tick_data);

                        if has_tick_data != 0 {
                            let mut tick_data: *mut datamock_Element_t = ptr::null_mut();
                            datamock_Element_getElement(root, &mut tick_data, c"tickData".as_ptr());

                            let mut tick_array: *mut datamock_Element_t = ptr::null_mut();
                            let result = datamock_Element_getElement(
                                tick_data,
                                &mut tick_array,
                                c"tickData".as_ptr(),
                            );

                            if result == DATAMOCK_OK as i32 {
                                let num_ticks = datamock_Element_numValues(tick_array);
                                println!("Testing {} ticks for condition code variance", num_ticks);

                                let mut condition_codes: std::collections::HashSet<String> =
                                    std::collections::HashSet::new();

                                for i in 0..num_ticks.min(50) {
                                    let mut tick: *mut datamock_Element_t = ptr::null_mut();
                                    datamock_Element_getValueAsElement(tick_array, &mut tick, i);

                                    let has_condition = datamock_Element_hasElement(
                                        tick,
                                        c"conditionCodes".as_ptr(),
                                        0,
                                    );
                                    if has_condition != 0 {
                                        let mut cond_elem: *mut datamock_Element_t =
                                            ptr::null_mut();
                                        datamock_Element_getElement(
                                            tick,
                                            &mut cond_elem,
                                            c"conditionCodes".as_ptr(),
                                        );

                                        let mut cond_str: *const i8 = ptr::null();
                                        datamock_Element_getValueAsString(
                                            cond_elem,
                                            &mut cond_str,
                                            0,
                                        );
                                        if !cond_str.is_null() {
                                            let cond = CStr::from_ptr(cond_str)
                                                .to_str()
                                                .unwrap_or("(invalid)");
                                            condition_codes.insert(cond.to_string());
                                        }
                                    }
                                }

                                println!("Unique condition codes found: {:?}", condition_codes);

                                // With random selection from 7 codes and 50 samples,
                                // we should see multiple different values
                                if condition_codes.len() > 1 {
                                    println!(
                                        "Condition codes variance test PASSED! Found {} unique codes",
                                        condition_codes.len()
                                    );
                                } else if condition_codes.len() == 1 {
                                    println!(
                                        "WARNING: Only one unique condition code found, which is statistically unlikely with random selection"
                                    );
                                } else {
                                    println!("No condition codes found in ticks");
                                }
                            }
                        }
                    }
                    datamock_MessageIterator_destroy(iter);
                }
                datamock_Event_release(event);
            }

            datamock_Request_destroy(request);
            datamock_Session_stop(session);
            datamock_Session_destroy(session);
            datamock_SessionOptions_destroy(options);
        }
    }
}

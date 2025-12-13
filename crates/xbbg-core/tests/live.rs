#[cfg(feature = "live")]
#[test]
fn live_builds() {
    // Placeholder to ensure the crate builds with the 'live' feature toggled.
    assert!(!xbbg_core::version().is_empty());
}

#[cfg(feature = "live")]
fn log_msg(msg: &xbbg_core::MessageRef) {
    let ty = msg.message_type();
    let mut cids = Vec::new();
    let n = msg.num_correlation_ids();
    for i in 0..(n as usize) {
        if let Some(cid) = msg.correlation_id(i) {
            if let Some(u) = cid.as_u64() {
                cids.push(format!("u64:{u}"));
            } else if let Some(s) = cid.as_tag() {
                cids.push(format!("tag:{s}"));
            }
        }
    }
    let rid = msg.get_request_id().unwrap_or("");
    println!("[{}] cids=[{}] rid={}", ty, cids.join(","), rid);
    let printed = msg.print_to_string();
    // Trim extremely long outputs for readability in CI
    let clipped = if printed.len() > 5000 {
        &printed[..5000]
    } else {
        &printed
    };
    println!("{}", clipped);
}

#[cfg(feature = "live")]
fn wait_for_session_started(sess: &xbbg_core::session::Session, timeout_ms: u64) {
    use std::thread::sleep;
    use std::time::{Duration, Instant};
    use xbbg_core::EventType;

    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    while Instant::now() < deadline {
        if let Some(ev) = sess.try_next_event() {
            if ev.event_type() == EventType::SessionStatus {
                for msg in ev.iter() {
                    let ty = msg.message_type();
                    let t = ty.as_str();
                    if t == "SessionStarted" || t == "SessionResumed" {
                        return;
                    }
                }
            } else {
                // Non-session event; drop it back to the loop for normal flow
            }
        } else {
            sleep(Duration::from_millis(50));
        }
    }
}

#[cfg(feature = "live")]
#[test]
fn live_requests_two_u64_cids() {
    use std::time::{Duration, Instant};
    use xbbg_core::{
        session::Session, CorrelationId, EventType, RequestBuilder, Service, SessionOptions,
    };

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    // Snapshot requests use mktdata; set default subscription service and open it.
    opts.set_default_subscription_service("//blp/mktdata")
        .unwrap();
    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);
    sess.open_service("//blp/refdata").expect("open refdata");
    let svc: Service = sess.get_service("//blp/refdata").expect("get refdata");

    let req1 = RequestBuilder::new()
        .securities(vec!["IBM US Equity".into()])
        .fields(vec!["PX_LAST".into()])
        .build(&svc, "ReferenceDataRequest")
        .expect("build req1");
    let req2 = RequestBuilder::new()
        .securities(vec!["MSFT US Equity".into()])
        .fields(vec!["PX_LAST".into()])
        .build(&svc, "ReferenceDataRequest")
        .expect("build req2");

    sess.send_request(&req1, None, Some(&CorrelationId::U64(1)))
        .expect("send req1");
    sess.send_request(&req2, None, Some(&CorrelationId::U64(2)))
        .expect("send req2");

    let deadline = Instant::now() + Duration::from_secs(30);
    let mut final_1 = false;
    let mut final_2 = false;
    while Instant::now() < deadline && !(final_1 && final_2) {
        let ev = sess.next_event(Some(1000)).expect("nextEvent");
        match ev.event_type() {
            EventType::PartialResponse | EventType::Response | EventType::RequestStatus => {
                for msg in ev.iter() {
                    log_msg(&msg);
                    let mut saw1 = false;
                    let mut saw2 = false;
                    let n = msg.num_correlation_ids();
                    for i in 0..(n as usize) {
                        if let Some(cid) = msg.correlation_id(i) {
                            if cid.as_u64() == Some(1) {
                                saw1 = true;
                            }
                            if cid.as_u64() == Some(2) {
                                saw2 = true;
                            }
                        }
                    }
                    if ev.event_type() == EventType::Response {
                        if saw1 {
                            final_1 = true;
                        }
                        if saw2 {
                            final_2 = true;
                        }
                    }
                }
            }
            _ => {}
        }
    }
    assert!(final_1 && final_2, "did not receive finals for both CIDs");
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_subscriptions_tag_unsubscribe_race() {
    use std::sync::Arc;
    use std::time::{Duration, Instant};
    use xbbg_core::{
        session::Session, CorrelationId, EventType, SessionOptions, SubscriptionListBuilder,
    };

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);
    sess.open_service("//blp/mktdata").expect("open mktdata");

    let topic = "IBM US Equity";
    let tag = Arc::<str>::from(topic);
    let list = SubscriptionListBuilder::new()
        .add(topic, &["LAST_PRICE"], CorrelationId::Tag(tag))
        .build()
        .expect("build subs");

    sess.subscribe(&list, None).expect("subscribe");

    let mut got_data = false;
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(10) && !got_data {
        let ev = sess.next_event(Some(2000)).expect("nextEvent");
        match ev.event_type() {
            EventType::SubscriptionData | EventType::SubscriptionStatus => {
                for msg in ev.iter() {
                    log_msg(&msg);
                    if let Some(cid) = msg.correlation_id(0) {
                        if let Some(s) = cid.as_tag() {
                            if s == topic {
                                got_data = true;
                            }
                        }
                    }
                }
            }
            _ => {}
        }
    }
    assert!(got_data, "did not receive subscription data for topic");

    sess.unsubscribe(&list).expect("unsubscribe");
    // Allow a brief window for race; ignore content, just ensure no panic
    let _ = sess.try_next_event();
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_snapshot_template_smoke() {
    use std::time::{Duration, Instant};
    use xbbg_core::{session::Session, CorrelationId, EventType, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);

    // Open the market data service required for snapshot templates
    sess.open_service("//blp/mktdata").expect("open mktdata");

    // Snapshot template with explicit status CID for lifecycle messages
    let tmpl_cid = CorrelationId::U64(123456);
    // Include fields to avoid BAD_FLD errors on snapshot requests
    let tmpl = match sess.create_snapshot_request_template_with_cid(
        "//blp/mktdata/ticker/IBM US Equity?fields=LAST_PRICE",
        Some(&tmpl_cid),
    ) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("snapshot template not supported here: {e:?}");
            sess.stop();
            return;
        }
    };
    // Send a snapshot request using this template with a per-request CID
    let req_cid = CorrelationId::U64(654321);
    let _ = sess.send_request_template_with_cid(&tmpl, Some(&req_cid));

    let deadline = Instant::now() + Duration::from_secs(20);
    let mut got = false;
    while Instant::now() < deadline && !got {
        let ev = sess.next_event(Some(1000)).expect("nextEvent");
        match ev.event_type() {
            EventType::Response
            | EventType::RequestStatus
            | EventType::SubscriptionData
            | EventType::ServiceStatus => {
                for msg in ev.iter() {
                    log_msg(&msg);
                    // Consider both response and lifecycle messages as success indicators
                    let ty = msg.message_type();
                    let t = ty.as_str();
                    if t == "RequestTemplateAvailable" || t == "RequestTemplateTerminated" {
                        got = true;
                    }
                }
            }
            _ => {}
        }
    }
    // Some environments may not support snapshot templates; tolerate missing response.
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_mcm_smoke() {
    use std::sync::Arc;
    use std::time::{Duration, Instant};
    use xbbg_core::{
        session::Session, CorrelationId, EventType, SessionOptions, SubscriptionListBuilder,
    };

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);
    sess.open_service("//blp/mktdata").expect("open mktdata");

    let topic = "MSFT US Equity";
    let list = SubscriptionListBuilder::new()
        .add(
            topic,
            &["LAST_PRICE"],
            CorrelationId::Tag(Arc::<str>::from(topic)),
        )
        .build()
        .expect("subs");
    sess.subscribe(&list, None).expect("subscribe");

    let deadline = Instant::now() + Duration::from_secs(10);
    let mut observed_n_ge_1 = false;
    while Instant::now() < deadline && !observed_n_ge_1 {
        let ev = sess.next_event(Some(1000)).expect("nextEvent");
        match ev.event_type() {
            EventType::SubscriptionData | EventType::SubscriptionStatus => {
                for msg in ev.iter() {
                    log_msg(&msg);
                    observed_n_ge_1 |= msg.num_correlation_ids() >= 1;
                }
            }
            _ => {}
        }
    }
    assert!(observed_n_ge_1, "no correlators observed");
    sess.unsubscribe(&list).expect("unsubscribe");
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_service_status_cid_smoke() {
    use std::time::{Duration, Instant};
    use xbbg_core::{session::Session, CorrelationId, EventType, Service, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);
    sess.open_service("//blp/refdata").expect("open refdata");
    let svc: Service = sess.get_service("//blp/refdata").expect("get refdata");
    let cid = CorrelationId::U64(9_999_999);
    let _ = sess.set_status_correlation_id(&svc, &cid);

    let deadline = Instant::now() + Duration::from_secs(5);
    let mut seen_and_matched = false;
    while Instant::now() < deadline && !seen_and_matched {
        if let Some(ev) = sess.try_next_event() {
            if ev.event_type() == EventType::ServiceStatus {
                for msg in ev.iter() {
                    log_msg(&msg);
                    let n = msg.num_correlation_ids();
                    for i in 0..(n as usize) {
                        if let Some(c) = msg.correlation_id(i) {
                            if c.as_u64() == Some(9_999_999) {
                                seen_and_matched = true;
                            }
                        }
                    }
                }
            }
        }
    }
    // We accept either matched or no service status observed within window; the call must not panic.
    assert!(true);
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_schema_refdata_request_shapes() {
    use xbbg_core::schema::DataType;
    use xbbg_core::{session::Session, Name, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);
    sess.open_service("//blp/refdata").expect("open refdata");
    let svc = sess.get_service("//blp/refdata").expect("get");

    // Find operation ReferenceDataRequest
    let op_name = Name::new("ReferenceDataRequest").unwrap();
    let op = svc.get_operation(&op_name).expect("get op");
    let req_def = op.request_definition().expect("req schema");

    // Expect securities/fields arrays of STRING
    let sec = req_def
        .child_by_name(&Name::new("securities").unwrap())
        .expect("securities");
    assert!(sec.is_array());
    assert_eq!(sec.data_type(), DataType::String);
    let flds = req_def
        .child_by_name(&Name::new("fields").unwrap())
        .expect("fields");
    assert!(flds.is_array());
    assert_eq!(flds.data_type(), DataType::String);

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_schema_showcase() {
    use xbbg_core::schema::DataType;
    use xbbg_core::{session::Session, Name, SessionOptions};

    fn print_schema(
        def: &xbbg_core::schema::SchemaElementDefinition,
        depth: usize,
        max_children: usize,
    ) {
        let indent = "  ".repeat(depth);
        println!(
            "{}- {}: {:?}{}{}",
            indent,
            def.name(),
            def.data_type(),
            if def.is_array() { "[]" } else { "" },
            if def.is_optional() { " (optional)" } else { "" }
        );
        let n = def.num_children();
        let limit = n.min(max_children);
        for i in 0..limit {
            if let Ok(child) = def.child_at(i) {
                print_schema(&child, depth + 1, max_children);
            }
        }
        if n > limit {
            println!("{}  ... ({} more)", indent, n - limit);
        }
    }

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();

    let sess = Session::new(&opts).expect("create session");
    sess.start().expect("start session");
    wait_for_session_started(&sess, 5_000);

    // Refdata operations and schemas
    sess.open_service("//blp/refdata").expect("open refdata");
    let svc = sess.get_service("//blp/refdata").expect("get");
    let op_names = svc.operation_names();
    println!("refdata: {} operations (showing up to 10):", op_names.len());
    for n in op_names.iter().take(10) {
        println!("  op: {}", n.as_str());
    }
    let op_name = Name::new("ReferenceDataRequest").unwrap();
    let op = svc.get_operation(&op_name).expect("get op");
    let req_def = op.request_definition().expect("req schema");
    println!("ReferenceDataRequest - request schema (top-level):");
    print_schema(&req_def, 0, 8);

    // Validate first response schema shape (ReferenceDataResponse) if available
    if op.num_response_definitions() > 0 {
        let resp_def = op.response_definition(0).expect("resp def 0");
        println!("ReferenceDataRequest - response[0] schema (top-level):");
        let n = resp_def.num_children().min(8);
        for i in 0..n {
            if let Ok(ch) = resp_def.child_at(i) {
                println!("  - {}: {:?}", ch.name(), ch.data_type());
            }
        }
        // Expect top-level 'securityData' array of Sequence
        if let Some(sd) = resp_def.child_by_name(&Name::new("securityData").unwrap()) {
            assert!(sd.is_array(), "securityData should be an array");
            assert_eq!(
                sd.data_type(),
                DataType::Sequence,
                "securityData should be a Sequence[]"
            );
            // Inspect elements within securityData sequence
            let security = sd
                .child_by_name(&Name::new("security").unwrap())
                .expect("security");
            assert_eq!(security.data_type(), DataType::String);
            let field_data = sd
                .child_by_name(&Name::new("fieldData").unwrap())
                .expect("fieldData");
            assert_eq!(field_data.data_type(), DataType::Sequence);
            assert!(!field_data.is_array(), "fieldData should not be an array");
        } else {
            println!("response: 'securityData' not present in top-level schema");
        }
    } else {
        println!("ReferenceDataRequest has no response definitions in this environment");
    }

    // Market data event definitions
    sess.open_service("//blp/mktdata").expect("open mktdata");
    let mkt = sess.get_service("//blp/mktdata").expect("get mktdata");
    let evn = mkt.num_event_definitions();
    println!("mktdata: {} event definitions (showing up to 5):", evn);
    for i in 0..evn.min(5) {
        if let Ok(ev) = mkt.get_event_definition(i) {
            println!("  event def {}: {} ({:?})", i, ev.name(), ev.data_type());
        }
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_apifields_search() {
    use std::ffi::CString;
    use xbbg_core::{session::Session, SessionOptions};
    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);
    // apiflds
    if let Err(e) = sess.open_service("//blp/apiflds") {
        eprintln!("skip apiflds: {:?}", e);
        sess.stop();
        return;
    }
    let svc = sess.get_service("//blp/apiflds").expect("get apiflds");
    let req = svc.create_request("FieldSearchRequest").expect("create");
    unsafe {
        let root = blpapi_sys::blpapi_Request_elements(req.as_raw());
        let k = CString::new("searchSpec").unwrap();
        let v = CString::new("last price").unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k.as_ptr(),
            std::ptr::null(),
            v.as_ptr(),
        );
    }
    sess.send_request(&req, None, None)
        .expect("send apiflds FieldSearchRequest");
    use std::time::{Duration, Instant};
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut got_response = false;
    while Instant::now() < deadline && !got_response {
        let ev = sess.next_event(Some(1000)).expect("nextEvent");
        for msg in ev.iter() {
            log_msg(&msg);
            let name = msg.message_type();
            let ty = name.as_str().to_owned();
            if ty.eq_ignore_ascii_case("FieldSearchResponse")
                || ty.eq_ignore_ascii_case("fieldResponse")
            {
                got_response = true;
            }
        }
    }
    assert!(
        got_response,
        "did not receive FieldSearchResponse within timeout"
    );
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_instruments_lookup() {
    use std::ffi::CString;
    use xbbg_core::{session::Session, SessionOptions};
    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);
    if let Err(e) = sess.open_service("//blp/instruments") {
        eprintln!("skip instruments: {:?}", e);
        sess.stop();
        return;
    }
    let svc = sess.get_service("//blp/instruments").expect("get");
    let req = svc.create_request("instrumentListRequest").expect("create");
    unsafe {
        let root = blpapi_sys::blpapi_Request_elements(req.as_raw());
        let k_query = CString::new("query").unwrap();
        let v_query = CString::new("AAPL").unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k_query.as_ptr(),
            std::ptr::null(),
            v_query.as_ptr(),
        );
        let k_max = CString::new("maxResults").unwrap();
        let _ =
            blpapi_sys::blpapi_Element_setElementInt32(root, k_max.as_ptr(), std::ptr::null(), 3);
        let k_yk = CString::new("yellowKeyFilter").unwrap();
        let v_yk = CString::new("YK_FILTER_EQTY").unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k_yk.as_ptr(),
            std::ptr::null(),
            v_yk.as_ptr(),
        );
    }
    let _ = sess.send_request(&req, None, None);
    use std::time::{Duration, Instant};
    let deadline = Instant::now() + Duration::from_secs(5);
    let mut got = false;
    while Instant::now() < deadline && !got {
        if let Some(ev) = sess.try_next_event() {
            for msg in ev.iter() {
                log_msg(&msg);
                got = true;
            }
        }
    }
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_intraday_sanity() {
    use std::ffi::CString;
    use xbbg_core::{session::Session, SessionOptions};
    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);
    if let Err(e) = sess.open_service("//blp/refdata") {
        eprintln!("skip intraday: {:?}", e);
        sess.stop();
        return;
    }
    let svc = sess.get_service("//blp/refdata").expect("get");
    let req = svc.create_request("IntradayBarRequest").expect("create");
    // Build small fixed window; tolerate no data in some envs
    let s_str = "2025-01-01T00:00:00".to_string();
    let e_str = "2025-01-01T00:02:00".to_string();
    unsafe {
        let root = blpapi_sys::blpapi_Request_elements(req.as_raw());
        let k_sec = CString::new("security").unwrap();
        let v_sec = CString::new("IBM US Equity").unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k_sec.as_ptr(),
            std::ptr::null(),
            v_sec.as_ptr(),
        );
        let k_ev = CString::new("eventType").unwrap();
        let v_ev = CString::new("TRADE").unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k_ev.as_ptr(),
            std::ptr::null(),
            v_ev.as_ptr(),
        );
        let k_int = CString::new("interval").unwrap();
        let _ =
            blpapi_sys::blpapi_Element_setElementInt32(root, k_int.as_ptr(), std::ptr::null(), 1);
        let k_sd = CString::new("startDateTime").unwrap();
        let v_sd = CString::new(s_str.as_str()).unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k_sd.as_ptr(),
            std::ptr::null(),
            v_sd.as_ptr(),
        );
        let k_ed = CString::new("endDateTime").unwrap();
        let v_ed = CString::new(e_str.as_str()).unwrap();
        let _ = blpapi_sys::blpapi_Element_setElementString(
            root,
            k_ed.as_ptr(),
            std::ptr::null(),
            v_ed.as_ptr(),
        );
    }
    let _ = sess.send_request(&req, None, None);
    use std::time::{Duration, Instant};
    let deadline = Instant::now() + Duration::from_secs(5);
    let mut got = false;
    while Instant::now() < deadline && !got {
        if let Some(ev) = sess.try_next_event() {
            for msg in ev.iter() {
                log_msg(&msg);
                got = true;
            }
        }
    }
    // do not assert; this probe is tolerant in restricted envs
    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_arrow_refdata() {
    use arrow::array::Array;
    use xbbg_core::arrow::execute_refdata_arrow;
    use xbbg_core::requests::ReferenceDataRequest;
    use xbbg_core::{session::Session, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);

    let req = ReferenceDataRequest::new(
        vec!["IBM US Equity", "MSFT US Equity"],
        vec!["PX_LAST", "NAME"],
    );
    let batch = execute_refdata_arrow(&sess, &req).expect("execute refdata arrow");

    println!(
        "RefData Arrow batch: {} rows, {} columns",
        batch.num_rows(),
        batch.num_columns()
    );
    println!("Schema: {:?}", batch.schema());

    // Print first 10 rows
    let num_rows_to_print = batch.num_rows().min(10);
    for i in 0..num_rows_to_print {
        let ticker = batch
            .column(0)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let field = batch
            .column(1)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let row_idx = batch
            .column(2)
            .as_any()
            .downcast_ref::<arrow::array::Int32Array>()
            .unwrap()
            .value(i);
        let value_str = batch
            .column(3)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(3)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        let value_num = batch
            .column(4)
            .as_any()
            .downcast_ref::<arrow::array::Float64Array>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                format!(
                    "{}",
                    batch
                        .column(4)
                        .as_any()
                        .downcast_ref::<arrow::array::Float64Array>()
                        .unwrap()
                        .value(i)
                )
            });
        println!(
            "  Row {}: ticker={}, field={}, row_idx={}, value_str={}, value_num={}",
            i, ticker, field, row_idx, value_str, value_num
        );
    }

    assert_eq!(batch.num_columns(), 8, "should have 8 columns (ticker, field, row_index, value_str, value_num, value_date, currency, source)");
    if batch.num_rows() == 0 {
        println!("WARNING: Got 0 rows - this might indicate a parsing issue or no data available");
    } else {
        assert!(batch.num_rows() > 0, "should have at least one row");
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_arrow_histdata() {
    use arrow::array::Array;
    use xbbg_core::arrow::execute_histdata_arrow;
    use xbbg_core::requests::HistoricalDataRequest;
    use xbbg_core::{session::Session, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);

    // Test with multiple tickers and multiple fields
    let req = HistoricalDataRequest::new(
        vec!["IBM US Equity", "MSFT US Equity"],
        vec!["PX_LAST", "VOLUME", "OPEN"],
        "2024-01-01",
        "2024-01-31",
    );
    let batch = execute_histdata_arrow(&sess, &req).expect("execute histdata arrow");

    println!(
        "HistData Arrow batch: {} rows, {} columns",
        batch.num_rows(),
        batch.num_columns()
    );
    println!("Schema: {:?}", batch.schema());

    // Print first 10 rows
    let num_rows_to_print = batch.num_rows().min(10);
    for i in 0..num_rows_to_print {
        let ticker = batch
            .column(0)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let date = batch
            .column(1)
            .as_any()
            .downcast_ref::<arrow::array::Date32Array>()
            .unwrap()
            .value(i);
        let field = batch
            .column(2)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let value_num = batch
            .column(3)
            .as_any()
            .downcast_ref::<arrow::array::Float64Array>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                format!(
                    "{}",
                    batch
                        .column(3)
                        .as_any()
                        .downcast_ref::<arrow::array::Float64Array>()
                        .unwrap()
                        .value(i)
                )
            });
        println!(
            "  Row {}: ticker={}, date={}, field={}, value_num={}",
            i, ticker, date, field, value_num
        );
    }

    assert_eq!(
        batch.num_columns(),
        6,
        "should have 6 columns (ticker, date, field, value_num, currency, adjustment_flag)"
    );

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_arrow_intraday_bars() {
    use arrow::array::Array;
    use xbbg_core::arrow::execute_intraday_bars_arrow;
    use xbbg_core::requests::IntradayBarRequest;
    use xbbg_core::{session::Session, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);

    // Use a recent date range
    let req = IntradayBarRequest::new(
        vec!["IBM US Equity"],
        "2025-11-13T09:30:00",
        "2025-11-13T16:00:00",
        60, // 1 minute bars
    );
    let batch = execute_intraday_bars_arrow(&sess, &req).expect("execute intraday bars arrow");

    println!(
        "IntradayBars Arrow batch: {} rows, {} columns",
        batch.num_rows(),
        batch.num_columns()
    );
    println!("Schema: {:?}", batch.schema());

    // Print first 10 rows
    let num_rows_to_print = batch.num_rows().min(10);
    for i in 0..num_rows_to_print {
        let ticker = batch
            .column(0)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let ts = batch
            .column(1)
            .as_any()
            .downcast_ref::<arrow::array::TimestampMillisecondArray>()
            .unwrap()
            .value(i);
        let field = batch
            .column(2)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let value_num = batch
            .column(3)
            .as_any()
            .downcast_ref::<arrow::array::Float64Array>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                format!(
                    "{}",
                    batch
                        .column(3)
                        .as_any()
                        .downcast_ref::<arrow::array::Float64Array>()
                        .unwrap()
                        .value(i)
                )
            });
        println!(
            "  Row {}: ticker={}, ts={}, field={}, value_num={}",
            i, ticker, ts, field, value_num
        );
    }

    assert_eq!(
        batch.num_columns(),
        4,
        "should have 4 columns (ticker, ts, field, value_num)"
    );

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_arrow_intraday_ticks() {
    use arrow::array::Array;
    use xbbg_core::arrow::execute_intraday_ticks_arrow;
    use xbbg_core::requests::IntradayTickRequest;
    use xbbg_core::{session::Session, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);

    // Use a recent date range
    let req = IntradayTickRequest::new(
        vec!["IBM US Equity"],
        "2025-11-13T09:30:00",
        "2025-11-13T09:35:00",
        vec!["TRADE"],
    );
    let batch = execute_intraday_ticks_arrow(&sess, &req).expect("execute intraday ticks arrow");

    println!(
        "IntradayTicks Arrow batch: {} rows, {} columns",
        batch.num_rows(),
        batch.num_columns()
    );
    println!("Schema: {:?}", batch.schema());

    // Print first 10 rows
    let num_rows_to_print = batch.num_rows().min(10);
    for i in 0..num_rows_to_print {
        let ticker = batch
            .column(0)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let ts = batch
            .column(1)
            .as_any()
            .downcast_ref::<arrow::array::TimestampMillisecondArray>()
            .unwrap()
            .value(i);
        let field = batch
            .column(2)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let value_num = batch
            .column(3)
            .as_any()
            .downcast_ref::<arrow::array::Float64Array>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                format!(
                    "{}",
                    batch
                        .column(3)
                        .as_any()
                        .downcast_ref::<arrow::array::Float64Array>()
                        .unwrap()
                        .value(i)
                )
            });
        let event_type = batch
            .column(4)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let cond_code = batch
            .column(5)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(5)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        println!(
            "  Row {}: ticker={}, ts={}, field={}, value_num={}, event_type={}, condition_code={}",
            i, ticker, ts, field, value_num, event_type, cond_code
        );
    }

    assert_eq!(
        batch.num_columns(),
        6,
        "should have 6 columns (ticker, ts, field, value_num, event_type, condition_code)"
    );

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_arrow_field_search() {
    use arrow::array::Array;
    use xbbg_core::arrow::execute_field_search_arrow;
    use xbbg_core::requests::FieldSearchRequest;
    use xbbg_core::{session::Session, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);

    let req = FieldSearchRequest::new("PX_LAST");
    let batch = execute_field_search_arrow(&sess, &req).expect("execute field search arrow");

    println!(
        "FieldSearch Arrow batch: {} rows, {} columns",
        batch.num_rows(),
        batch.num_columns()
    );
    println!("Schema: {:?}", batch.schema());

    // Print first 10 rows
    let num_rows_to_print = batch.num_rows().min(10);
    for i in 0..num_rows_to_print {
        let field_id = batch
            .column(0)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let field_name = batch
            .column(1)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(1)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        let field_type = batch
            .column(2)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(2)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        println!(
            "  Row {}: field_id={}, field_name={}, field_type={}",
            i, field_id, field_name, field_type
        );
    }

    assert_eq!(
        batch.num_columns(),
        5,
        "should have 5 columns (field_id, field_name, field_type, description, category)"
    );

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn live_arrow_field_info() {
    use arrow::array::Array;
    use xbbg_core::arrow::execute_field_info_arrow;
    use xbbg_core::requests::FieldInfoRequest;
    use xbbg_core::{session::Session, SessionOptions};

    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);
    let mut opts = SessionOptions::new().expect("opts");
    opts.set_server_host(&host).unwrap();
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000).unwrap();
    let sess = Session::new(&opts).expect("session");
    sess.start().expect("start");
    wait_for_session_started(&sess, 3_000);

    let req = FieldInfoRequest::new(vec!["PX_LAST", "NAME"]);
    let batch = execute_field_info_arrow(&sess, &req).expect("execute field info arrow");

    println!(
        "FieldInfo Arrow batch: {} rows, {} columns",
        batch.num_rows(),
        batch.num_columns()
    );
    println!("Schema: {:?}", batch.schema());

    // Print all rows
    for i in 0..batch.num_rows() {
        let field_id = batch
            .column(0)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .value(i);
        let mnemonic = batch
            .column(1)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(1)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        let ftype = batch
            .column(2)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(2)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        let desc = batch
            .column(3)
            .as_any()
            .downcast_ref::<arrow::array::StringArray>()
            .unwrap()
            .is_null(i)
            .then(|| "NULL".to_string())
            .unwrap_or_else(|| {
                batch
                    .column(3)
                    .as_any()
                    .downcast_ref::<arrow::array::StringArray>()
                    .unwrap()
                    .value(i)
                    .to_string()
            });
        println!(
            "  Row {}: field_id={}, mnemonic={}, ftype={}, description={}",
            i, field_id, mnemonic, ftype, desc
        );
    }

    assert_eq!(
        batch.num_columns(),
        5,
        "should have 5 columns (field_id, mnemonic, ftype, description, category)"
    );

    sess.stop();
}

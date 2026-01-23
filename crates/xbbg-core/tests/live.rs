//! Live integration tests for xbbg-core.
//!
//! These tests require a Bloomberg connection and are gated behind the `live` feature.
//!
//! Run with: cargo test --package xbbg_core --features live -- --nocapture
//!
//! Environment variables:
//! - BLP_HOST: Bloomberg API host (default: 127.0.0.1)
//! - BLP_PORT: Bloomberg API port (default: 8194)

#![cfg(feature = "live")]

use std::time::{Duration, Instant};
use xbbg_core::{EventType, Name, Session, SessionOptions};

// ============================================================================
// Test Helpers
// ============================================================================

/// Create a session with default options.
fn create_session() -> Session {
    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("failed to create session options");
    opts.set_server_host(&host).expect("failed to set host");
    opts.set_server_port(port);
    opts.set_connect_timeout_ms(10_000)
        .expect("failed to set timeout");

    Session::new(&opts).expect("failed to create session")
}

/// Wait for session to start.
fn wait_for_session_started(sess: &Session, timeout_ms: u64) {
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);

    while Instant::now() < deadline {
        if let Some(ev) = sess.try_next_event() {
            if ev.event_type() == EventType::SessionStatus {
                for msg in ev.iter() {
                    let ty = msg.message_type();
                    let name = ty.as_str();
                    if name == "SessionStarted" || name == "SessionResumed" {
                        return;
                    }
                }
            }
        } else {
            std::thread::sleep(Duration::from_millis(50));
        }
    }
    panic!("Session did not start within {}ms", timeout_ms);
}

// ============================================================================
// Basic Connectivity Tests
// ============================================================================

#[test]
fn live_builds() {
    // Verify crate compiles with live feature
    assert!(!xbbg_core::version().is_empty());
}

#[test]
fn live_session_start_stop() {
    let sess = create_session();
    sess.start().expect("failed to start session");
    wait_for_session_started(&sess, 5000);
    sess.stop();
}

#[test]
fn live_open_refdata_service() {
    let sess = create_session();
    sess.start().expect("failed to start session");
    wait_for_session_started(&sess, 5000);

    sess.open_service("//blp/refdata")
        .expect("failed to open refdata service");
    let _svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get refdata service");

    sess.stop();
}

// ============================================================================
// Reference Data Tests
// ============================================================================

#[test]
fn live_bdp_single_field() {
    let sess = create_session();
    sess.start().expect("failed to start session");
    wait_for_session_started(&sess, 5000);

    sess.open_service("//blp/refdata")
        .expect("failed to open service");
    let svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get service");

    // Pre-intern names
    let securities = Name::get_or_intern("securities");
    let fields = Name::get_or_intern("fields");
    let security_data = Name::get_or_intern("securityData");
    let field_data = Name::get_or_intern("fieldData");
    let px_last = Name::get_or_intern("PX_LAST");

    // Create request
    let mut req = svc
        .create_request("ReferenceDataRequest")
        .expect("failed to create request");
    req.append_string(&securities, "IBM US Equity")
        .expect("failed to add security");
    req.append_string(&fields, "PX_LAST")
        .expect("failed to add field");

    // Send request
    sess.send_request(&req, None, None)
        .expect("failed to send request");

    // Get response
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut got_response = false;

    while Instant::now() < deadline && !got_response {
        if let Ok(ev) = sess.next_event(Some(1000)) {
            if ev.event_type() == EventType::Response {
                for msg in ev.iter() {
                    println!("Message type: {}", msg.message_type().as_str());

                    let root = msg.elements();
                    if let Some(sd) = root.get(&security_data) {
                        if let Some(first) = sd.get_at(0) {
                            if let Some(fd) = first.get(&field_data) {
                                if let Some(px) = fd.get(&px_last) {
                                    if let Some(value) = px.get_f64(0) {
                                        println!("PX_LAST = {}", value);
                                        assert!(value > 0.0, "PX_LAST should be positive");
                                        got_response = true;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    assert!(got_response, "Did not receive response within timeout");
    sess.stop();
}

#[test]
fn live_bdp_multiple_fields() {
    let sess = create_session();
    sess.start().expect("failed to start session");
    wait_for_session_started(&sess, 5000);

    sess.open_service("//blp/refdata")
        .expect("failed to open service");
    let svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get service");

    // Pre-intern names
    let securities = Name::get_or_intern("securities");
    let fields = Name::get_or_intern("fields");
    let security_data = Name::get_or_intern("securityData");
    let field_data = Name::get_or_intern("fieldData");
    let px_last = Name::get_or_intern("PX_LAST");
    let name_field = Name::get_or_intern("NAME");

    // Create request with multiple fields
    let mut req = svc
        .create_request("ReferenceDataRequest")
        .expect("failed to create request");
    req.append_string(&securities, "AAPL US Equity")
        .expect("failed to add security");
    req.append_string(&fields, "PX_LAST")
        .expect("failed to add field");
    req.append_string(&fields, "NAME")
        .expect("failed to add field");

    // Send request
    sess.send_request(&req, None, None)
        .expect("failed to send request");

    // Get response
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut got_px_last = false;
    let mut got_name = false;

    while Instant::now() < deadline && !(got_px_last && got_name) {
        if let Ok(ev) = sess.next_event(Some(1000)) {
            if ev.event_type() == EventType::Response {
                for msg in ev.iter() {
                    let root = msg.elements();
                    if let Some(sd) = root.get(&security_data) {
                        if let Some(first) = sd.get_at(0) {
                            if let Some(fd) = first.get(&field_data) {
                                // Extract PX_LAST (numeric)
                                if let Some(px) = fd.get(&px_last) {
                                    if let Some(value) = px.get_f64(0) {
                                        println!("PX_LAST = {}", value);
                                        got_px_last = true;
                                    }
                                }

                                // Extract NAME (string)
                                if let Some(nm) = fd.get(&name_field) {
                                    if let Some(value) = nm.get_str(0) {
                                        println!("NAME = {}", value);
                                        got_name = true;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    assert!(got_px_last, "Did not get PX_LAST");
    assert!(got_name, "Did not get NAME");
    sess.stop();
}

// ============================================================================
// Value Extraction Tests
// ============================================================================

#[test]
fn live_get_value_dynamic_extraction() {
    use xbbg_core::Value;

    let sess = create_session();
    sess.start().expect("failed to start session");
    wait_for_session_started(&sess, 5000);

    sess.open_service("//blp/refdata")
        .expect("failed to open service");
    let svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get service");

    // Pre-intern names
    let securities = Name::get_or_intern("securities");
    let fields = Name::get_or_intern("fields");
    let security_data = Name::get_or_intern("securityData");
    let field_data = Name::get_or_intern("fieldData");
    let px_last = Name::get_or_intern("PX_LAST");

    // Create request
    let mut req = svc
        .create_request("ReferenceDataRequest")
        .expect("failed to create request");
    req.append_string(&securities, "IBM US Equity")
        .expect("failed to add security");
    req.append_string(&fields, "PX_LAST")
        .expect("failed to add field");

    // Send request
    sess.send_request(&req, None, None)
        .expect("failed to send request");

    // Get response and use get_value()
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut got_response = false;

    while Instant::now() < deadline && !got_response {
        if let Ok(ev) = sess.next_event(Some(1000)) {
            if ev.event_type() == EventType::Response {
                for msg in ev.iter() {
                    let root = msg.elements();
                    if let Some(sd) = root.get(&security_data) {
                        if let Some(first) = sd.get_at(0) {
                            if let Some(fd) = first.get(&field_data) {
                                if let Some(px) = fd.get(&px_last) {
                                    // Use get_value() for dynamic extraction
                                    if let Some(value) = px.get_value(0) {
                                        println!("get_value() returned: {:?}", value);
                                        match value {
                                            Value::Float64(v) => {
                                                println!("Extracted as Float64: {}", v);
                                                assert!(v > 0.0);
                                                got_response = true;
                                            }
                                            other => {
                                                panic!("Expected Float64, got {:?}", other);
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
    }

    assert!(got_response, "Did not receive response within timeout");
    sess.stop();
}

// ============================================================================
// Name Cache Tests
// ============================================================================

#[test]
fn live_name_cache_works() {
    // Clear cache first
    xbbg_core::clear_name_cache();
    assert_eq!(xbbg_core::name_cache_size(), 0);

    // Intern some names
    let _n1 = Name::get_or_intern("PX_LAST");
    let _n2 = Name::get_or_intern("PX_OPEN");
    let _n3 = Name::get_or_intern("PX_HIGH");

    assert_eq!(xbbg_core::name_cache_size(), 3);

    // Second call should use cache (same size)
    let _n1_again = Name::get_or_intern("PX_LAST");
    assert_eq!(xbbg_core::name_cache_size(), 3);

    // Clear and verify
    xbbg_core::clear_name_cache();
    assert_eq!(xbbg_core::name_cache_size(), 0);
}

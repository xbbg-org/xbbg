//! Unit tests for xbbg-core.
//!
//! These tests don't require a Bloomberg connection.

use std::sync::Arc;

use crate::correlation::CorrelationId;

// =========================================================================
// Correlation ID tests
// =========================================================================

#[test]
fn test_correlation_id_next_returns_unique_ids() {
    let id1 = CorrelationId::next();
    let id2 = CorrelationId::next();
    let id3 = CorrelationId::next();

    // Each call should return a different ID
    assert_ne!(id1, id2);
    assert_ne!(id2, id3);
    assert_ne!(id1, id3);
}

#[test]
fn test_correlation_id_next_is_sequential() {
    let id1 = CorrelationId::next();
    let id2 = CorrelationId::next();

    if let (CorrelationId::U64(v1), CorrelationId::U64(v2)) = (&id1, &id2) {
        assert_eq!(*v2, *v1 + 1, "IDs should be sequential");
    } else {
        panic!("Expected U64 variants");
    }
}

#[test]
fn test_correlation_id_u64_as_u64() {
    let id = CorrelationId::U64(42);
    assert_eq!(id.as_u64(), Some(42));
    assert_eq!(id.as_tag(), None);
}

#[test]
fn test_correlation_id_tag_as_tag() {
    let id = CorrelationId::Tag(Arc::from("my-request"));
    assert_eq!(id.as_tag(), Some("my-request"));
    assert_eq!(id.as_u64(), None);
}

#[test]
fn test_correlation_id_equality() {
    let id1 = CorrelationId::U64(100);
    let id2 = CorrelationId::U64(100);
    let id3 = CorrelationId::U64(200);

    assert_eq!(id1, id2);
    assert_ne!(id1, id3);

    let tag1 = CorrelationId::Tag(Arc::from("test"));
    let tag2 = CorrelationId::Tag(Arc::from("test"));
    let tag3 = CorrelationId::Tag(Arc::from("other"));

    assert_eq!(tag1, tag2);
    assert_ne!(tag1, tag3);
}

#[test]
fn test_correlation_id_clone() {
    let id = CorrelationId::U64(999);
    let cloned = id.clone();
    assert_eq!(id, cloned);

    let tag = CorrelationId::Tag(Arc::from("cloneable"));
    let cloned_tag = tag.clone();
    assert_eq!(tag, cloned_tag);
}

#[test]
fn test_correlation_id_debug() {
    let id = CorrelationId::U64(123);
    let debug_str = format!("{:?}", id);
    assert!(debug_str.contains("U64"));
    assert!(debug_str.contains("123"));

    let tag = CorrelationId::Tag(Arc::from("debug-test"));
    let debug_str = format!("{:?}", tag);
    assert!(debug_str.contains("Tag"));
    assert!(debug_str.contains("debug-test"));
}

// =========================================================================
// Low-level intraday bar tests (require Bloomberg connection)
// =========================================================================

#[cfg(feature = "live")]
mod live_tests {
    use crate::arrow::execute_intraday_bars_arrow;
    use crate::requests::IntradayBarRequest;
    use crate::session::Session;
    use crate::SessionOptions;

    fn create_session() -> Session {
        let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".into());
        let port: u16 = std::env::var("BLP_PORT")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(8194);

        let mut opts = SessionOptions::new().expect("session options");
        opts.set_server_host(&host).expect("set host");
        opts.set_server_port(port);
        let session = Session::new(&opts).expect("session new");
        session.start().expect("session start");
        session
    }

    #[test]
    fn test_bdib_low_level() {
        let session = create_session();

        // Use December 23, 2025 (a trading day)
        let req = IntradayBarRequest::new(
            vec!["IBM US Equity"],
            "2025-12-18T14:00:00",
            "2025-12-18T15:00:00",
            5,
        );

        println!("Request: {:?}", req);

        let batch = execute_intraday_bars_arrow(&session, &req).expect("execute_intraday_bars_arrow");

        println!(
            "Result: {} rows, {} columns",
            batch.num_rows(),
            batch.num_columns()
        );
        for field in batch.schema().fields() {
            println!("  - {} ({:?})", field.name(), field.data_type());
        }

        if batch.num_rows() > 0 {
            println!("First row data available");
        } else {
            println!("No data returned (might be outside trading hours)");
        }
    }

    #[test]
    fn test_field_search_low_level() {
        use crate::arrow::execute_field_search_arrow;
        use crate::requests::FieldSearchRequest;
        
        let session = create_session();

        let req = FieldSearchRequest::new("last price");

        println!("Field Search Request: {:?}", req);

        let batch = execute_field_search_arrow(&session, &req).expect("execute_field_search_arrow");

        println!(
            "Result: {} rows, {} columns",
            batch.num_rows(),
            batch.num_columns()
        );
        for field in batch.schema().fields() {
            println!("  - {} ({:?})", field.name(), field.data_type());
        }
        
        // Print first few rows
        use arrow::array::{Array, StringArray};
        if batch.num_rows() > 0 {
            let field_ids = batch.column(0).as_any().downcast_ref::<StringArray>().unwrap();
            let field_names = batch.column(1).as_any().downcast_ref::<StringArray>().unwrap();
            for i in 0..batch.num_rows().min(5) {
                println!("  {} -> {}", 
                    field_ids.value(i),
                    field_names.value(i)
                );
            }
        }
    }

    #[test]
    fn test_field_types_enumeration() {
        use crate::arrow::execute_field_search_arrow;
        use crate::requests::FieldSearchRequest;
        use std::collections::HashSet;

        let session = create_session();
        let req = FieldSearchRequest::new("price");
        let batch = execute_field_search_arrow(&session, &req).expect("field search");

        use arrow::array::{Array, StringArray};
        let field_types = batch.column(2).as_any().downcast_ref::<StringArray>().unwrap();

        let mut unique_types: HashSet<String> = HashSet::new();
        for i in 0..batch.num_rows() {
            if !field_types.is_null(i) {
                unique_types.insert(field_types.value(i).to_string());
            }
        }

        println!("\n=== Unique Field Types ===");
        let mut sorted: Vec<_> = unique_types.iter().collect();
        sorted.sort();
        for t in &sorted {
            println!("  {}", t);
        }

        // Show sample of each type
        println!("\n=== Sample Fields by Type ===");
        let field_names = batch.column(1).as_any().downcast_ref::<StringArray>().unwrap();
        let descriptions = batch.column(3).as_any().downcast_ref::<StringArray>().unwrap();

        let mut seen_types: HashSet<String> = HashSet::new();
        for i in 0..batch.num_rows() {
            if !field_types.is_null(i) {
                let ftype = field_types.value(i).to_string();
                if !seen_types.contains(&ftype) {
                    seen_types.insert(ftype.clone());
                    let name = if field_names.is_null(i) { "?" } else { field_names.value(i) };
                    let desc = if descriptions.is_null(i) { "" } else { descriptions.value(i) };
                    println!("  {:12} -> {:30} ({})", ftype, name, desc);
                }
            }
        }
    }

    /// Low-level BDP timing test - measures pure Bloomberg SDK round-trip time.
    ///
    /// This bypasses all async machinery (no Engine, no pump, no tokio).
    /// It measures:
    /// - open_service time
    /// - request build time
    /// - send_request time
    /// - PURE Bloomberg network round-trip (from send to response event)
    /// - Arrow conversion time
    #[test]
    fn test_bdp_timing_low_level() {
        use crate::arrow::execute_refdata_arrow;
        use crate::requests::ReferenceDataRequest;
        use std::time::Instant;

        println!("\n=== Low-Level BDP Timing Test ===\n");

        // Measure session creation
        let t0 = Instant::now();
        let session = create_session();
        let session_time = t0.elapsed();
        println!("Session create + start: {:?}", session_time);

        // Warmup request
        println!("\n--- Warmup Request ---");
        let req = ReferenceDataRequest {
            tickers: vec!["IBM US Equity".into()],
            fields: vec!["PX_LAST".into()],
            overrides: vec![],
            label: None,
        };
        let _ = execute_refdata_arrow(&session, &req);

        // Timed requests
        println!("\n--- Timed Requests (5 iterations) ---");
        let mut times = Vec::new();

        for i in 0..5 {
            let req = ReferenceDataRequest {
                tickers: vec!["IBM US Equity".into()],
                fields: vec!["PX_LAST".into()],
                overrides: vec![],
                label: None,
            };

            let t = Instant::now();
            let batch = execute_refdata_arrow(&session, &req).expect("execute_refdata_arrow");
            let elapsed = t.elapsed();
            times.push(elapsed);

            println!(
                "  Request {}: {:?} ({} rows)",
                i + 1,
                elapsed,
                batch.num_rows()
            );
        }

        // Statistics
        let total: std::time::Duration = times.iter().sum();
        let avg = total / times.len() as u32;
        let min = times.iter().min().unwrap();
        let max = times.iter().max().unwrap();

        println!("\n--- Summary ---");
        println!("  Average: {:?}", avg);
        println!("  Min:     {:?}", min);
        println!("  Max:     {:?}", max);
        println!("\nThis is the pure Bloomberg SDK time (no async, no pump).");
    }

    /// Even lower-level timing - measure each step separately.
    #[test]
    fn test_bdp_timing_breakdown() {
        use crate::{CorrelationId, EventType, RequestBuilder};
        use std::time::Instant;

        println!("\n=== BDP Timing Breakdown ===\n");

        let session = create_session();

        // 1. Measure open_service
        let t = Instant::now();
        session.open_service("//blp/refdata").expect("open_service");
        println!("open_service: {:?}", t.elapsed());

        // 2. Measure get_service
        let t = Instant::now();
        let service = session.get_service("//blp/refdata").expect("get_service");
        println!("get_service:  {:?}", t.elapsed());

        // 3. Measure request build
        let t = Instant::now();
        let request = RequestBuilder::new()
            .securities(vec!["IBM US Equity".into()])
            .fields(vec!["PX_LAST".into()])
            .build(&service, "ReferenceDataRequest")
            .expect("build request");
        println!("build_request: {:?}", t.elapsed());

        // 4. Measure send_request
        let cid = CorrelationId::next();
        let t = Instant::now();
        session.send_request(&request, None, Some(&cid)).expect("send_request");
        let send_time = t.elapsed();
        println!("send_request: {:?}", send_time);

        // 5. Measure event loop until Response
        let t = Instant::now();
        let mut response_received = false;
        let mut poll_count = 0;
        let mut partial_count = 0;

        while !response_received {
            poll_count += 1;
            match session.next_event(Some(1000)) {
                Ok(ev) => {
                    match ev.event_type() {
                        EventType::PartialResponse => {
                            partial_count += 1;
                        }
                        EventType::Response => {
                            response_received = true;
                        }
                        EventType::SessionStatus | EventType::ServiceStatus => {
                            // Admin messages, continue
                        }
                        _ => {}
                    }
                }
                Err(_) => {
                    // Timeout, keep polling
                }
            }
        }
        let network_time = t.elapsed();

        println!("\n--- Network Round-Trip ---");
        println!("Pure network time: {:?}", network_time);
        println!("Poll iterations:   {}", poll_count);
        println!("Partial responses: {}", partial_count);
        println!("\nThis is the PURE Bloomberg network latency.");
        println!("(from send_request return to Response event)");
    }
}

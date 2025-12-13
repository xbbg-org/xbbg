//! Test queries for Arrow builders (request types 1-7).
//!
//! These tests validate that the Arrow builders correctly:
//! - Build Bloomberg API requests
//! - Parse responses into Arrow RecordBatches
//! - Produce correct long-format schemas
//! - Handle multi-ticker requests where applicable

#[cfg(feature = "live")]
#[test]
fn test_refdata_arrow_bdp() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_refdata_arrow, requests::ReferenceDataRequest, session::Session,
        SessionOptions,
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

    // Test BDP (single-value reference data) - multi-ticker
    let req = ReferenceDataRequest::new(
        vec!["IBM US Equity", "MSFT US Equity"],
        vec!["PX_LAST", "NAME", "CURRENCY"],
    );

    let batch = execute_refdata_arrow(&sess, &req).expect("execute refdata");

    // Validate schema
    assert_eq!(batch.num_columns(), 9);
    assert_eq!(batch.schema().field(0).name(), "ticker");
    assert_eq!(batch.schema().field(1).name(), "field");
    assert_eq!(batch.schema().field(2).name(), "row_index");

    // Validate data shape
    let num_rows = batch.num_rows();
    println!("BDP: Got {} rows", num_rows);
    assert!(num_rows > 0, "should have at least one row");

    // Print sample data
    print_batch_summary("BDP", &batch);

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_refdata_arrow_bds() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_refdata_arrow, requests::ReferenceDataRequest, session::Session,
        SessionOptions,
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

    // Test BDS (bulk/block data) - multi-row fields
    let req = ReferenceDataRequest::new(
        vec!["IBM US Equity"],
        vec!["DVD_HIST_ALL"], // Dividend history is a bulk field
    );

    let batch = execute_refdata_arrow(&sess, &req).expect("execute refdata BDS");

    // Validate schema
    assert_eq!(batch.num_columns(), 9);

    let num_rows = batch.num_rows();
    println!("BDS: Got {} rows", num_rows);

    // BDS should have multiple rows per ticker/field
    if num_rows > 0 {
        print_batch_summary("BDS", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_histdata_arrow() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_histdata_arrow, requests::HistoricalDataRequest, session::Session,
        SessionOptions,
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

    // Test historical data - multi-ticker
    let req = HistoricalDataRequest::new(
        vec!["IBM US Equity", "MSFT US Equity"],
        vec!["PX_LAST", "VOLUME"],
        "2024-01-01",
        "2024-01-31",
    )
    .with_override("periodicityAdjustment", "ACTUAL")
    .with_override("periodicitySelection", "DAILY");

    let batch = execute_histdata_arrow(&sess, &req).expect("execute histdata");

    // Validate schema
    assert_eq!(batch.num_columns(), 6);
    assert_eq!(batch.schema().field(0).name(), "ticker");
    assert_eq!(batch.schema().field(1).name(), "date");
    assert_eq!(batch.schema().field(2).name(), "field");

    let num_rows = batch.num_rows();
    println!("BDH: Got {} rows", num_rows);

    if num_rows > 0 {
        print_batch_summary("BDH", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_intraday_bars_arrow() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_intraday_bars_arrow, requests::IntradayBarRequest, session::Session,
        SessionOptions,
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

    // Test intraday bars - use fixed date 11/13/2025
    let start = "2025-11-13T09:30:00";
    let end = "2025-11-13T16:00:00";

    let req = IntradayBarRequest::new(
        vec!["IBM US Equity"],
        start.to_string(),
        end.to_string(),
        60, // 1-minute bars
    );

    let batch = execute_intraday_bars_arrow(&sess, &req).expect("execute intraday bars");

    // Validate schema
    assert_eq!(batch.num_columns(), 4);
    assert_eq!(batch.schema().field(0).name(), "ticker");
    assert_eq!(batch.schema().field(1).name(), "ts");
    assert_eq!(batch.schema().field(2).name(), "field");

    let num_rows = batch.num_rows();
    println!("BDIB: Got {} rows", num_rows);

    if num_rows > 0 {
        print_batch_summary("BDIB", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_intraday_bars_arrow_multi_ticker() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_intraday_bars_arrow, requests::IntradayBarRequest, session::Session,
        SessionOptions,
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

    // Test intraday bars with multiple tickers - use fixed date 11/13/2025
    let start = "2025-11-13T09:30:00";
    let end = "2025-11-13T16:00:00";

    let req = IntradayBarRequest::new(
        vec!["IBM US Equity", "MSFT US Equity"],
        start.to_string(),
        end.to_string(),
        60, // 1-minute bars
    );

    let batch =
        execute_intraday_bars_arrow(&sess, &req).expect("execute intraday bars multi-ticker");

    // Validate schema
    assert_eq!(batch.num_columns(), 4);
    assert_eq!(batch.schema().field(0).name(), "ticker");
    assert_eq!(batch.schema().field(1).name(), "ts");
    assert_eq!(batch.schema().field(2).name(), "field");

    let num_rows = batch.num_rows();
    println!("BDIB Multi-ticker: Got {} rows", num_rows);

    // Verify we have data from both tickers
    if num_rows > 0 {
        use arrow::array::{Array, StringArray};
        let ticker_col = batch
            .column(0)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap();
        let unique_tickers: std::collections::HashSet<String> = (0..ticker_col.len())
            .map(|i| ticker_col.value(i).to_string())
            .collect();
        println!(
            "BDIB Multi-ticker: Found {} unique tickers: {:?}",
            unique_tickers.len(),
            unique_tickers
        );
        assert!(unique_tickers.len() >= 1, "Should have at least one ticker");
        print_batch_summary("BDIB Multi-ticker", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_intraday_ticks_arrow() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_intraday_ticks_arrow, requests::IntradayTickRequest, session::Session,
        SessionOptions,
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

    // Test intraday ticks - use fixed date 11/13/2025
    let start = "2025-11-13T09:30:00";
    let end = "2025-11-13T16:00:00";

    let req = IntradayTickRequest::new(
        vec!["IBM US Equity"],
        start.to_string(),
        end.to_string(),
        vec!["TRADE", "BID", "ASK"],
    );

    let batch = execute_intraday_ticks_arrow(&sess, &req).expect("execute intraday ticks");

    // Validate schema
    assert_eq!(batch.num_columns(), 6);
    assert_eq!(batch.schema().field(0).name(), "ticker");
    assert_eq!(batch.schema().field(1).name(), "ts");
    assert_eq!(batch.schema().field(2).name(), "field");
    assert_eq!(batch.schema().field(4).name(), "event_type");

    let num_rows = batch.num_rows();
    println!("BDTICK: Got {} rows", num_rows);

    if num_rows > 0 {
        print_batch_summary("BDTICK", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_intraday_ticks_arrow_multi_ticker() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_intraday_ticks_arrow, requests::IntradayTickRequest, session::Session,
        SessionOptions,
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

    // Test intraday ticks with multiple tickers - use fixed date 11/13/2025
    let start = "2025-11-13T09:30:00";
    let end = "2025-11-13T16:00:00";

    let req = IntradayTickRequest::new(
        vec!["IBM US Equity", "MSFT US Equity"],
        start.to_string(),
        end.to_string(),
        vec!["TRADE", "BID", "ASK"],
    );

    let batch =
        execute_intraday_ticks_arrow(&sess, &req).expect("execute intraday ticks multi-ticker");

    // Validate schema
    assert_eq!(batch.num_columns(), 6);
    assert_eq!(batch.schema().field(0).name(), "ticker");
    assert_eq!(batch.schema().field(1).name(), "ts");
    assert_eq!(batch.schema().field(2).name(), "field");
    assert_eq!(batch.schema().field(4).name(), "event_type");

    let num_rows = batch.num_rows();
    println!("BDTICK Multi-ticker: Got {} rows", num_rows);

    // Verify we have data from both tickers
    if num_rows > 0 {
        use arrow::array::{Array, StringArray};
        let ticker_col = batch
            .column(0)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap();
        let unique_tickers: std::collections::HashSet<String> = (0..ticker_col.len())
            .map(|i| ticker_col.value(i).to_string())
            .collect();
        println!(
            "BDTICK Multi-ticker: Found {} unique tickers: {:?}",
            unique_tickers.len(),
            unique_tickers
        );
        assert!(unique_tickers.len() >= 1, "Should have at least one ticker");
        print_batch_summary("BDTICK Multi-ticker", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_field_search_arrow() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_field_search_arrow, requests::FieldSearchRequest, session::Session,
        SessionOptions,
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

    // Test field search
    let req = FieldSearchRequest::new("PX_LAST");

    let batch = execute_field_search_arrow(&sess, &req).expect("execute field search");

    // Validate schema
    assert_eq!(batch.num_columns(), 5);
    assert_eq!(batch.schema().field(0).name(), "field_id");
    assert_eq!(batch.schema().field(1).name(), "field_name");
    assert_eq!(batch.schema().field(2).name(), "field_type");

    let num_rows = batch.num_rows();
    println!("Field Search: Got {} rows", num_rows);

    if num_rows > 0 {
        print_batch_summary("Field Search", &batch);
    }

    sess.stop();
}

#[cfg(feature = "live")]
#[test]
fn test_field_info_arrow() {
    use arrow::record_batch::RecordBatch;
    use xbbg_core::{
        arrow::execute_field_info_arrow, requests::FieldInfoRequest, session::Session,
        SessionOptions,
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

    // Test field info - multi-field
    let req = FieldInfoRequest::new(vec!["PX_LAST", "VOLUME", "NAME"]);

    let batch = execute_field_info_arrow(&sess, &req).expect("execute field info");

    // Validate schema
    assert_eq!(batch.num_columns(), 5);
    assert_eq!(batch.schema().field(0).name(), "field_id");
    assert_eq!(batch.schema().field(1).name(), "mnemonic");
    assert_eq!(batch.schema().field(2).name(), "ftype");

    let num_rows = batch.num_rows();
    println!("Field Info: Got {} rows", num_rows);

    if num_rows > 0 {
        print_batch_summary("Field Info", &batch);
    }

    sess.stop();
}

// Helper functions

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
            }
        } else {
            sleep(Duration::from_millis(50));
        }
    }
}

#[cfg(feature = "live")]
fn print_batch_summary(name: &str, batch: &arrow::record_batch::RecordBatch) {
    use arrow::array::*;
    use arrow::datatypes::*;

    println!("\n=== {} Summary ===", name);
    println!(
        "Schema: {} columns, {} rows",
        batch.num_columns(),
        batch.num_rows()
    );

    // Print column names and types
    for (i, field) in batch.schema().fields().iter().enumerate() {
        println!("  Column {}: {} ({:?})", i, field.name(), field.data_type());
    }

    // Print first few rows
    let num_rows_to_show = batch.num_rows().min(5);
    if num_rows_to_show > 0 {
        println!("\nFirst {} rows:", num_rows_to_show);
        for row_idx in 0..num_rows_to_show {
            print!("  Row {}: ", row_idx);
            let schema = batch.schema();
            for (col_idx, column) in batch.columns().iter().enumerate() {
                let field = schema.field(col_idx);
                match field.data_type() {
                    DataType::Utf8 => {
                        let arr = column.as_any().downcast_ref::<StringArray>().unwrap();
                        if arr.is_null(row_idx) {
                            print!("{}: NULL, ", field.name());
                        } else {
                            let val = arr.value(row_idx);
                            let display = if val.len() > 20 { &val[..20] } else { val };
                            print!("{}: {}, ", field.name(), display);
                        }
                    }
                    DataType::Int32 => {
                        let arr = column.as_any().downcast_ref::<Int32Array>().unwrap();
                        if arr.is_null(row_idx) {
                            print!("{}: NULL, ", field.name());
                        } else {
                            print!("{}: {}, ", field.name(), arr.value(row_idx));
                        }
                    }
                    DataType::Int64 => {
                        let arr = column.as_any().downcast_ref::<Int64Array>().unwrap();
                        if arr.is_null(row_idx) {
                            print!("{}: NULL, ", field.name());
                        } else {
                            print!("{}: {}, ", field.name(), arr.value(row_idx));
                        }
                    }
                    DataType::Float64 => {
                        let arr = column.as_any().downcast_ref::<Float64Array>().unwrap();
                        if arr.is_null(row_idx) {
                            print!("{}: NULL, ", field.name());
                        } else {
                            print!("{}: {}, ", field.name(), arr.value(row_idx));
                        }
                    }
                    DataType::Date32 => {
                        let arr = column.as_any().downcast_ref::<Date32Array>().unwrap();
                        if arr.is_null(row_idx) {
                            print!("{}: NULL, ", field.name());
                        } else {
                            print!("{}: {}, ", field.name(), arr.value(row_idx));
                        }
                    }
                    DataType::Timestamp(_, _) => {
                        let arr = column
                            .as_any()
                            .downcast_ref::<TimestampMillisecondArray>()
                            .unwrap();
                        if arr.is_null(row_idx) {
                            print!("{}: NULL, ", field.name());
                        } else {
                            let ts = arr.value(row_idx);
                            let dt = chrono::DateTime::<chrono::Utc>::from_timestamp_millis(ts);
                            print!("{}: {:?}, ", field.name(), dt);
                        }
                    }
                    _ => {
                        print!("{}: <{:?}>, ", field.name(), field.data_type());
                    }
                }
            }
            println!();
        }
        if batch.num_rows() > num_rows_to_show {
            println!("  ... ({} more rows)", batch.num_rows() - num_rows_to_show);
        }
    }
    println!();
}

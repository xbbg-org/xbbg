//! Cached message parsing benchmark.
//!
//! This benchmark isolates CPU-bound parsing from network latency by:
//! 1. Making ONE network request to get real Bloomberg data
//! 2. Caching the event in memory
//! 3. Parsing the cached data thousands of times
//!
//! Run:
//!   cargo bench --package xbbg-bench --bench parse_cached

use std::time::Instant;
use xbbg_bench::{env_iterations, open_service, setup_session, FieldNames};
use xbbg_core::Event;

/// Fetch a BDP response and return the event (keeps data in memory).
fn fetch_bdp_response(
    sess: &xbbg_core::Session,
    names: &FieldNames,
    tickers: &[&str],
    fields: &[&str],
) -> Event {
    let svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get service");
    let mut req = svc
        .create_request("ReferenceDataRequest")
        .expect("failed to create request");

    for ticker in tickers {
        req.append_string(&names.securities, ticker)
            .expect("failed to add security");
    }
    for field in fields {
        req.append_string(&names.fields, field)
            .expect("failed to add field");
    }

    sess.send_request(&req, None, None)
        .expect("failed to send request");

    // Wait for Response event
    loop {
        if let Ok(ev) = sess.next_event(Some(10000)) {
            if ev.event_type() == xbbg_core::EventType::Response {
                return ev;
            }
        }
    }
}

/// Parse all fields from cached event - the hot path we're profiling.
/// BASELINE: Uses N separate get(&name) lookups per security.
#[inline(never)]
fn parse_all_fields(event: &Event, names: &FieldNames) -> (usize, usize) {
    let mut securities_parsed = 0;
    let mut fields_extracted = 0;

    for msg in event.messages() {
        let root = msg.elements();

        if let Some(security_data) = root.get(&names.security_data) {
            for i in 0..security_data.len() {
                if let Some(sec) = security_data.get_element(i) {
                    securities_parsed += 1;

                    // Get security ticker
                    let _ticker = sec.get(&names.security).and_then(|e| e.get_str(0));

                    // Get field data
                    if let Some(fd) = sec.get(&names.field_data) {
                        // Extract all fields - 10 separate get() calls
                        if fd.get(&names.px_last).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd.get(&names.px_open).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd.get(&names.px_high).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd.get(&names.px_low).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd.get(&names.volume).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd
                            .get(&names.cur_mkt_cap)
                            .and_then(|e| e.get_f64(0))
                            .is_some()
                        {
                            fields_extracted += 1;
                        }
                        if fd
                            .get(&names.eqy_weighted_avg_px)
                            .and_then(|e| e.get_f64(0))
                            .is_some()
                        {
                            fields_extracted += 1;
                        }
                        if fd.get(&names.px_bid).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd.get(&names.px_ask).and_then(|e| e.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                        if fd
                            .get(&names.last_trade)
                            .and_then(|e| e.get_str(0))
                            .is_some()
                        {
                            fields_extracted += 1;
                        }
                    }
                }
            }
        }
    }

    (securities_parsed, fields_extracted)
}

/// OPTIMIZED V1: Iterate children once instead of N separate lookups.
/// From exploration/ULTIMATE_OPTIMIZATION_GUIDE.md
#[inline(never)]
fn parse_all_fields_optimized(event: &Event, names: &FieldNames) -> (usize, usize) {
    let mut securities_parsed = 0;
    let mut fields_extracted = 0;

    for msg in event.messages() {
        let root = msg.elements();

        if let Some(security_data) = root.get(&names.security_data) {
            let num_securities = security_data.len();

            for i in 0..num_securities {
                if let Some(sec) = security_data.get_element(i) {
                    securities_parsed += 1;

                    // Get ticker - use unchecked for known ASCII
                    let _ticker = sec
                        .get(&names.security)
                        .and_then(|e| unsafe { e.get_str_unchecked(0) });

                    if let Some(fd) = sec.get(&names.field_data) {
                        // OPTIMIZATION: Use name_eq() instead of name() - avoids
                        // blpapi_Name_duplicate + blpapi_Name_destroy per field!
                        for field in fd.children() {
                            // Use name_eq for O(1) pointer comparison (1 FFI call vs 3)
                            if field.name_eq(&names.px_last)
                                || field.name_eq(&names.px_open)
                                || field.name_eq(&names.px_high)
                                || field.name_eq(&names.px_low)
                                || field.name_eq(&names.volume)
                                || field.name_eq(&names.cur_mkt_cap)
                                || field.name_eq(&names.eqy_weighted_avg_px)
                                || field.name_eq(&names.px_bid)
                                || field.name_eq(&names.px_ask)
                            {
                                if field.get_f64(0).is_some() {
                                    fields_extracted += 1;
                                }
                            } else if field.name_eq(&names.last_trade)
                                && unsafe { field.get_str_unchecked(0) }.is_some()
                            {
                                fields_extracted += 1;
                            }
                        }
                    }
                }
            }
        }
    }

    (securities_parsed, fields_extracted)
}

/// OPTIMIZED V2: Skip name comparison entirely - just extract by datatype.
/// If we only care about counting fields (not which ones), this is fastest.
#[inline(never)]
fn parse_all_fields_by_datatype(event: &Event, names: &FieldNames) -> (usize, usize) {
    let mut securities_parsed = 0;
    let mut fields_extracted = 0;

    for msg in event.messages() {
        let root = msg.elements();

        if let Some(security_data) = root.get(&names.security_data) {
            for i in 0..security_data.len() {
                if let Some(sec) = security_data.get_element(i) {
                    securities_parsed += 1;

                    // Skip ticker for this benchmark

                    if let Some(fd) = sec.get(&names.field_data) {
                        // HYPER-OPTIMIZED: Just iterate and extract by datatype
                        // No name lookup, no name comparison
                        for j in 0..fd.num_children() {
                            if let Some(field) = fd.get_at(j) {
                                // Use datatype() (single FFI call) to dispatch
                                let dtype = field.datatype();
                                match dtype {
                                    // Float64 = 7, Int64 = 5, Int32 = 4
                                    xbbg_core::DataType::Float64
                                    | xbbg_core::DataType::Int64
                                    | xbbg_core::DataType::Int32 => {
                                        if field.get_f64(0).is_some() {
                                            fields_extracted += 1;
                                        }
                                    }
                                    // String = 8
                                    xbbg_core::DataType::String => {
                                        if unsafe { field.get_str_unchecked(0) }.is_some() {
                                            fields_extracted += 1;
                                        }
                                    }
                                    _ => {}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    (securities_parsed, fields_extracted)
}

/// OPTIMIZED V3: Unchecked iterators - skip per-element error checks.
#[inline(never)]
fn parse_all_fields_unchecked(event: &Event, names: &FieldNames) -> (usize, usize) {
    // Use unchecked methods for validated paths

    let mut securities_parsed = 0;
    let mut fields_extracted = 0;

    for msg in event.messages() {
        let root = msg.elements();

        if let Some(security_data) = root.get(&names.security_data) {
            // Use values() iterator for security array
            for sec in security_data.values() {
                securities_parsed += 1;

                if let Some(fd) = sec.get(&names.field_data) {
                    // Use children() for field iteration
                    for field in fd.children() {
                        // Direct extraction
                        if field.get_f64(0).is_some() {
                            fields_extracted += 1;
                        }
                    }
                }
            }
        }
    }

    (securities_parsed, fields_extracted)
}

/// OPTIMIZED V4: Maximum speed - column-driven extraction (only requested fields).
/// Instead of iterating all fields, directly get() only the ones we need.
#[inline(never)]
fn parse_all_fields_max_speed(event: &Event, names: &FieldNames) -> (usize, usize) {
    let mut securities_parsed = 0;
    let mut fields_extracted = 0;

    // Pre-built list of numeric field names
    let numeric_fields = [
        &names.px_last,
        &names.px_open,
        &names.px_high,
        &names.px_low,
        &names.volume,
        &names.cur_mkt_cap,
        &names.eqy_weighted_avg_px,
        &names.px_bid,
        &names.px_ask,
    ];

    for msg in event.messages() {
        let root = msg.elements();

        if let Some(security_data) = root.get(&names.security_data) {
            for sec in security_data.values() {
                securities_parsed += 1;

                if let Some(fd) = sec.get(&names.field_data) {
                    // COLUMN-DRIVEN: Only get() the fields we need (9 lookups vs iterating all)
                    for field_name in &numeric_fields {
                        if fd.get(field_name).and_then(|f| f.get_f64(0)).is_some() {
                            fields_extracted += 1;
                        }
                    }
                    // String field
                    if fd
                        .get(&names.last_trade)
                        .and_then(|f| unsafe { f.get_str_unchecked(0) })
                        .is_some()
                    {
                        fields_extracted += 1;
                    }
                }
            }
        }
    }

    (securities_parsed, fields_extracted)
}

/// OPTIMIZED V5: Minimal FFI - unchecked everywhere, no Option overhead.
/// Uses unsafe to skip all validation once structure is known.
#[inline(never)]
fn parse_all_fields_minimal_ffi(event: &Event, names: &FieldNames) -> (usize, usize) {
    let mut securities_parsed = 0;
    let mut fields_extracted = 0;

    for msg in event.messages() {
        let root = msg.elements();

        // We know the structure: root -> securityData[] -> security{fieldData{...}}
        if let Some(security_data) = root.get(&names.security_data) {
            let num_secs = security_data.len();
            for i in 0..num_secs {
                // Use get_element (getValueAsElement) not get_at (getElementAt)
                if let Some(sec) = security_data.get_element(i) {
                    securities_parsed += 1;

                    if let Some(fd) = sec.get(&names.field_data) {
                        let num_fields = fd.num_children();
                        // Iterate with raw index, use unchecked access
                        for j in 0..num_fields {
                            // UNSAFE: We verified j < num_fields
                            let field = unsafe { fd.get_at_unchecked(j) };
                            // Just extract - don't check name (datatype dispatch)
                            if field.get_f64(0).is_some() {
                                fields_extracted += 1;
                            }
                        }
                    }
                }
            }
        }
    }

    (securities_parsed, fields_extracted)
}

/// Parse using get_str (SIMD ASCII fast-path).
#[inline(never)]
#[allow(dead_code)]
fn parse_with_str_fast(event: &Event, names: &FieldNames) -> usize {
    let mut fields_extracted = 0;

    for msg in event.messages() {
        let root = msg.elements();
        if let Some(security_data) = root.get(&names.security_data) {
            for i in 0..security_data.len() {
                if let Some(sec) = security_data.get_element(i) {
                    // Use get_str for ticker
                    if sec
                        .get(&names.security)
                        .and_then(|e| e.get_str(0))
                        .is_some()
                    {
                        fields_extracted += 1;
                    }
                    if let Some(fd) = sec.get(&names.field_data) {
                        if fd
                            .get(&names.last_trade)
                            .and_then(|e| e.get_str(0))
                            .is_some()
                        {
                            fields_extracted += 1;
                        }
                    }
                }
            }
        }
    }

    fields_extracted
}

fn main() {
    println!("xbbg-core Cached Parse Benchmark");
    println!("=================================================\n");

    let iterations = env_iterations("BENCH_ITERATIONS", 10_000);

    // Tickers and fields to request
    let tickers = &[
        "IBM US Equity",
        "AAPL US Equity",
        "MSFT US Equity",
        "GOOGL US Equity",
        "AMZN US Equity",
    ];
    let fields = &[
        "PX_LAST",
        "PX_OPEN",
        "PX_HIGH",
        "PX_LOW",
        "VOLUME",
        "CUR_MKT_CAP",
        "EQY_WEIGHTED_AVG_PX",
        "PX_BID",
        "PX_ASK",
        "LAST_TRADE",
    ];

    println!("Setup: {} tickers, {} fields", tickers.len(), fields.len());

    // Pre-intern all names
    let names = FieldNames::new();

    // Setup session and fetch data ONCE (network call)
    println!("Connecting to Bloomberg...");
    let sess = setup_session();
    open_service(&sess, "//blp/refdata");

    println!("Fetching data (single network call)...");
    let fetch_start = Instant::now();
    let cached_event = fetch_bdp_response(&sess, &names, tickers, fields);
    let fetch_time = fetch_start.elapsed();
    println!(
        "Fetch time: {:?} (this includes network latency)\n",
        fetch_time
    );

    // Verify we got data
    let (sec_count, field_count) = parse_all_fields(&cached_event, &names);
    println!(
        "Cached data: {} securities, {} fields extracted\n",
        sec_count, field_count
    );

    // =========================================================================
    // BENCHMARK 1: Parse all fields N times
    // =========================================================================
    // BENCHMARK 1: Baseline vs Optimized parsing
    // =========================================================================
    println!(
        "Benchmark 1: Baseline vs Optimized parsing x {}",
        iterations
    );

    // 1a. Baseline: N separate get(&name) lookups
    let start = Instant::now();
    let mut total_fields = 0;
    for _ in 0..iterations {
        let (_, fields) = parse_all_fields(&cached_event, &names);
        total_fields += fields;
    }
    let elapsed_baseline = start.elapsed();

    // 1b. Optimized V1: Iterate children once
    let start = Instant::now();
    let mut total_fields_opt = 0;
    for _ in 0..iterations {
        let (_, fields) = parse_all_fields_optimized(&cached_event, &names);
        total_fields_opt += fields;
    }
    let elapsed_optimized = start.elapsed();

    // 1c. Optimized V2: Datatype-based extraction (no name comparison)
    let start = Instant::now();
    let mut total_fields_dtype = 0;
    for _ in 0..iterations {
        let (_, fields) = parse_all_fields_by_datatype(&cached_event, &names);
        total_fields_dtype += fields;
    }
    let elapsed_datatype = start.elapsed();

    // 1d. Optimized V3: Unchecked iterators
    let start = Instant::now();
    let mut total_fields_unchecked = 0;
    for _ in 0..iterations {
        let (_, fields) = parse_all_fields_unchecked(&cached_event, &names);
        total_fields_unchecked += fields;
    }
    let elapsed_unchecked = start.elapsed();

    // 1e. Optimized V4: Column-driven extraction
    let start = Instant::now();
    let mut total_fields_max = 0;
    for _ in 0..iterations {
        let (_, fields) = parse_all_fields_max_speed(&cached_event, &names);
        total_fields_max += fields;
    }
    let elapsed_max = start.elapsed();

    // 1f. Optimized V5: Minimal FFI - unchecked everywhere
    let start = Instant::now();
    let mut total_fields_minimal = 0;
    for _ in 0..iterations {
        let (_, fields) = parse_all_fields_minimal_ffi(&cached_event, &names);
        total_fields_minimal += fields;
    }
    let elapsed_minimal = start.elapsed();

    println!(
        "  Baseline (N lookups):     {:?} ({:?}/iter) - {:.2}M fields/sec",
        elapsed_baseline,
        elapsed_baseline / iterations as u32,
        (total_fields as f64 / elapsed_baseline.as_secs_f64()) / 1_000_000.0
    );
    println!(
        "  V1 (iterate+name_eq):     {:?} ({:?}/iter) - {:.2}M fields/sec",
        elapsed_optimized,
        elapsed_optimized / iterations as u32,
        (total_fields_opt as f64 / elapsed_optimized.as_secs_f64()) / 1_000_000.0
    );
    println!(
        "  V2 (datatype dispatch):   {:?} ({:?}/iter) - {:.2}M fields/sec",
        elapsed_datatype,
        elapsed_datatype / iterations as u32,
        (total_fields_dtype as f64 / elapsed_datatype.as_secs_f64()) / 1_000_000.0
    );
    println!(
        "  V3 (unchecked iter):      {:?} ({:?}/iter) - {:.2}M fields/sec",
        elapsed_unchecked,
        elapsed_unchecked / iterations as u32,
        (total_fields_unchecked as f64 / elapsed_unchecked.as_secs_f64()) / 1_000_000.0
    );
    println!(
        "  V4 (column-driven):       {:?} ({:?}/iter) - {:.2}M fields/sec",
        elapsed_max,
        elapsed_max / iterations as u32,
        (total_fields_max as f64 / elapsed_max.as_secs_f64()) / 1_000_000.0
    );
    println!(
        "  V5 (minimal FFI):         {:?} ({:?}/iter) - {:.2}M fields/sec",
        elapsed_minimal,
        elapsed_minimal / iterations as u32,
        (total_fields_minimal as f64 / elapsed_minimal.as_secs_f64()) / 1_000_000.0
    );

    println!("\n  Speedups vs Baseline:");
    println!(
        "    V1 (iterate+name_eq):   {:.2}x",
        elapsed_baseline.as_nanos() as f64 / elapsed_optimized.as_nanos() as f64
    );
    println!(
        "    V2 (datatype dispatch): {:.2}x",
        elapsed_baseline.as_nanos() as f64 / elapsed_datatype.as_nanos() as f64
    );
    println!(
        "    V3 (unchecked iter):    {:.2}x",
        elapsed_baseline.as_nanos() as f64 / elapsed_unchecked.as_nanos() as f64
    );
    println!(
        "    V4 (column-driven):     {:.2}x",
        elapsed_baseline.as_nanos() as f64 / elapsed_max.as_nanos() as f64
    );
    println!(
        "    V5 (minimal FFI):       {:.2}x",
        elapsed_baseline.as_nanos() as f64 / elapsed_minimal.as_nanos() as f64
    );
    println!();

    // =========================================================================
    // BENCHMARK 2: String extraction methods comparison
    // =========================================================================
    // BENCHMARK 2: String extraction methods comparison
    // =========================================================================
    println!("Benchmark 2: String extraction methods x {}", iterations);
    println!("  (Testing get_str variants on security ticker field)");

    // Count how many string extractions per iteration
    let calls_per_iter = 5; // 5 securities

    // 1. Standard get_str (CStr::from_ptr + UTF-8 validation)
    let start = Instant::now();
    for _ in 0..iterations {
        for msg in cached_event.messages() {
            let root = msg.elements();
            if let Some(security_data) = root.get(&names.security_data) {
                for i in 0..security_data.len() {
                    if let Some(sec) = security_data.get_element(i) {
                        if let Some(elem) = sec.get(&names.security) {
                            std::hint::black_box(elem.get_str(0));
                        }
                    }
                }
            }
        }
    }
    let elapsed_std = start.elapsed();

    // 2. get_str_unchecked (no UTF-8 validation - unsafe)
    let start = Instant::now();
    for _ in 0..iterations {
        for msg in cached_event.messages() {
            let root = msg.elements();
            if let Some(security_data) = root.get(&names.security_data) {
                for i in 0..security_data.len() {
                    if let Some(sec) = security_data.get_element(i) {
                        if let Some(elem) = sec.get(&names.security) {
                            std::hint::black_box(unsafe { elem.get_str_unchecked(0) });
                        }
                    }
                }
            }
        }
    }
    let elapsed_unchecked = start.elapsed();

    let total_calls = iterations * calls_per_iter;
    println!(
        "  get_str:           {:>10?} ({:>6}ns/call)",
        elapsed_std,
        elapsed_std.as_nanos() / total_calls as u128
    );
    println!(
        "  get_str_unchecked: {:>10?} ({:>6}ns/call)",
        elapsed_unchecked,
        elapsed_unchecked.as_nanos() / total_calls as u128
    );

    // Show speedup
    let base = elapsed_std.as_nanos() as f64;
    println!("\n  Speedup vs get_str:");
    println!(
        "    get_str_unchecked: {:.2}x",
        base / elapsed_unchecked.as_nanos() as f64
    );
    println!();

    // =========================================================================
    // BENCHMARK 3: Breakdown - where is time spent?
    // =========================================================================
    println!("Benchmark 3: Breakdown analysis x {}", iterations);
    println!("  (Where is time actually spent?)");

    // 3a. Just iteration (no field extraction)
    let start = Instant::now();
    let mut count = 0usize;
    for _ in 0..iterations {
        for msg in cached_event.messages() {
            let root = msg.elements();
            if let Some(security_data) = root.get(&names.security_data) {
                for i in 0..security_data.len() {
                    if let Some(sec) = security_data.get_element(i) {
                        if let Some(fd) = sec.get(&names.field_data) {
                            for j in 0..fd.num_children() {
                                if fd.get_at(j).is_some() {
                                    count += 1;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    let elapsed_iter = start.elapsed();
    std::hint::black_box(count);

    // 3b. Iteration + datatype()
    let start = Instant::now();
    let mut count = 0usize;
    for _ in 0..iterations {
        for msg in cached_event.messages() {
            let root = msg.elements();
            if let Some(security_data) = root.get(&names.security_data) {
                for i in 0..security_data.len() {
                    if let Some(sec) = security_data.get_element(i) {
                        if let Some(fd) = sec.get(&names.field_data) {
                            for j in 0..fd.num_children() {
                                if let Some(field) = fd.get_at(j) {
                                    std::hint::black_box(field.datatype());
                                    count += 1;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    let elapsed_dtype = start.elapsed();
    std::hint::black_box(count);

    // 3c. Iteration + datatype() + get_f64()
    let start = Instant::now();
    let mut count = 0usize;
    for _ in 0..iterations {
        for msg in cached_event.messages() {
            let root = msg.elements();
            if let Some(security_data) = root.get(&names.security_data) {
                for i in 0..security_data.len() {
                    if let Some(sec) = security_data.get_element(i) {
                        if let Some(fd) = sec.get(&names.field_data) {
                            for j in 0..fd.num_children() {
                                if let Some(field) = fd.get_at(j) {
                                    std::hint::black_box(field.datatype());
                                    if field.get_f64(0).is_some() {
                                        count += 1;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    let elapsed_extract = start.elapsed();
    std::hint::black_box(count);

    let fields_per_iter = 50; // 5 securities * 10 fields
    let total_fields = iterations * fields_per_iter;

    println!(
        "  Iteration only:       {:?} ({:.0}ns/field)",
        elapsed_iter,
        elapsed_iter.as_nanos() as f64 / total_fields as f64
    );
    println!(
        "  + datatype():         {:?} ({:.0}ns/field)",
        elapsed_dtype,
        elapsed_dtype.as_nanos() as f64 / total_fields as f64
    );
    println!(
        "  + get_f64():          {:?} ({:.0}ns/field)",
        elapsed_extract,
        elapsed_extract.as_nanos() as f64 / total_fields as f64
    );
    let iter_ns = elapsed_iter.as_nanos() as f64 / total_fields as f64;
    let dtype_ns = elapsed_dtype.as_nanos() as f64 / total_fields as f64;
    let extract_ns = elapsed_extract.as_nanos() as f64 / total_fields as f64;
    println!(
        "\n  Breakdown: iter={:.0}ns, +datatype={:.0}ns, +get_f64={:.0}ns",
        iter_ns,
        dtype_ns - iter_ns,
        extract_ns - dtype_ns
    );
    println!();

    // =========================================================================
    // BENCHMARK 4: Raw FFI overhead measurement
    // =========================================================================
    println!("Benchmark 4: Raw FFI call overhead");

    // Get a single element to test raw FFI calls
    let mut test_elem = None;
    for msg in cached_event.messages() {
        let root = msg.elements();
        if let Some(sd) = root.get(&names.security_data) {
            if let Some(sec) = sd.get_element(0) {
                if let Some(fd) = sec.get(&names.field_data) {
                    if let Some(field) = fd.get(&names.px_last) {
                        test_elem = Some(field);
                        break;
                    }
                }
            }
        }
    }

    if let Some(elem) = test_elem {
        // 4a. Raw get_f64 calls - same element, many times
        let calls = iterations * 100; // 1M calls
        let start = Instant::now();
        let mut sum = 0.0f64;
        for _ in 0..calls {
            if let Some(v) = elem.get_f64(0) {
                sum += v;
            }
        }
        let elapsed = start.elapsed();
        std::hint::black_box(sum);
        println!(
            "  get_f64 (same elem, {}x): {:?} ({:.0}ns/call)",
            calls,
            elapsed,
            elapsed.as_nanos() as f64 / calls as f64
        );

        // 4b. Raw datatype calls
        let start = Instant::now();
        let mut sum = 0i32;
        for _ in 0..calls {
            sum += elem.datatype() as i32;
        }
        let elapsed = start.elapsed();
        std::hint::black_box(sum);
        println!(
            "  datatype (same elem, {}x): {:?} ({:.0}ns/call)",
            calls,
            elapsed,
            elapsed.as_nanos() as f64 / calls as f64
        );

        // 4c. Raw num_children calls (on fieldData)
        for msg in cached_event.messages() {
            let root = msg.elements();
            if let Some(sd) = root.get(&names.security_data) {
                if let Some(sec) = sd.get_element(0) {
                    if let Some(fd) = sec.get(&names.field_data) {
                        let start = Instant::now();
                        let mut sum = 0usize;
                        for _ in 0..calls {
                            sum += fd.num_children();
                        }
                        let elapsed = start.elapsed();
                        std::hint::black_box(sum);
                        println!(
                            "  num_children (same elem, {}x): {:?} ({:.0}ns/call)",
                            calls,
                            elapsed,
                            elapsed.as_nanos() as f64 / calls as f64
                        );
                        break;
                    }
                }
            }
        }
    }
    println!();

    // =========================================================================
    // BENCHMARK 5: SIMD utilities (if we had bulk data)
    // =========================================================================
    println!("Benchmark 5: SIMD utilities x {}", iterations);

    // Simulate validity bitmap packing (1000 rows)
    let validity_bytes: Vec<u8> = (0..1000).map(|i| if i % 3 == 0 { 0 } else { 1 }).collect();
    let mut bitmap = vec![0u8; validity_bytes.len().div_ceil(8)];

    let start = Instant::now();
    for _ in 0..iterations {
        xbbg_core::simd::pack_validity(&validity_bytes, &mut bitmap);
    }
    let elapsed = start.elapsed();
    println!(
        "  pack_validity (1000 rows): {:?}/iter",
        elapsed / iterations as u32
    );

    // ASCII detection (typical Bloomberg field value length)
    let ascii_data = b"IBM US Equity - International Business Machines Corporation";
    let start = Instant::now();
    for _ in 0..iterations {
        let _ = xbbg_core::simd::is_ascii_runtime(ascii_data);
    }
    let elapsed = start.elapsed();
    println!(
        "  is_ascii (60 bytes): {:?}/iter",
        elapsed / iterations as u32
    );

    // i32 to f64 conversion (100 values)
    let ints: Vec<i32> = (0..100).collect();
    let mut floats = vec![0.0f64; 100];
    let start = Instant::now();
    for _ in 0..iterations {
        xbbg_core::simd::i32_to_f64_runtime(&ints, &mut floats);
    }
    let elapsed = start.elapsed();
    println!(
        "  i32_to_f64 (100 vals): {:?}/iter",
        elapsed / iterations as u32
    );
    println!();

    // Cleanup
    sess.stop();

    println!("=================================================");
    println!("Benchmark complete.");
}

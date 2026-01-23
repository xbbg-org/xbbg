//! Live BDP benchmark for xbbg-core.
//!
//! Measures end-to-end BDP request performance including:
//! - Session setup and service open
//! - Request construction
//! - Request/response round-trip
//! - Field extraction
//!
//! **Requires Bloomberg connection** - writes results to benchmarks/results/
//!
//! Run with: cargo bench --package xbbg_core --bench live_bdp --features live

use std::fs::{self, File};
use std::io::Write;
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use xbbg_core::{EventType, Name, Session, SessionOptions};

/// Benchmark result for a single run.
#[derive(Debug)]
struct BenchResult {
    name: String,
    iterations: usize,
    cold_start_us: u64,
    warm_mean_us: u64,
    warm_min_us: u64,
    warm_max_us: u64,
    warm_std_us: f64,
    fields_extracted: usize,
}

/// Pre-interned names for hot path.
struct FieldNames {
    securities: Name,
    fields: Name,
    security_data: Name,
    field_data: Name,
    px_last: Name,
    px_open: Name,
    px_high: Name,
    px_low: Name,
    volume: Name,
}

impl FieldNames {
    fn new() -> Self {
        Self {
            securities: Name::get_or_intern("securities"),
            fields: Name::get_or_intern("fields"),
            security_data: Name::get_or_intern("securityData"),
            field_data: Name::get_or_intern("fieldData"),
            px_last: Name::get_or_intern("PX_LAST"),
            px_open: Name::get_or_intern("PX_OPEN"),
            px_high: Name::get_or_intern("PX_HIGH"),
            px_low: Name::get_or_intern("PX_LOW"),
            volume: Name::get_or_intern("VOLUME"),
        }
    }
}

fn setup_session() -> Session {
    let host = std::env::var("BLP_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port: u16 = std::env::var("BLP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8194);

    let mut opts = SessionOptions::new().expect("failed to create session options");
    opts.set_server_host(&host).expect("failed to set host");
    opts.set_server_port(port);

    let sess = Session::new(&opts).expect("failed to create session");
    sess.start().expect("failed to start session");

    // Wait for SessionStarted
    loop {
        if let Ok(ev) = sess.next_event(Some(5000)) {
            if ev.event_type() == EventType::SessionStatus {
                break;
            }
        }
    }

    sess
}

/// Measure full BDP round-trip: build request, send, receive, extract.
fn bench_bdp_roundtrip(
    sess: &Session,
    names: &FieldNames,
    ticker: &str,
    field_names: &[&Name],
    field_strs: &[&str],
) -> (Duration, usize) {
    let start = Instant::now();

    // Get service
    let svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get service");

    // Create request
    let mut req = svc
        .create_request("ReferenceDataRequest")
        .expect("failed to create request");

    // Add security
    req.append_string(&names.securities, ticker)
        .expect("failed to add security");

    // Add fields
    for field in field_strs {
        req.append_string(&names.fields, field)
            .expect("failed to add field");
    }

    // Send request
    sess.send_request(&req, None, None)
        .expect("failed to send request");

    // Get response and extract fields
    let mut fields_extracted = 0;
    loop {
        if let Ok(ev) = sess.next_event(Some(5000)) {
            if ev.event_type() == EventType::Response {
                // Extract fields
                for msg in ev.messages() {
                    let root = msg.elements();
                    if let Some(sd) = root.get(&names.security_data) {
                        if let Some(first) = sd.get_at(0) {
                            if let Some(fd) = first.get(&names.field_data) {
                                for field_name in field_names {
                                    if fd.get(field_name).and_then(|e| e.get_f64(0)).is_some() {
                                        fields_extracted += 1;
                                    }
                                }
                            }
                        }
                    }
                }
                break;
            }
        }
    }

    (start.elapsed(), fields_extracted)
}

/// Run benchmark with warmup and multiple iterations.
fn run_benchmark<F>(name: &str, iterations: usize, warmup: usize, mut f: F) -> BenchResult
where
    F: FnMut() -> (Duration, usize),
{
    // Warmup
    for _ in 0..warmup {
        let _ = f();
    }

    // Cold start (first real iteration)
    let (cold_dur, fields) = f();
    let cold_start_us = cold_dur.as_micros() as u64;

    // Warm iterations
    let mut times_us: Vec<u64> = Vec::with_capacity(iterations - 1);
    for _ in 1..iterations {
        let (dur, _) = f();
        times_us.push(dur.as_micros() as u64);
    }

    // Calculate stats
    let warm_mean_us = if times_us.is_empty() {
        cold_start_us
    } else {
        times_us.iter().sum::<u64>() / times_us.len() as u64
    };

    let warm_min_us = *times_us.iter().min().unwrap_or(&cold_start_us);
    let warm_max_us = *times_us.iter().max().unwrap_or(&cold_start_us);

    let warm_std_us = if times_us.len() > 1 {
        let mean = warm_mean_us as f64;
        let variance = times_us
            .iter()
            .map(|&t| (t as f64 - mean).powi(2))
            .sum::<f64>()
            / (times_us.len() - 1) as f64;
        variance.sqrt()
    } else {
        0.0
    };

    BenchResult {
        name: name.to_string(),
        iterations,
        cold_start_us,
        warm_mean_us,
        warm_min_us,
        warm_max_us,
        warm_std_us,
        fields_extracted: fields,
    }
}

fn write_results(results: &[BenchResult], output_path: &PathBuf) {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    let json = format!(
        r#"{{
  "timestamp": {},
  "crate": "xbbg-core",
  "benchmarks": [
{}
  ]
}}"#,
        timestamp,
        results
            .iter()
            .map(|r| {
                format!(
                    r#"    {{
      "name": "{}",
      "iterations": {},
      "cold_start_us": {},
      "warm_mean_us": {},
      "warm_min_us": {},
      "warm_max_us": {},
      "warm_std_us": {:.2},
      "fields_extracted": {}
    }}"#,
                    r.name,
                    r.iterations,
                    r.cold_start_us,
                    r.warm_mean_us,
                    r.warm_min_us,
                    r.warm_max_us,
                    r.warm_std_us,
                    r.fields_extracted
                )
            })
            .collect::<Vec<_>>()
            .join(",\n")
    );

    let mut file = File::create(output_path).expect("failed to create output file");
    file.write_all(json.as_bytes())
        .expect("failed to write results");

    println!("\nResults written to: {}", output_path.display());
}

fn print_results(results: &[BenchResult]) {
    println!("\n{:=<70}", "");
    println!("  xbbg-core BDP Benchmark Results");
    println!("{:=<70}\n", "");

    println!(
        "  {:<30} {:>10} {:>10} {:>10} {:>10}",
        "Benchmark", "Cold (μs)", "Mean (μs)", "Min (μs)", "Max (μs)"
    );
    println!("  {:-<70}", "");

    for r in results {
        println!(
            "  {:<30} {:>10} {:>10} {:>10} {:>10}",
            r.name, r.cold_start_us, r.warm_mean_us, r.warm_min_us, r.warm_max_us
        );
    }

    println!("\n{:=<70}", "");
}

fn main() {
    println!("xbbg-core Live BDP Benchmark");
    println!("============================\n");

    let iterations: usize = std::env::var("BENCH_ITERATIONS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(10);

    let warmup: usize = std::env::var("BENCH_WARMUP")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);

    println!("Config: {} iterations, {} warmup\n", iterations, warmup);

    // Setup
    let names = FieldNames::new();
    let sess = setup_session();

    // Open refdata service once
    sess.open_service("//blp/refdata")
        .expect("failed to open service");

    let mut results = Vec::new();

    // Benchmark 1: Single ticker, single field
    println!("Running: bdp_1t_1f (IBM US Equity, PX_LAST)...");
    let r = run_benchmark("bdp_1t_1f", iterations, warmup, || {
        bench_bdp_roundtrip(
            &sess,
            &names,
            "IBM US Equity",
            &[&names.px_last],
            &["PX_LAST"],
        )
    });
    results.push(r);

    // Benchmark 2: Single ticker, 5 fields
    println!("Running: bdp_1t_5f (IBM US Equity, 5 fields)...");
    let r = run_benchmark("bdp_1t_5f", iterations, warmup, || {
        bench_bdp_roundtrip(
            &sess,
            &names,
            "IBM US Equity",
            &[
                &names.px_last,
                &names.px_open,
                &names.px_high,
                &names.px_low,
                &names.volume,
            ],
            &["PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW", "VOLUME"],
        )
    });
    results.push(r);

    // Cleanup
    sess.stop();

    // Print and save results
    print_results(&results);

    // Create results directory and write
    let results_dir = PathBuf::from("benchmarks/results");
    fs::create_dir_all(&results_dir).expect("failed to create results directory");

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    let output_path = results_dir.join(format!("xbbg_core_bdp_{}.json", timestamp));
    write_results(&results, &output_path);

    // Also write to latest.json
    let latest_path = results_dir.join("xbbg_core_bdp_latest.json");
    write_results(&results, &latest_path);
}

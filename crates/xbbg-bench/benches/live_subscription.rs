//! Live Subscription benchmark for xbbg-core.
//!
//! Measures subscription performance including:
//! - Subscription setup latency
//! - Time to first tick
//! - Tick processing throughput
//! - Field extraction from subscription data
//!
//! **Requires Bloomberg connection** - writes results to benchmarks/results/
//!
//! Run with: cargo bench --package xbbg-bench --bench live_subscription

use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use xbbg_bench::{open_service, setup_session, write_json, FieldNames};
use xbbg_core::{CorrelationId, EventType, SubscriptionList};

/// Benchmark result for subscription tests.
#[derive(Debug)]
struct SubBenchResult {
    name: String,
    setup_us: u64,
    time_to_first_tick_us: u64,
    ticks_received: usize,
    tick_processing_us: u64,
    fields_per_tick: f64,
}

/// Measure subscription setup and time to first data.
fn bench_subscription_setup(
    sess: &xbbg_core::Session,
    names: &FieldNames,
    ticker: &str,
    fields: &[&str],
    collect_duration_ms: u64,
) -> SubBenchResult {
    let setup_start = Instant::now();

    // Create subscription list
    let mut sub_list = SubscriptionList::new();

    // Add subscription with fields and options
    let cid = CorrelationId::new_int(1);
    sub_list
        .add(ticker, fields, "", &cid)
        .expect("failed to add subscription");

    // Subscribe
    sess.subscribe(&sub_list, None)
        .expect("failed to subscribe");

    let setup_us = setup_start.elapsed().as_micros() as u64;

    // Wait for first tick
    let first_tick_start = Instant::now();
    let mut time_to_first_tick_us = 0u64;
    let mut ticks_received = 0usize;
    let mut total_fields = 0usize;
    let mut tick_processing_total_us = 0u64;

    let deadline = Instant::now() + Duration::from_millis(collect_duration_ms);

    loop {
        let timeout_ms = deadline
            .saturating_duration_since(Instant::now())
            .as_millis() as u32;
        if timeout_ms == 0 {
            break;
        }

        if let Ok(ev) = sess.next_event(Some(timeout_ms)) {
            match ev.event_type() {
                EventType::SubscriptionData => {
                    let tick_start = Instant::now();

                    if ticks_received == 0 {
                        time_to_first_tick_us = first_tick_start.elapsed().as_micros() as u64;
                    }

                    // Extract fields from tick
                    for msg in ev.messages() {
                        let root = msg.elements();

                        // Try to extract each field
                        if root
                            .get(&names.last_price)
                            .and_then(|e| e.get_f64(0))
                            .is_some()
                        {
                            total_fields += 1;
                        }
                        if root.get(&names.bid).and_then(|e| e.get_f64(0)).is_some() {
                            total_fields += 1;
                        }
                        if root.get(&names.ask).and_then(|e| e.get_f64(0)).is_some() {
                            total_fields += 1;
                        }
                    }

                    tick_processing_total_us += tick_start.elapsed().as_micros() as u64;
                    ticks_received += 1;
                }
                EventType::SubscriptionStatus => {
                    // Subscription confirmed
                }
                _ => {}
            }
        }
    }

    // Unsubscribe
    sess.unsubscribe(&sub_list).expect("failed to unsubscribe");

    let fields_per_tick = if ticks_received > 0 {
        total_fields as f64 / ticks_received as f64
    } else {
        0.0
    };

    SubBenchResult {
        name: format!("subscription_{}", ticker.replace(' ', "_")),
        setup_us,
        time_to_first_tick_us,
        ticks_received,
        tick_processing_us: tick_processing_total_us,
        fields_per_tick,
    }
}

/// Measure multi-ticker subscription.
fn bench_multi_subscription(
    sess: &xbbg_core::Session,
    names: &FieldNames,
    tickers: &[&str],
    fields: &[&str],
    collect_duration_ms: u64,
) -> SubBenchResult {
    let setup_start = Instant::now();

    // Create subscription list with multiple tickers
    let mut sub_list = SubscriptionList::new();

    for (i, ticker) in tickers.iter().enumerate() {
        let cid = CorrelationId::new_int(i as i64 + 1);
        sub_list
            .add(ticker, fields, "", &cid)
            .expect("failed to add subscription");
    }

    // Subscribe
    sess.subscribe(&sub_list, None)
        .expect("failed to subscribe");

    let setup_us = setup_start.elapsed().as_micros() as u64;

    // Collect ticks
    let first_tick_start = Instant::now();
    let mut time_to_first_tick_us = 0u64;
    let mut ticks_received = 0usize;
    let mut total_fields = 0usize;
    let mut tick_processing_total_us = 0u64;

    let deadline = Instant::now() + Duration::from_millis(collect_duration_ms);

    loop {
        let timeout_ms = deadline
            .saturating_duration_since(Instant::now())
            .as_millis() as u32;
        if timeout_ms == 0 {
            break;
        }

        if let Ok(ev) = sess.next_event(Some(timeout_ms)) {
            if ev.event_type() == EventType::SubscriptionData {
                let tick_start = Instant::now();

                if ticks_received == 0 {
                    time_to_first_tick_us = first_tick_start.elapsed().as_micros() as u64;
                }

                for msg in ev.messages() {
                    let root = msg.elements();
                    if root
                        .get(&names.last_price)
                        .and_then(|e| e.get_f64(0))
                        .is_some()
                    {
                        total_fields += 1;
                    }
                    if root.get(&names.bid).and_then(|e| e.get_f64(0)).is_some() {
                        total_fields += 1;
                    }
                    if root.get(&names.ask).and_then(|e| e.get_f64(0)).is_some() {
                        total_fields += 1;
                    }
                }

                tick_processing_total_us += tick_start.elapsed().as_micros() as u64;
                ticks_received += 1;
            }
        }
    }

    // Unsubscribe
    sess.unsubscribe(&sub_list).expect("failed to unsubscribe");

    let fields_per_tick = if ticks_received > 0 {
        total_fields as f64 / ticks_received as f64
    } else {
        0.0
    };

    SubBenchResult {
        name: format!("subscription_{}t_{}f", tickers.len(), fields.len()),
        setup_us,
        time_to_first_tick_us,
        ticks_received,
        tick_processing_us: tick_processing_total_us,
        fields_per_tick,
    }
}

fn write_results(results: &[SubBenchResult], output_path: &PathBuf) {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    let json = format!(
        r#"{{
  "timestamp": {},
  "crate": "xbbg-core",
  "benchmark_type": "subscription",
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
      "setup_us": {},
      "time_to_first_tick_us": {},
      "ticks_received": {},
      "tick_processing_us": {},
      "fields_per_tick": {:.2}
    }}"#,
                    r.name,
                    r.setup_us,
                    r.time_to_first_tick_us,
                    r.ticks_received,
                    r.tick_processing_us,
                    r.fields_per_tick
                )
            })
            .collect::<Vec<_>>()
            .join(",\n")
    );

    write_json(output_path, &json);
}

fn print_results(results: &[SubBenchResult]) {
    println!("\n{:=<80}", "");
    println!("  xbbg-core Subscription Benchmark Results");
    println!("{:=<80}\n", "");

    println!(
        "  {:<30} {:>12} {:>12} {:>10} {:>10}",
        "Benchmark", "Setup (μs)", "1st Tick", "Ticks", "Fields/Tick"
    );
    println!("  {:-<80}", "");

    for r in results {
        println!(
            "  {:<30} {:>12} {:>12} {:>10} {:>10.2}",
            r.name, r.setup_us, r.time_to_first_tick_us, r.ticks_received, r.fields_per_tick
        );
    }

    println!("\n{:=<80}", "");
}

fn main() {
    println!("xbbg-core Live Subscription Benchmark");
    println!("======================================\n");

    let collect_duration_ms: u64 = std::env::var("BENCH_COLLECT_MS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(5000); // 5 seconds default

    println!(
        "Config: collecting data for {}ms per test\n",
        collect_duration_ms
    );

    // Setup
    let names = FieldNames::new();
    let sess = setup_session();

    // Open mktdata service
    open_service(&sess, "//blp/mktdata");

    let mut results = Vec::new();

    // Benchmark 1: Single ticker, 3 fields
    println!("Running: Single ticker subscription (IBM US Equity)...");
    let r = bench_subscription_setup(
        &sess,
        &names,
        "IBM US Equity",
        &["LAST_PRICE", "BID", "ASK"],
        collect_duration_ms,
    );
    results.push(r);

    // Small delay between tests
    std::thread::sleep(Duration::from_millis(500));

    // Benchmark 2: Multi-ticker subscription
    println!("Running: Multi-ticker subscription (3 tickers)...");
    let r = bench_multi_subscription(
        &sess,
        &names,
        &["IBM US Equity", "AAPL US Equity", "MSFT US Equity"],
        &["LAST_PRICE", "BID", "ASK"],
        collect_duration_ms,
    );
    results.push(r);

    // Cleanup
    sess.stop();

    // Print and save results
    print_results(&results);

    // Write results
    let results_dir = PathBuf::from("benchmarks/results");

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    let output_path = results_dir.join(format!("xbbg_core_subscription_{}.json", timestamp));
    write_results(&results, &output_path);

    // Also write to latest.json
    let latest_path = results_dir.join("xbbg_core_subscription_latest.json");
    write_results(&results, &latest_path);
}

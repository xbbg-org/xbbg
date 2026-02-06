//! Profiled BDP benchmark - breaks down timing for each phase.
//!
//! Run with: cargo bench --package xbbg-bench --bench live_bdp_profiled

use std::time::Instant;
use xbbg_bench::{env_iterations, open_service, setup_session, FieldNames};
use xbbg_core::EventType;

/// Timing breakdown for a single BDP request.
#[derive(Debug, Default, Clone)]
struct PhaseTimings {
    get_service_us: u64,
    create_request_us: u64,
    append_securities_us: u64,
    append_fields_us: u64,
    send_request_us: u64,
    wait_response_us: u64,
    parse_response_us: u64,
    total_us: u64,
}

impl PhaseTimings {
    fn print_header() {
        println!(
            "{:>12} {:>12} {:>12} {:>12} {:>12} {:>12} {:>12} {:>12}",
            "get_svc",
            "create_req",
            "append_sec",
            "append_fld",
            "send_req",
            "wait_resp",
            "parse",
            "TOTAL"
        );
        println!("{:-<108}", "");
    }

    fn print(&self) {
        println!(
            "{:>12} {:>12} {:>12} {:>12} {:>12} {:>12} {:>12} {:>12}",
            self.get_service_us,
            self.create_request_us,
            self.append_securities_us,
            self.append_fields_us,
            self.send_request_us,
            self.wait_response_us,
            self.parse_response_us,
            self.total_us
        );
    }

    fn print_averages(timings: &[PhaseTimings]) {
        if timings.is_empty() {
            return;
        }
        let n = timings.len() as u64;
        let avg = PhaseTimings {
            get_service_us: timings.iter().map(|t| t.get_service_us).sum::<u64>() / n,
            create_request_us: timings.iter().map(|t| t.create_request_us).sum::<u64>() / n,
            append_securities_us: timings.iter().map(|t| t.append_securities_us).sum::<u64>() / n,
            append_fields_us: timings.iter().map(|t| t.append_fields_us).sum::<u64>() / n,
            send_request_us: timings.iter().map(|t| t.send_request_us).sum::<u64>() / n,
            wait_response_us: timings.iter().map(|t| t.wait_response_us).sum::<u64>() / n,
            parse_response_us: timings.iter().map(|t| t.parse_response_us).sum::<u64>() / n,
            total_us: timings.iter().map(|t| t.total_us).sum::<u64>() / n,
        };
        println!("{:-<108}", "");
        print!("AVG: ");
        avg.print();

        // Print percentage breakdown
        if avg.total_us > 0 {
            println!("\nPhase breakdown (% of total):");
            println!(
                "  get_service:     {:>6.2}%  ({:>8} μs)",
                avg.get_service_us as f64 / avg.total_us as f64 * 100.0,
                avg.get_service_us
            );
            println!(
                "  create_request:  {:>6.2}%  ({:>8} μs)",
                avg.create_request_us as f64 / avg.total_us as f64 * 100.0,
                avg.create_request_us
            );
            println!(
                "  append_sec:      {:>6.2}%  ({:>8} μs)",
                avg.append_securities_us as f64 / avg.total_us as f64 * 100.0,
                avg.append_securities_us
            );
            println!(
                "  append_fields:   {:>6.2}%  ({:>8} μs)",
                avg.append_fields_us as f64 / avg.total_us as f64 * 100.0,
                avg.append_fields_us
            );
            println!(
                "  send_request:    {:>6.2}%  ({:>8} μs)",
                avg.send_request_us as f64 / avg.total_us as f64 * 100.0,
                avg.send_request_us
            );
            println!(
                "  wait_response:   {:>6.2}%  ({:>8} μs)  <-- NETWORK + BLOOMBERG",
                avg.wait_response_us as f64 / avg.total_us as f64 * 100.0,
                avg.wait_response_us
            );
            println!(
                "  parse_response:  {:>6.2}%  ({:>8} μs)",
                avg.parse_response_us as f64 / avg.total_us as f64 * 100.0,
                avg.parse_response_us
            );
        }
    }
}

/// Profiled BDP request - returns timing for each phase.
fn bench_bdp_profiled(sess: &xbbg_core::Session, names: &FieldNames, ticker: &str) -> PhaseTimings {
    let mut timings = PhaseTimings::default();
    let total_start = Instant::now();

    // Phase 1: Get service
    let t = Instant::now();
    let svc = sess
        .get_service("//blp/refdata")
        .expect("failed to get service");
    timings.get_service_us = t.elapsed().as_micros() as u64;

    // Phase 2: Create request
    let t = Instant::now();
    let mut req = svc
        .create_request("ReferenceDataRequest")
        .expect("failed to create request");
    timings.create_request_us = t.elapsed().as_micros() as u64;

    // Phase 3: Append securities
    let t = Instant::now();
    req.append_string(&names.securities, ticker)
        .expect("failed to add security");
    timings.append_securities_us = t.elapsed().as_micros() as u64;

    // Phase 4: Append fields
    let t = Instant::now();
    req.append_string(&names.fields, "PX_LAST")
        .expect("failed to add field");
    timings.append_fields_us = t.elapsed().as_micros() as u64;

    // Phase 5: Send request
    let t = Instant::now();
    sess.send_request(&req, None, None)
        .expect("failed to send request");
    timings.send_request_us = t.elapsed().as_micros() as u64;

    // Phase 6: Wait for response
    let t = Instant::now();
    let ev = loop {
        if let Ok(ev) = sess.next_event(Some(5000)) {
            if ev.event_type() == EventType::Response {
                break ev;
            }
        }
    };
    timings.wait_response_us = t.elapsed().as_micros() as u64;

    // Phase 7: Parse response
    let t = Instant::now();
    for msg in ev.messages() {
        let root = msg.elements();
        if let Some(sd) = root.get(&names.security_data) {
            if let Some(first) = sd.get_at(0) {
                if let Some(fd) = first.get(&names.field_data) {
                    let _ = fd.get(&names.px_last).and_then(|e| e.get_f64(0));
                }
            }
        }
    }
    timings.parse_response_us = t.elapsed().as_micros() as u64;

    timings.total_us = total_start.elapsed().as_micros() as u64;
    timings
}

fn main() {
    println!("xbbg-core Profiled BDP Benchmark");
    println!("=================================\n");

    let iterations = env_iterations("BENCH_ITERATIONS", 10);

    println!("Running {} iterations...\n", iterations);

    // Setup
    let names = FieldNames::new();
    let sess = setup_session();

    // Open refdata service once
    let t = Instant::now();
    open_service(&sess, "//blp/refdata");
    println!("Service open time: {} μs\n", t.elapsed().as_micros());

    // Run profiled benchmarks
    PhaseTimings::print_header();

    let mut all_timings = Vec::with_capacity(iterations);

    for i in 0..iterations {
        let timings = bench_bdp_profiled(&sess, &names, "IBM US Equity");
        if i < 5 || i == iterations - 1 {
            // Print first 5 and last
            timings.print();
        } else if i == 5 {
            println!("... ({} more iterations) ...", iterations - 6);
        }
        all_timings.push(timings);
    }

    PhaseTimings::print_averages(&all_timings);

    // Cleanup
    sess.stop();

    println!("\n=================================");
    println!("Profiling complete.");
}

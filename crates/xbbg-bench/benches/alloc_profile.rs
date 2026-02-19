//! Allocation profiling benchmark using dhat.
//!
//! This provides BenchmarkDotNet-style allocation tracking:
//! - Total bytes allocated
//! - Total allocation count
//! - Peak memory usage
//! - Allocation patterns by call site
//!
//! Run with: cargo bench --package xbbg-bench --bench alloc_profile
//!
//! Output: dhat-heap.json (view at https://nnethercote.github.io/dh_view/dh_view.html)

#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

use std::time::Instant;
use xbbg_bench::{env_iterations, open_service, setup_session, FieldNames};
use xbbg_core::{EventType, Name};

/// Allocation stats for a single operation.
#[derive(Debug, Clone)]
struct AllocStats {
    name: String,
    bytes_allocated: u64,
    allocations: u64,
    duration_us: u64,
    bytes_per_op: f64,
    allocs_per_op: f64,
}

impl AllocStats {
    fn print_header() {
        println!(
            "\n{:<30} {:>12} {:>12} {:>12} {:>14} {:>14}",
            "Operation", "Bytes", "Allocs", "Time (us)", "Bytes/op", "Allocs/op"
        );
        println!("{:-<96}", "");
    }

    fn print(&self) {
        println!(
            "{:<30} {:>12} {:>12} {:>12} {:>14.1} {:>14.2}",
            self.name,
            self.bytes_allocated,
            self.allocations,
            self.duration_us,
            self.bytes_per_op,
            self.allocs_per_op
        );
    }
}

/// Simple random u64 for unique name generation.
fn rand_u64() -> u64 {
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::SystemTime;
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let c = COUNTER.fetch_add(1, Ordering::Relaxed);
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap()
        .as_nanos() as u64
        ^ c
}

/// Profile allocations for a closure, running it `iterations` times.
fn profile_allocs<F, R>(name: &str, iterations: usize, mut f: F) -> AllocStats
where
    F: FnMut() -> R,
{
    // Get baseline stats
    let stats_before = dhat::HeapStats::get();
    let start = Instant::now();

    // Run the operation
    for _ in 0..iterations {
        let _ = std::hint::black_box(f());
    }

    let duration = start.elapsed();
    let stats_after = dhat::HeapStats::get();

    // Calculate delta
    let bytes = stats_after
        .total_bytes
        .saturating_sub(stats_before.total_bytes);
    let allocs = stats_after
        .total_blocks
        .saturating_sub(stats_before.total_blocks);

    AllocStats {
        name: name.to_string(),
        bytes_allocated: bytes,
        allocations: allocs,
        duration_us: duration.as_micros() as u64,
        bytes_per_op: bytes as f64 / iterations as f64,
        allocs_per_op: allocs as f64 / iterations as f64,
    }
}

/// Profile BDP request phases individually.
fn profile_bdp_phases(
    sess: &xbbg_core::Session,
    names: &FieldNames,
    iterations: usize,
) -> Vec<AllocStats> {
    let mut results = Vec::new();

    // Phase 1: Get service (should be cached after first call)
    let stats = profile_allocs("get_service", iterations, || {
        sess.get_service("//blp/refdata")
            .expect("failed to get service")
    });
    results.push(stats);

    // Phase 2: Create request
    let svc = sess.get_service("//blp/refdata").expect("service");
    let stats = profile_allocs("create_request", iterations, || {
        svc.create_request("ReferenceDataRequest")
            .expect("failed to create request")
    });
    results.push(stats);

    // Phase 3: Append securities
    let stats = profile_allocs("append_security", iterations, || {
        let mut req = svc.create_request("ReferenceDataRequest").unwrap();
        req.append_string(&names.securities, "IBM US Equity")
            .unwrap();
        req
    });
    results.push(stats);

    // Phase 4: Append fields (5 fields)
    let stats = profile_allocs("append_5_fields", iterations, || {
        let mut req = svc.create_request("ReferenceDataRequest").unwrap();
        req.append_string(&names.fields, "PX_LAST").unwrap();
        req.append_string(&names.fields, "PX_OPEN").unwrap();
        req.append_string(&names.fields, "PX_HIGH").unwrap();
        req.append_string(&names.fields, "PX_LOW").unwrap();
        req.append_string(&names.fields, "VOLUME").unwrap();
        req
    });
    results.push(stats);

    // Phase 5: Full request construction
    let stats = profile_allocs("full_request_build", iterations, || {
        let mut req = svc.create_request("ReferenceDataRequest").unwrap();
        req.append_string(&names.securities, "IBM US Equity")
            .unwrap();
        req.append_string(&names.fields, "PX_LAST").unwrap();
        req.append_string(&names.fields, "PX_OPEN").unwrap();
        req.append_string(&names.fields, "PX_HIGH").unwrap();
        req.append_string(&names.fields, "PX_LOW").unwrap();
        req.append_string(&names.fields, "VOLUME").unwrap();
        req
    });
    results.push(stats);

    results
}

/// Profile response parsing allocations.
fn profile_response_parsing(
    sess: &xbbg_core::Session,
    names: &FieldNames,
    iterations: usize,
) -> Vec<AllocStats> {
    let mut results = Vec::new();

    // Send a request and capture the response
    let svc = sess.get_service("//blp/refdata").expect("service");
    let mut req = svc.create_request("ReferenceDataRequest").unwrap();
    req.append_string(&names.securities, "IBM US Equity")
        .unwrap();
    req.append_string(&names.fields, "PX_LAST").unwrap();
    sess.send_request(&req, None, None).expect("send");

    // Get response event
    let ev = loop {
        if let Ok(ev) = sess.next_event(Some(5000)) {
            if ev.event_type() == EventType::Response {
                break ev;
            }
        }
    };

    // Profile message iteration
    let stats = profile_allocs("message_iteration", iterations, || {
        let mut count = 0;
        for msg in ev.messages() {
            let _ = std::hint::black_box(msg.elements());
            count += 1;
        }
        count
    });
    results.push(stats);

    // Profile element access
    let stats = profile_allocs("element_get_by_name", iterations, || {
        for msg in ev.messages() {
            let root = msg.elements();
            let _ = std::hint::black_box(root.get(&names.security_data));
        }
    });
    results.push(stats);

    // Profile full field extraction
    let stats = profile_allocs("full_field_extraction", iterations, || {
        let mut value = None;
        for msg in ev.messages() {
            let root = msg.elements();
            if let Some(sd) = root.get(&names.security_data) {
                if let Some(first) = sd.get_at(0) {
                    if let Some(fd) = first.get(&names.field_data) {
                        value = fd.get(&names.px_last).and_then(|e| e.get_f64(0));
                    }
                }
            }
        }
        value
    });
    results.push(stats);

    results
}

/// Profile Name operations.
fn profile_name_operations(iterations: usize) -> Vec<AllocStats> {
    let mut results = Vec::new();

    // Name creation (first time - may allocate)
    let stats = profile_allocs("name_create_new", iterations, || {
        // Use unique names to force allocation
        Name::new(&format!("FIELD_{}", rand_u64()))
    });
    results.push(stats);

    // Name interning (lookup existing)
    let existing = Name::get_or_intern("PX_LAST");
    let stats = profile_allocs("name_lookup_existing", iterations, || {
        let _ = std::hint::black_box(&existing);
        Name::get_or_intern("PX_LAST")
    });
    results.push(stats);

    // Name comparison
    let name1 = Name::get_or_intern("PX_LAST");
    let name2 = Name::get_or_intern("PX_LAST");
    let stats = profile_allocs("name_compare", iterations, || {
        std::hint::black_box(&name1) == std::hint::black_box(&name2)
    });
    results.push(stats);

    // Name to string
    let name = Name::get_or_intern("SECURITY_DATA");
    let stats = profile_allocs("name_to_str", iterations, || {
        std::hint::black_box(name.as_str())
    });
    results.push(stats);

    results
}

fn main() {
    // Initialize dhat profiler - will output dhat-heap.json on exit
    let _profiler = dhat::Profiler::new_heap();

    println!("=================================================================");
    println!("  xbbg-core Allocation Profiling");
    println!("=================================================================");
    println!("\nNote: Rust has no GC. This tracks heap allocations only.");
    println!("      Memory is freed deterministically when values drop.\n");

    let iterations = env_iterations("ALLOC_ITERATIONS", 100);

    println!("Iterations per operation: {}", iterations);

    // Profile Name operations (no Bloomberg connection needed for basic tests)
    println!("\n--- Name Operations ---");
    AllocStats::print_header();
    for stats in profile_name_operations(iterations) {
        stats.print();
    }

    // Profile with Bloomberg connection
    println!("\n--- Session Setup ---");
    let names = FieldNames::new();
    let sess = setup_session();

    open_service(&sess, "//blp/refdata");

    // Profile request building
    println!("\n--- Request Building ---");
    AllocStats::print_header();
    for stats in profile_bdp_phases(&sess, &names, iterations) {
        stats.print();
    }

    // Profile response parsing
    println!("\n--- Response Parsing ---");
    AllocStats::print_header();
    for stats in profile_response_parsing(&sess, &names, iterations) {
        stats.print();
    }

    // Cleanup
    sess.stop();

    println!("\n=================================================================");
    println!("  Profiling complete.");
    println!("  Full heap profile written to: dhat-heap.json");
    println!("  View at: https://nnethercote.github.io/dh_view/dh_view.html");
    println!("=================================================================\n");

    // dhat profiler drops here and prints summary + writes JSON
}

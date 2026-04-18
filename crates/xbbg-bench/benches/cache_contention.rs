//! Reader/writer latency percentiles on SchemaCache + FieldTypeResolver.
//!
//! Run with:
//!   BENCH_LABEL=baseline cargo bench -p xbbg-bench --bench cache_contention
//! Results are printed and appended to
//!   target/bench_cache/<label>.txt
//! so baseline and post-change runs can be diffed.

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use hdrhistogram::Histogram;
use tempfile::TempDir;

use xbbg_async::field_cache::{FieldInfo, FieldTypeResolver};
use xbbg_async::schema::{ElementInfo, OperationSchema, SchemaCache, ServiceSchema};

const READER_CONCURRENCY: &[usize] = &[10, 100, 1000];
const BENCH_DURATION: Duration = Duration::from_secs(2);
const WRITE_INTERVAL: Duration = Duration::from_millis(5);

fn make_schema(service: &str) -> ServiceSchema {
    ServiceSchema::new(
        service.to_string(),
        "bench".to_string(),
        vec![OperationSchema {
            name: "BenchRequest".to_string(),
            description: String::new(),
            request: ElementInfo::empty(),
            responses: vec![],
        }],
    )
}

fn make_field(id: u32) -> FieldInfo {
    FieldInfo {
        field_id: format!("FIELD_{id}"),
        arrow_type: "float64".to_string(),
        description: String::new(),
        category: String::new(),
    }
}

fn new_hist() -> Histogram<u64> {
    // 1ns .. 1s at 3 significant figures.
    Histogram::<u64>::new_with_bounds(1, 1_000_000_000, 3).unwrap()
}

fn percentiles(label: &str, h: &Histogram<u64>) -> String {
    format!(
        "{label:<32} samples={:>10} p50={:>8}ns p99={:>9}ns p99.9={:>9}ns max={:>10}ns",
        h.len(),
        h.value_at_quantile(0.50),
        h.value_at_quantile(0.99),
        h.value_at_quantile(0.999),
        h.max(),
    )
}

fn bench_schema(readers: usize) -> Histogram<u64> {
    let temp = TempDir::new().unwrap();
    let cache = Arc::new(SchemaCache::with_cache_dir(temp.path().to_path_buf()));
    const KEY_COUNT: u32 = 10;
    for i in 0..KEY_COUNT {
        let svc = format!("//blp/svc{i}");
        cache.insert(&svc, make_schema(&svc));
    }

    let stop = Arc::new(AtomicBool::new(false));
    let mut handles = Vec::with_capacity(readers);

    for _ in 0..readers {
        let cache = Arc::clone(&cache);
        let stop = Arc::clone(&stop);
        handles.push(thread::spawn(move || {
            let mut h = new_hist();
            let mut i: u32 = 0;
            while !stop.load(Ordering::Relaxed) {
                let key = format!("//blp/svc{}", i % KEY_COUNT);
                let t0 = Instant::now();
                let _ = cache.get(&key);
                let ns = t0.elapsed().as_nanos() as u64;
                let _ = h.record(ns.max(1));
                i = i.wrapping_add(1);
            }
            h
        }));
    }

    // Writer: re-insert svc0 every WRITE_INTERVAL. Disk IO happens outside the
    // cache's write lock, so we're measuring pure lock contention under steady
    // write pressure.
    let w_cache = Arc::clone(&cache);
    let w_stop = Arc::clone(&stop);
    let writer = thread::spawn(move || {
        while !w_stop.load(Ordering::Relaxed) {
            w_cache.insert("//blp/svc0", make_schema("//blp/svc0"));
            thread::sleep(WRITE_INTERVAL);
        }
    });

    thread::sleep(BENCH_DURATION);
    stop.store(true, Ordering::Release);
    writer.join().unwrap();

    let mut total = new_hist();
    for h in handles {
        total.add(h.join().unwrap()).unwrap();
    }
    total
}

fn bench_field(readers: usize) -> Histogram<u64> {
    let temp = TempDir::new().unwrap();
    let resolver = Arc::new(FieldTypeResolver::with_cache_path(
        temp.path().join("field_cache.json"),
    ));
    const KEY_COUNT: u32 = 500;
    for i in 0..KEY_COUNT {
        resolver.insert(make_field(i));
    }

    let stop = Arc::new(AtomicBool::new(false));
    let mut handles = Vec::with_capacity(readers);

    for _ in 0..readers {
        let resolver = Arc::clone(&resolver);
        let stop = Arc::clone(&stop);
        handles.push(thread::spawn(move || {
            let mut h = new_hist();
            let mut i: u32 = 0;
            while !stop.load(Ordering::Relaxed) {
                let key = format!("FIELD_{}", i % KEY_COUNT);
                let t0 = Instant::now();
                let _ = resolver.get(&key);
                let ns = t0.elapsed().as_nanos() as u64;
                let _ = h.record(ns.max(1));
                i = i.wrapping_add(1);
            }
            h
        }));
    }

    // Writer inserts a new (growing) field every WRITE_INTERVAL — mirrors the
    // incremental //blp/apiflds discovery pattern during a session.
    let w_resolver = Arc::clone(&resolver);
    let w_stop = Arc::clone(&stop);
    let writer = thread::spawn(move || {
        let mut n = KEY_COUNT;
        while !w_stop.load(Ordering::Relaxed) {
            w_resolver.insert(make_field(n));
            n += 1;
            thread::sleep(WRITE_INTERVAL);
        }
    });

    thread::sleep(BENCH_DURATION);
    stop.store(true, Ordering::Release);
    writer.join().unwrap();

    let mut total = new_hist();
    for h in handles {
        total.add(h.join().unwrap()).unwrap();
    }
    total
}

fn results_path(label: &str) -> std::path::PathBuf {
    // CARGO_MANIFEST_DIR = <repo>/crates/xbbg-bench; go up two to workspace root.
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("workspace root")
        .to_path_buf();
    root.join("target")
        .join("bench_cache")
        .join(format!("{label}.txt"))
}

fn main() {
    let label = std::env::var("BENCH_LABEL").unwrap_or_else(|_| "run".to_string());

    println!(
        "cache contention bench — label=\"{label}\" duration={:?} write_every={:?}",
        BENCH_DURATION, WRITE_INTERVAL
    );
    println!("------------------------------------------------------------------------------------------------");

    let mut lines = Vec::new();
    for &concurrency in READER_CONCURRENCY {
        let h = bench_schema(concurrency);
        let line = percentiles(&format!("schema readers={concurrency:>4}"), &h);
        println!("{line}");
        lines.push(line);
    }
    for &concurrency in READER_CONCURRENCY {
        let h = bench_field(concurrency);
        let line = percentiles(&format!("field  readers={concurrency:>4}"), &h);
        println!("{line}");
        lines.push(line);
    }

    let path = results_path(&label);
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(&path, lines.join("\n") + "\n");
    println!("------------------------------------------------------------------------------------------------");
    println!("results saved to {}", path.display());
}

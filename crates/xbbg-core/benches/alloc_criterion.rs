//! Allocation-aware Criterion benchmarks.
//!
//! Uses tracking_allocator to measure allocations alongside timing.
//! This integrates allocation metrics into standard Criterion benchmarks.
//!
//! Run with: cargo bench --package xbbg_core --bench alloc_criterion
//!
//! For live Bloomberg:
//!   cargo bench --package xbbg_core --bench alloc_criterion --no-default-features --features live

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicU64, Ordering};
use xbbg_core::datetime::HighPrecisionDatetime;
use xbbg_core::ffi;
use xbbg_core::Name;

// =============================================================================
// Custom Allocator for Tracking
// =============================================================================

/// A simple tracking allocator that wraps System.
struct TrackingAlloc {
    alloc_count: AtomicU64,
    alloc_bytes: AtomicU64,
    dealloc_count: AtomicU64,
    dealloc_bytes: AtomicU64,
}

impl TrackingAlloc {
    const fn new() -> Self {
        Self {
            alloc_count: AtomicU64::new(0),
            alloc_bytes: AtomicU64::new(0),
            dealloc_count: AtomicU64::new(0),
            dealloc_bytes: AtomicU64::new(0),
        }
    }

    #[allow(dead_code)]
    fn reset(&self) {
        self.alloc_count.store(0, Ordering::SeqCst);
        self.alloc_bytes.store(0, Ordering::SeqCst);
        self.dealloc_count.store(0, Ordering::SeqCst);
        self.dealloc_bytes.store(0, Ordering::SeqCst);
    }

    fn snapshot(&self) -> AllocSnapshot {
        AllocSnapshot {
            alloc_count: self.alloc_count.load(Ordering::SeqCst),
            alloc_bytes: self.alloc_bytes.load(Ordering::SeqCst),
            dealloc_count: self.dealloc_count.load(Ordering::SeqCst),
            dealloc_bytes: self.dealloc_bytes.load(Ordering::SeqCst),
        }
    }
}

unsafe impl GlobalAlloc for TrackingAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        self.alloc_count.fetch_add(1, Ordering::Relaxed);
        self.alloc_bytes
            .fetch_add(layout.size() as u64, Ordering::Relaxed);
        System.alloc(layout)
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        self.dealloc_count.fetch_add(1, Ordering::Relaxed);
        self.dealloc_bytes
            .fetch_add(layout.size() as u64, Ordering::Relaxed);
        System.dealloc(ptr, layout)
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        // Count as dealloc + alloc
        self.dealloc_count.fetch_add(1, Ordering::Relaxed);
        self.dealloc_bytes
            .fetch_add(layout.size() as u64, Ordering::Relaxed);
        self.alloc_count.fetch_add(1, Ordering::Relaxed);
        self.alloc_bytes
            .fetch_add(new_size as u64, Ordering::Relaxed);
        System.realloc(ptr, layout, new_size)
    }
}

#[global_allocator]
static ALLOCATOR: TrackingAlloc = TrackingAlloc::new();

#[derive(Debug, Clone, Copy)]
struct AllocSnapshot {
    alloc_count: u64,
    alloc_bytes: u64,
    dealloc_count: u64,
    dealloc_bytes: u64,
}

impl AllocSnapshot {
    fn diff(&self, other: &AllocSnapshot) -> AllocDiff {
        AllocDiff {
            allocs: self.alloc_count.saturating_sub(other.alloc_count),
            bytes: self.alloc_bytes.saturating_sub(other.alloc_bytes),
            deallocs: self.dealloc_count.saturating_sub(other.dealloc_count),
            freed_bytes: self.dealloc_bytes.saturating_sub(other.dealloc_bytes),
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct AllocDiff {
    allocs: u64,
    bytes: u64,
    deallocs: u64,
    freed_bytes: u64,
}

impl std::fmt::Display for AllocDiff {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{} allocs ({} bytes), {} deallocs ({} freed)",
            self.allocs, self.bytes, self.deallocs, self.freed_bytes
        )
    }
}

/// Measure allocations for a closure.
fn measure_allocs<F, R>(f: F) -> (R, AllocDiff)
where
    F: FnOnce() -> R,
{
    let before = ALLOCATOR.snapshot();
    let result = f();
    let after = ALLOCATOR.snapshot();
    (result, after.diff(&before))
}

// =============================================================================
// Datetime Benchmarks with Allocation Tracking
// =============================================================================

fn make_datetime(
    year: u16,
    month: u8,
    day: u8,
    hours: u8,
    minutes: u8,
    seconds: u8,
    milliseconds: u16,
) -> HighPrecisionDatetime {
    HighPrecisionDatetime::from_raw(ffi::blpapi_HighPrecisionDatetime_t {
        parts: 0xFF,
        hours,
        minutes,
        seconds,
        milliseconds,
        month,
        day,
        year,
        offset: 0,
        picoseconds: 0,
    })
}

fn bench_datetime_with_allocs(c: &mut Criterion) {
    let mut group = c.benchmark_group("datetime_allocs");

    let dt = make_datetime(2024, 6, 15, 14, 30, 45, 123);

    // Benchmark to_micros with allocation tracking
    group.bench_function("to_micros", |b| {
        b.iter_custom(|iters| {
            let before = ALLOCATOR.snapshot();
            let start = std::time::Instant::now();
            for _ in 0..iters {
                black_box(black_box(&dt).to_micros());
            }
            let elapsed = start.elapsed();
            let after = ALLOCATOR.snapshot();
            let diff = after.diff(&before);

            // Print allocation info for significant runs
            if iters > 100 && diff.allocs > 0 {
                eprintln!(
                    "  to_micros: {} iters -> {} allocs, {} bytes",
                    iters, diff.allocs, diff.bytes
                );
            }

            elapsed
        });
    });

    // Benchmark to_nanos
    group.bench_function("to_nanos", |b| {
        b.iter_custom(|iters| {
            let before = ALLOCATOR.snapshot();
            let start = std::time::Instant::now();
            for _ in 0..iters {
                black_box(black_box(&dt).to_nanos());
            }
            let elapsed = start.elapsed();
            let after = ALLOCATOR.snapshot();
            let diff = after.diff(&before);

            if iters > 100 && diff.allocs > 0 {
                eprintln!(
                    "  to_nanos: {} iters -> {} allocs, {} bytes",
                    iters, diff.allocs, diff.bytes
                );
            }

            elapsed
        });
    });

    group.finish();
}

// =============================================================================
// Name Benchmarks with Allocation Tracking
// =============================================================================

fn bench_name_with_allocs(c: &mut Criterion) {
    let mut group = c.benchmark_group("name_allocs");

    // Name comparison (should be zero-alloc)
    let name1 = Name::new("PX_LAST").expect("name");
    let name2 = Name::new("PX_LAST").expect("name");

    group.bench_function("compare", |b| {
        b.iter_custom(|iters| {
            let before = ALLOCATOR.snapshot();
            let start = std::time::Instant::now();
            for _ in 0..iters {
                black_box(black_box(&name1) == black_box(&name2));
            }
            let elapsed = start.elapsed();
            let after = ALLOCATOR.snapshot();
            let diff = after.diff(&before);

            if iters > 100 && diff.allocs > 0 {
                eprintln!(
                    "  name_compare: {} iters -> {} allocs (should be 0!)",
                    iters, diff.allocs
                );
            }

            elapsed
        });
    });

    // Name to_str (should be zero-alloc - just pointer deref)
    let name = Name::new("SECURITY_DATA").expect("name");

    group.bench_function("to_str", |b| {
        b.iter_custom(|iters| {
            let before = ALLOCATOR.snapshot();
            let start = std::time::Instant::now();
            for _ in 0..iters {
                black_box(black_box(&name).as_str());
            }
            let elapsed = start.elapsed();
            let after = ALLOCATOR.snapshot();
            let diff = after.diff(&before);

            if iters > 100 && diff.allocs > 0 {
                eprintln!(
                    "  name_to_str: {} iters -> {} allocs (should be 0!)",
                    iters, diff.allocs
                );
            }

            elapsed
        });
    });

    // Name get_or_intern (cached lookup - should be zero-alloc after first)
    let _ = Name::get_or_intern("CACHED_FIELD");

    group.bench_function("get_or_intern_cached", |b| {
        b.iter_custom(|iters| {
            let before = ALLOCATOR.snapshot();
            let start = std::time::Instant::now();
            for _ in 0..iters {
                black_box(Name::get_or_intern("CACHED_FIELD"));
            }
            let elapsed = start.elapsed();
            let after = ALLOCATOR.snapshot();
            let diff = after.diff(&before);

            if iters > 100 && diff.allocs > 0 {
                eprintln!(
                    "  get_or_intern_cached: {} iters -> {} allocs",
                    iters, diff.allocs
                );
            }

            elapsed
        });
    });

    group.finish();
}

// =============================================================================
// Parameterized Allocation Benchmarks (like Manuel's MessageSize)
// =============================================================================

fn bench_varying_field_count(c: &mut Criterion) {
    let mut group = c.benchmark_group("field_count_allocs");

    // Simulate different message sizes by creating varying numbers of Names
    for field_count in [1, 5, 10, 50, 100] {
        group.bench_with_input(
            BenchmarkId::new("intern_n_names", field_count),
            &field_count,
            |b, &n| {
                // Pre-generate field names
                let field_names: Vec<String> = (0..n).map(|i| format!("FIELD_{}", i)).collect();

                b.iter_custom(|iters| {
                    let before = ALLOCATOR.snapshot();
                    let start = std::time::Instant::now();

                    for _ in 0..iters {
                        for name in &field_names {
                            black_box(Name::get_or_intern(name));
                        }
                    }

                    let elapsed = start.elapsed();
                    let after = ALLOCATOR.snapshot();
                    let diff = after.diff(&before);

                    // Report allocation per operation
                    if iters > 10 {
                        let allocs_per_iter = diff.allocs as f64 / iters as f64;
                        let bytes_per_iter = diff.bytes as f64 / iters as f64;
                        eprintln!(
                            "  {} fields x {} iters: {:.1} allocs/iter, {:.1} bytes/iter",
                            n, iters, allocs_per_iter, bytes_per_iter
                        );
                    }

                    elapsed
                });
            },
        );
    }

    group.finish();
}

// =============================================================================
// Summary Report
// =============================================================================

fn print_alloc_summary(c: &mut Criterion) {
    // Final summary benchmark that prints allocation stats
    let mut group = c.benchmark_group("allocation_summary");

    group.bench_function("summary", |b| {
        b.iter(|| {
            // Measure some representative operations
            let (_, name_allocs) = measure_allocs(|| {
                for _ in 0..100 {
                    black_box(Name::get_or_intern("SUMMARY_TEST"));
                }
            });

            let dt = make_datetime(2024, 1, 1, 12, 0, 0, 0);
            let (_, dt_allocs) = measure_allocs(|| {
                for _ in 0..100 {
                    black_box(dt.to_micros());
                }
            });

            (name_allocs, dt_allocs)
        });
    });

    group.finish();

    // Print final summary
    println!("\n");
    println!("=================================================================");
    println!("  Allocation Summary");
    println!("=================================================================");
    println!("  Zero-allocation operations (hot path targets):");
    println!("    - Name comparison");
    println!("    - Name.as_str()");
    println!("    - Name.get_or_intern() for cached names");
    println!("    - datetime.to_micros() / to_nanos()");
    println!();
    println!("  Expected allocations:");
    println!("    - Name.new() for uncached names");
    println!("    - Request building (Bloomberg SDK internal)");
    println!("    - Response parsing (element tree traversal)");
    println!("=================================================================\n");
}

criterion_group!(
    benches,
    bench_datetime_with_allocs,
    bench_name_with_allocs,
    bench_varying_field_count,
    print_alloc_summary,
);

criterion_main!(benches);

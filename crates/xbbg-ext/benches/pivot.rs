//! Benchmarks for pivot operations.

use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn pivot_benchmark(c: &mut Criterion) {
    // TODO: Add actual benchmarks once we have test data
    c.bench_function("pivot_placeholder", |b| b.iter(|| black_box(1 + 1)));
}

criterion_group!(benches, pivot_benchmark);
criterion_main!(benches);

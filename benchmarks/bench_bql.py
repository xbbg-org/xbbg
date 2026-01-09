"""Benchmark BQL (Bloomberg Query Language) across packages.

Data usage: ~10-20 data points per run
"""

from __future__ import annotations

from dataclasses import dataclass
import statistics
import time
import tracemalloc

from config import BQL_MULTI, BQL_SIMPLE, ITERATIONS, WARMUP_ITERATIONS


@dataclass
class BenchmarkResult:
    """Result from a benchmark run."""

    package: str
    operation: str
    cold_start_ms: float
    warm_mean_ms: float
    warm_median_ms: float
    warm_p95_ms: float
    warm_p99_ms: float
    warm_std_ms: float
    memory_peak_mb: float
    data_shape: tuple
    iterations: int


def benchmark_bql(package_name: str, bql_func, query: str) -> BenchmarkResult:
    """Benchmark BQL operation.

    Args:
        package_name: Name of package being benchmarked
        bql_func: Function to call for bql(query)
        query: BQL query string

    Returns:
        BenchmarkResult with timing and memory stats
    """
    times = []
    result = None

    # Start memory tracking
    tracemalloc.start()

    # Warmup iterations (discarded)
    for _ in range(WARMUP_ITERATIONS):
        bql_func(query)

    # Measured iterations
    for _i in range(ITERATIONS):
        start = time.perf_counter()
        result = bql_func(query)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    # Get memory usage
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    memory_mb = peak / 1024 / 1024

    # Get result shape
    if hasattr(result, "shape"):
        shape = result.shape
    elif hasattr(result, "__len__"):
        shape = (len(result),)
    else:
        shape = (1,)

    # Calculate statistics
    cold_start = times[0]
    warm_times = times[1:] if len(times) > 1 else times
    warm_mean = statistics.mean(warm_times)
    warm_median = statistics.median(warm_times)
    warm_std = statistics.stdev(warm_times) if len(warm_times) > 1 else 0

    # Percentiles
    sorted_times = sorted(warm_times)
    p95_idx = int(len(sorted_times) * 0.95)
    p99_idx = int(len(sorted_times) * 0.99)
    warm_p95 = sorted_times[p95_idx] if sorted_times else warm_mean
    warm_p99 = sorted_times[p99_idx] if sorted_times else warm_mean

    # Truncate query for display
    query_display = query if len(query) <= 40 else query[:37] + "..."

    return BenchmarkResult(
        package=package_name,
        operation=f"bql({query_display})",
        cold_start_ms=cold_start,
        warm_mean_ms=warm_mean,
        warm_median_ms=warm_median,
        warm_p95_ms=warm_p95,
        warm_p99_ms=warm_p99,
        warm_std_ms=warm_std,
        memory_peak_mb=memory_mb,
        data_shape=shape,
        iterations=ITERATIONS,
    )


def run_xbbg_rust(query: str):
    """Benchmark xbbg Rust version."""
    import xbbg

    return xbbg.bql(query)


def run_xbbg_legacy(query: str):
    """Benchmark legacy xbbg Python version."""
    try:
        import xbbg_legacy

        return xbbg_legacy.bql(query)
    except ImportError:
        print("Warning: xbbg legacy not installed")
        return None


def run_pdblp(query: str):
    """Benchmark pdblp."""
    # pdblp does not support BQL directly
    print("Warning: pdblp does not support BQL")
    return


def run_bbg_fetch(query: str):
    """Benchmark bbg-fetch."""
    try:
        import bbg_fetch  # noqa: F401

        # bbg-fetch may not support BQL
        print("Warning: bbg-fetch BQL support needs verification")
        return
    except ImportError:
        print("Warning: bbg-fetch not installed")
        return


def main():
    """Run all BQL benchmarks."""
    print("=" * 70)
    print("BQL (Bloomberg Query Language) Benchmark")
    print("=" * 70)
    print(f"\nIterations: {ITERATIONS}")
    print(f"Warmup: {WARMUP_ITERATIONS}")

    results = []

    # Test 1: Simple query
    print("\n\nTest 1: Simple BQL query")
    print("-" * 70)
    print(f"Query: {BQL_SIMPLE}")

    if True:  # xbbg Rust
        print("\nRunning xbbg (Rust)...")
        try:
            result = benchmark_bql("xbbg-rust", run_xbbg_rust, BQL_SIMPLE)
            results.append(result)
            print(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    if True:  # xbbg Legacy
        print("Running xbbg (legacy)...")
        try:
            result = benchmark_bql("xbbg-legacy", run_xbbg_legacy, BQL_SIMPLE)
            if result:
                results.append(result)
                print(
                    f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                )
        except Exception as e:
            print(f"  ✗ Error: {e}")

    # Test 2: Multi-security query
    print("\n\nTest 2: Multi-security BQL query")
    print("-" * 70)
    print(f"Query: {BQL_MULTI}")

    if True:  # xbbg Rust
        print("\nRunning xbbg (Rust)...")
        try:
            result = benchmark_bql("xbbg-rust", run_xbbg_rust, BQL_MULTI)
            results.append(result)
            print(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    if True:  # xbbg Legacy
        print("Running xbbg (legacy)...")
        try:
            result = benchmark_bql("xbbg-legacy", run_xbbg_legacy, BQL_MULTI)
            if result:
                results.append(result)
                print(
                    f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB, shape={result.data_shape}"
                )
        except Exception as e:
            print(f"  ✗ Error: {e}")

    # Print summary
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for result in results:
        print(f"\n{result.package} - {result.operation}")
        print(f"  Cold start: {result.cold_start_ms:.2f}ms")
        print(f"  Warm mean:  {result.warm_mean_ms:.2f}ms ± {result.warm_std_ms:.2f}ms")
        print(f"  Warm p95:   {result.warm_p95_ms:.2f}ms")
        print(f"  Memory:     {result.memory_peak_mb:.2f}MB")
        print(f"  Shape:      {result.data_shape}")

    # Calculate speedups
    xbbg_rust_results = [r for r in results if r.package == "xbbg-rust"]
    legacy_results = [r for r in results if r.package == "xbbg-legacy"]

    if xbbg_rust_results and legacy_results:
        rust_time = sum(r.warm_mean_ms for r in xbbg_rust_results)
        legacy_time = sum(r.warm_mean_ms for r in legacy_results)
        speedup = legacy_time / rust_time if rust_time > 0 else 0

        print(f"\n\n{'=' * 70}")
        print(f"xbbg Rust vs Legacy Speedup: {speedup:.2f}x faster")
        print(f"{'=' * 70}")

    return results


if __name__ == "__main__":
    main()

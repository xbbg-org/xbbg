"""Benchmark BDP (Reference Data) across packages.

Data usage: ~10-20 data points per run
"""

from __future__ import annotations

import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dataclasses import dataclass
import statistics
import time
import tracemalloc

logger = logging.getLogger(__name__)

from config import (
    FIELDS_MULTI,
    FIELDS_SINGLE,
    ITERATIONS,
    TICKERS_MULTI,
    TICKERS_SINGLE,
    WARMUP_ITERATIONS,
)


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


def benchmark_bdp(package_name: str, bdp_func, tickers, fields) -> BenchmarkResult:
    """Benchmark BDP operation.

    Args:
        package_name: Name of package being benchmarked
        bdp_func: Function to call for bdp(tickers, fields)
        tickers: List of tickers or single ticker
        fields: List of fields or single field

    Returns:
        BenchmarkResult with timing and memory stats
    """
    times = []
    result = None

    # Start memory tracking
    tracemalloc.start()

    # Warmup iterations (discarded)
    for _ in range(WARMUP_ITERATIONS):
        bdp_func(tickers, fields)

    # Measured iterations
    for _i in range(ITERATIONS):
        start = time.perf_counter()
        result = bdp_func(tickers, fields)
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

    return BenchmarkResult(
        package=package_name,
        operation=f"bdp({len(tickers) if isinstance(tickers, list) else 1}t, {len(fields) if isinstance(fields, list) else 1}f)",
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


def run_xbbg_rust(tickers, fields):
    """Benchmark xbbg Rust version."""
    import xbbg

    return xbbg.bdp(tickers, fields)


def run_xbbg_legacy(tickers, fields):
    """Benchmark legacy xbbg Python version."""
    # Assume xbbg 0.10.3 is installed separately
    # (Could use virtual env or rename import)
    try:
        import xbbg_legacy

        return xbbg_legacy.bdp(tickers, fields)
    except ImportError:
        logger.warning("xbbg legacy not installed (pip install xbbg==0.10.3)")
        return None


def run_blpapi_raw(tickers, fields):
    """Benchmark raw blpapi (with minimal wrapper)."""
    import blpapi

    # Minimal wrapper for consistent API
    session_options = blpapi.SessionOptions()
    session_options.setServerHost("localhost")
    session_options.setServerPort(8194)

    session = blpapi.Session(session_options)
    if not session.start():
        raise RuntimeError("Failed to start session")

    if not session.openService("//blp/refdata"):
        raise RuntimeError("Failed to open service")

    ref_data_service = session.getService("//blp/refdata")
    request = ref_data_service.createRequest("ReferenceDataRequest")

    # Add tickers and fields
    ticker_list = tickers if isinstance(tickers, list) else [tickers]
    field_list = fields if isinstance(fields, list) else [fields]

    for ticker in ticker_list:
        request.append("securities", ticker)
    for field in field_list:
        request.append("fields", field)

    session.sendRequest(request)

    # Collect results
    results = []
    while True:
        event = session.nextEvent(500)
        if event.eventType() == blpapi.Event.RESPONSE:
            results.extend(list(event))
            break

    session.stop()
    return results


def run_pdblp(tickers, fields):
    """Benchmark pdblp."""
    try:
        import pdblp

        con = pdblp.BCon(debug=False, timeout=5000)
        con.start()

        ticker_list = tickers if isinstance(tickers, list) else [tickers]
        field_list = fields if isinstance(fields, list) else [fields]

        result = con.ref(ticker_list, field_list)
        con.stop()
        return result
    except ImportError:
        logger.warning("pdblp not installed (pip install pdblp)")
        return None


def run_bbg_fetch(tickers, fields):
    """Benchmark bbg-fetch."""
    try:
        import bbg_fetch  # noqa: F401

        # bbg-fetch has different API, adapt as needed
        # This is a placeholder - adjust based on actual bbg-fetch API
        logger.warning("bbg-fetch wrapper not implemented yet")
        return
    except ImportError:
        logger.warning("bbg-fetch not installed (pip install bbg-fetch)")
        return


def main():
    """Run all BDP benchmarks."""
    logger.info("=" * 70)
    logger.info("BDP (Reference Data) Benchmark")
    logger.info("=" * 70)
    logger.info(f"\nIterations: {ITERATIONS}")
    logger.info(f"Warmup: {WARMUP_ITERATIONS}")

    results = []

    # Test 1: Single ticker, single field
    logger.info("\n\nTest 1: Single ticker, single field")
    logger.info("-" * 70)

    if True:  # xbbg Rust
        logger.info("Running xbbg (Rust)...")
        try:
            result = benchmark_bdp("xbbg-rust", run_xbbg_rust, TICKERS_SINGLE[0], FIELDS_SINGLE[0])
            results.append(result)
            logger.info(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    if True:  # xbbg Legacy
        logger.info("Running xbbg (legacy)...")
        try:
            result = benchmark_bdp("xbbg-legacy", run_xbbg_legacy, TICKERS_SINGLE[0], FIELDS_SINGLE[0])
            if result:
                results.append(result)
                logger.info(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    if True:  # pdblp
        logger.info("Running pdblp...")
        try:
            result = benchmark_bdp("pdblp", run_pdblp, TICKERS_SINGLE[0], FIELDS_SINGLE[0])
            if result:
                results.append(result)
                logger.info(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    # Test 2: Multiple tickers, multiple fields
    logger.info("\n\nTest 2: Multiple tickers, multiple fields")
    logger.info("-" * 70)

    if True:  # xbbg Rust
        logger.info("Running xbbg (Rust)...")
        try:
            result = benchmark_bdp("xbbg-rust", run_xbbg_rust, TICKERS_MULTI, FIELDS_MULTI)
            results.append(result)
            logger.info(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    if True:  # xbbg Legacy
        logger.info("Running xbbg (legacy)...")
        try:
            result = benchmark_bdp("xbbg-legacy", run_xbbg_legacy, TICKERS_MULTI, FIELDS_MULTI)
            if result:
                results.append(result)
                logger.info(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    if True:  # pdblp
        logger.info("Running pdblp...")
        try:
            result = benchmark_bdp("pdblp", run_pdblp, TICKERS_MULTI, FIELDS_MULTI)
            if result:
                results.append(result)
                logger.info(f"  ✓ {result.warm_mean_ms:.2f}ms (mean), {result.memory_peak_mb:.2f}MB")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")

    # Print summary
    logger.info("\n\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    for result in results:
        logger.info(f"\n{result.package} - {result.operation}")
        logger.info(f"  Cold start: {result.cold_start_ms:.2f}ms")
        logger.info(f"  Warm mean:  {result.warm_mean_ms:.2f}ms ± {result.warm_std_ms:.2f}ms")
        logger.info(f"  Warm p95:   {result.warm_p95_ms:.2f}ms")
        logger.info(f"  Memory:     {result.memory_peak_mb:.2f}MB")
        logger.info(f"  Shape:      {result.data_shape}")

    # Calculate speedups
    xbbg_rust_results = [r for r in results if r.package == "xbbg-rust"]
    legacy_results = [r for r in results if r.package == "xbbg-legacy"]

    if xbbg_rust_results and legacy_results:
        rust_time = sum(r.warm_mean_ms for r in xbbg_rust_results)
        legacy_time = sum(r.warm_mean_ms for r in legacy_results)
        speedup = legacy_time / rust_time if rust_time > 0 else 0

        logger.info(f"\n\n{'=' * 70}")
        logger.info(f"xbbg Rust vs Legacy Speedup: {speedup:.2f}x faster")
        logger.info(f"{'=' * 70}")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()

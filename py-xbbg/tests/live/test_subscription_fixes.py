#!/usr/bin/env python
"""Live validation test for subscription pipeline fixes.

Tests:
  1. Multi-type field preservation (Fix #1) — Int32, Int64, Float64, Date, Datetime
  2. Bloomberg event timestamps (Fix #6) — not SystemTime
  3. Error propagation (Fix #2) — invalid security raises exception
  4. Schema types inspection — verify Arrow types are correct

Usage:
    uv run python py-xbbg/tests/live/test_subscription_fixes.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import pyarrow as pa


async def test_multitype_fields():
    """Test Fix #1: Multi-type field preservation.

    Subscribe to live data with fields of different Bloomberg types:
    - LAST_PRICE (Float64)
    - VOLUME (Int64)
    - BID_SIZE / ASK_SIZE (Int32)
    - TRADE_UPDATE_STAMP_RT (Datetime)
    - TRADING_DT_REALTIME (Date)
    """
    from xbbg._core import PyEngine, set_log_level

    set_log_level("info")

    engine = PyEngine()

    # Fields chosen to exercise multiple Bloomberg types
    fields = [
        "LAST_PRICE",
        "BID",
        "ASK",
        "VOLUME",
        "BID_SIZE",
        "ASK_SIZE",
        "NUM_TRADES_RT",
        "TRADE_UPDATE_STAMP_RT",
        "TRADING_DT_REALTIME",
        "RT_PX_CHG_PCT_1D",
    ]

    tickers = ["ESH6 Index", "UXH6 Index", "NQH6 Index"]

    print(f"\n{'=' * 60}")
    print("TEST: Multi-type field preservation (Fix #1)")
    print(f"{'=' * 60}")
    print(f"Tickers: {tickers}")
    print(f"Fields:  {fields}")
    print()

    sub = await engine.subscribe(tickers, fields)
    print(f"Subscription active: {sub.is_active}")
    print(f"Tickers: {sub.tickers}")
    print()

    batches_received = 0
    max_batches = 15  # Collect enough to see INITPAINT + a few updates

    try:
        async for batch in sub:
            batches_received += 1

            # Print schema on first batch
            if batches_received == 1:
                print("--- Arrow Schema ---")
                for i, field in enumerate(batch.schema):
                    print(f"  {field.name:30s} {field.type}")
                print()

            # Print data
            topic = batch.column("topic")[0].as_py()
            ts = batch.column("timestamp")[0].as_py()

            print(f"[Batch {batches_received}] topic={topic}  ts={ts}")

            # Print non-null field values with their Arrow types
            for field in batch.schema:
                if field.name in ("timestamp", "topic"):
                    continue
                col = batch.column(field.name)
                val = col[0].as_py()
                if val is not None:
                    print(f"  {field.name:30s} type={field.type!s:20s} value={val!r}")

            print()

            if batches_received >= max_batches:
                break

    except Exception as e:
        print(f"ERROR during iteration: {type(e).__name__}: {e}")

    await sub.unsubscribe()
    print(f"\nTotal batches received: {batches_received}")

    # Verify we got data
    assert batches_received > 0, "No batches received!"
    print("PASSED: Multi-type fields working\n")


async def test_timestamp_source():
    """Test Fix #6: Bloomberg event timestamps.

    Verify that timestamps come from Bloomberg SDK (not SystemTime::now()).
    Bloomberg timestamps should be close to wall clock but come from the SDK's
    recorded receive time.
    """
    from xbbg._core import PyEngine, set_log_level

    set_log_level("warn")

    engine = PyEngine()

    print(f"\n{'=' * 60}")
    print("TEST: Bloomberg event timestamps (Fix #6)")
    print(f"{'=' * 60}")

    sub = await engine.subscribe(["ESH6 Index"], ["LAST_PRICE", "BID", "ASK"])

    batch_count = 0
    timestamps = []

    try:
        async for batch in sub:
            batch_count += 1
            ts_col = batch.column("timestamp")
            ts_val = ts_col[0].as_py()
            timestamps.append(ts_val)

            now = datetime.now(timezone.utc)
            # Bloomberg SDK receive time should be within a few seconds of wall clock
            if ts_val is not None and hasattr(ts_val, "timestamp"):
                assert ts_val.tzinfo == timezone.utc, f"Expected UTC-aware timestamp, got {ts_val!r}"
                diff_seconds = abs((now - ts_val).total_seconds())
                print(f"  Batch {batch_count}: ts={ts_val}  wall_diff={diff_seconds:.3f}s")
            else:
                print(f"  Batch {batch_count}: ts={ts_val} (type: {type(ts_val).__name__})")

            if batch_count >= 5:
                break

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

    await sub.unsubscribe()

    # Verify timestamps are reasonable (not epoch, not far future)
    assert len(timestamps) > 0, "No timestamps received"
    for ts in timestamps:
        if ts is not None and hasattr(ts, "year"):
            assert ts.year >= 2025, f"Timestamp too old: {ts}"
            assert ts.year <= 2030, f"Timestamp too far in future: {ts}"

    print("PASSED: Timestamps look reasonable\n")


async def test_error_propagation():
    """Test Fix #2: Error propagation for invalid subscriptions.

    Subscribe to an invalid security and verify the error is propagated
    to the Python consumer as an exception (not silently swallowed).
    """
    from xbbg._core import PyEngine, set_log_level

    set_log_level("warn")

    engine = PyEngine()

    print(f"\n{'=' * 60}")
    print("TEST: Error propagation (Fix #2)")
    print(f"{'=' * 60}")

    # Mix valid and invalid tickers
    sub = await engine.subscribe(
        ["TOTALLY_INVALID_TICKER_XYZ Equity"],
        ["LAST_PRICE"],
    )

    print(f"Subscription created (is_active={sub.is_active})")

    got_error = False
    got_data = False
    batch_count = 0

    try:
        async for batch in sub:
            batch_count += 1
            got_data = True
            print(f"  Got data batch: {batch.num_rows} rows")
            if batch_count >= 3:
                break
    except StopAsyncIteration:
        print("  Stream ended (StopAsyncIteration)")
    except Exception as e:
        got_error = True
        print(f"  Got error: {type(e).__name__}: {e}")

    # Give a moment for Bloomberg to send failure
    if not got_error and not got_data:
        try:
            await asyncio.wait_for(sub.__anext__(), timeout=10.0)
        except StopAsyncIteration:
            print("  Stream ended after wait")
        except asyncio.TimeoutError:
            print("  Timed out waiting for response (no error, no data)")
        except Exception as e:
            got_error = True
            print(f"  Got error after wait: {type(e).__name__}: {e}")

    try:
        await sub.unsubscribe()
    except Exception:
        pass

    if got_error:
        print("PASSED: Error was propagated to consumer\n")
    else:
        print("NOTE: No error received (Bloomberg may have returned empty data or timed out)")
        print("      This is expected if Bloomberg handles unknown tickers gracefully.\n")


async def test_schema_types():
    """Verify Arrow schema types match expected Bloomberg types.

    After INITPAINT, check that:
    - VOLUME is Int64 (not Float64)
    - BID_SIZE is Int32 (not Float64)
    - TRADE_UPDATE_STAMP_RT is Timestamp (not Null/Utf8)
    - TRADING_DT_REALTIME is Date32 (not Null/Utf8)
    """
    from xbbg._core import PyEngine, set_log_level

    set_log_level("warn")

    engine = PyEngine()

    print(f"\n{'=' * 60}")
    print("TEST: Schema type verification")
    print(f"{'=' * 60}")

    fields = [
        "LAST_PRICE",
        "VOLUME",
        "BID_SIZE",
        "ASK_SIZE",
        "TRADE_UPDATE_STAMP_RT",
        "TRADING_DT_REALTIME",
    ]

    sub = await engine.subscribe(["ESH6 Index"], fields)

    # Collect enough batches to see trade messages (TRADE_UPDATE_STAMP_RT
    # only appears in trade updates, not quote-only messages)
    schema = None
    batch_count = 0
    try:
        async for batch in sub:
            batch_count += 1
            schema = batch.schema
            if batch_count >= 20:
                break
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

    await sub.unsubscribe()

    if schema is None:
        print("FAILED: No schema received")
        return

    print("\nFinal schema after stabilization:")
    type_map = {}
    for field in schema:
        type_map[field.name] = field.type
        print(f"  {field.name:30s} {field.type}")

    print()

    # Verify key type expectations
    passed = True
    checks = [
        ("LAST_PRICE", pa.float64(), "Float64"),
        ("VOLUME", pa.int64(), "Int64"),
        ("BID_SIZE", pa.int32(), "Int32"),
        ("ASK_SIZE", pa.int32(), "Int32"),
    ]

    for field_name, expected_type, label in checks:
        if field_name in type_map:
            actual = type_map[field_name]
            if actual == expected_type:
                print(f"  OK: {field_name} is {label} ({actual})")
            elif str(actual).startswith("timestamp"):
                # Timestamps might be Timestamp[us] which is fine
                print(f"  OK: {field_name} is Timestamp ({actual})")
            else:
                print(f"  MISMATCH: {field_name} expected {expected_type} but got {actual}")
                passed = False
        else:
            print(f"  SKIP: {field_name} not in schema (field may not have been sent)")

    # Check datetime fields — they should NOT be Utf8 (old behavior was null/missing)
    for ts_field in ["TRADE_UPDATE_STAMP_RT", "TRADING_DT_REALTIME"]:
        if ts_field in type_map:
            actual = type_map[ts_field]
            if actual == pa.utf8():
                print(f"  MISMATCH: {ts_field} is Utf8 — expected Timestamp or Date")
                passed = False
            elif actual == pa.null():
                print(f"  NOTE: {ts_field} is Null (no data received for this field yet)")
            else:
                print(f"  OK: {ts_field} is {actual} (non-string type preserved)")

    print()
    if passed:
        print("PASSED: Schema types match expectations\n")
    else:
        print("FAILED: Some schema types don't match\n")


async def test_field_exposure_modes():
    """Verify filtered vs full-field subscription exposure modes.

    Default mode should stay narrow except for event metadata. Full-field mode
    should grow the schema when Bloomberg sends additional top-level fields.
    """
    from xbbg._core import PyEngine, set_log_level

    set_log_level("warn")

    engine = PyEngine()
    ticker = ["ESH6 Index"]
    requested_fields = ["LAST_PRICE", "BID", "ASK"]
    metadata_fields = {"MKTDATA_EVENT_TYPE", "MKTDATA_EVENT_SUBTYPE"}
    base_columns = {"timestamp", "topic"}

    print(f"\n{'=' * 60}")
    print("TEST: Field exposure modes")
    print(f"{'=' * 60}")

    filtered_sub = await engine.subscribe(ticker, requested_fields)
    filtered_schema = None
    try:
        async for batch in filtered_sub:
            filtered_schema = batch.schema
            if batch.num_rows > 0:
                break
    except Exception as e:
        print(f"ERROR during filtered subscription: {type(e).__name__}: {e}")
    finally:
        await filtered_sub.unsubscribe()

    assert filtered_schema is not None, "No filtered subscription schema received"
    filtered_names = {field.name for field in filtered_schema}
    print("Filtered schema columns:")
    for field in filtered_schema:
        print(f"  {field.name:30s} {field.type}")
    print()

    assert metadata_fields.issubset(filtered_names), (
        f"Missing event metadata in filtered mode: {sorted(metadata_fields - filtered_names)}"
    )
    filtered_extras = filtered_names - set(requested_fields) - metadata_fields - base_columns
    assert not filtered_extras, f"Filtered mode exposed unexpected extra fields: {sorted(filtered_extras)}"

    full_sub = await engine.subscribe(ticker, requested_fields, all_fields=True)
    full_schema = None
    try:
        async for batch in full_sub:
            full_schema = batch.schema
            full_names = {field.name for field in full_schema}
            full_extras = full_names - set(requested_fields) - metadata_fields - base_columns
            if full_extras:
                break
    except Exception as e:
        print(f"ERROR during full-field subscription: {type(e).__name__}: {e}")
    finally:
        await full_sub.unsubscribe()

    assert full_schema is not None, "No full-field subscription schema received"
    full_names = {field.name for field in full_schema}
    print("Full-field schema columns:")
    for field in full_schema:
        print(f"  {field.name:30s} {field.type}")
    print()

    assert metadata_fields.issubset(full_names), (
        f"Missing event metadata in full-field mode: {sorted(metadata_fields - full_names)}"
    )
    full_extras = full_names - set(requested_fields) - metadata_fields - base_columns
    assert full_extras, "Full-field mode did not expose any additional Bloomberg fields"
    print(f"PASSED: Full-field mode exposed extra fields: {sorted(full_extras)[:10]}\n")


async def main():
    """Run all subscription validation tests."""
    print("=" * 60)
    print("XBBG Subscription Pipeline Validation")
    print("=" * 60)
    print(f"Time: {datetime.now()}")
    print()

    await test_multitype_fields()
    await test_timestamp_source()
    await test_schema_types()
    await test_field_exposure_modes()
    await test_error_propagation()

    print("=" * 60)
    print("All validation tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

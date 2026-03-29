"""Repro for GitHub issue #270: tokio worker thread panic during interpreter shutdown.

When asubscribe() is used with tick_mode=True and ticks are flowing, a tokio worker
thread panics at pyo3::interpreter_lifecycle.rs because Python::attach() is called
after Py_Finalize.

Strategy: Run the event loop in a daemon thread so it's still actively iterating
the subscription (with pending __anext__ tokio futures) when the main thread exits
and triggers Py_Finalize. This widens the race window to near-certain reproduction.

Usage:
    DYLD_LIBRARY_PATH=vendor/blpapi-sdk/3.26.1.1/Darwin .venv/bin/python3 py-xbbg/tests/repro_270_shutdown_panic.py

Pass --safe to call shutdown() properly (should never panic).
"""

import sys
import os
import asyncio
import threading
import time

sys.path.insert(0, "py-xbbg/src")

TICKER = "XBTUSD Curncy"
FIELDS = ["LAST_PRICE", "BID", "ASK"]
WARMUP_TICKS = 20
STREAM_SECONDS = 2


async def stream_forever(ready_event):
    """Subscribe and keep iterating -- never unsubscribe, never stop."""
    import xbbg

    print(f"[repro] subscribing to {TICKER} tick_mode=True, all_fields=True")
    try:
        sub = await xbbg.asubscribe(
            TICKER,
            FIELDS,
            tick_mode=True,
            all_fields=True,
        )
    except Exception as e:
        print(f"[repro] subscription failed (Bloomberg not connected?): {e}")
        ready_event.set()
        return

    count = 0
    async for _tick in sub:
        count += 1
        if count == WARMUP_TICKS:
            print(f"[repro] warmed up with {count} ticks, signaling main thread")
            ready_event.set()
        if count % 10 == 0:
            print(f"[repro] received {count} ticks (still streaming)")
    # This line should never be reached -- main thread exits first
    print(f"[repro] stream ended after {count} ticks")


def run_loop(ready_event):
    """Run the event loop in a daemon thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(stream_forever(ready_event))


def main():
    safe = "--safe" in sys.argv
    mode = "SAFE (with shutdown)" if safe else "UNSAFE (no shutdown -- may panic)"
    print(f"[repro] issue #270 repro -- mode: {mode}")
    print(f"[repro] pid={os.getpid()}")

    if safe:
        # Safe mode: normal asyncio.run with explicit shutdown
        async def safe_run():
            import xbbg
            sub = await xbbg.asubscribe(TICKER, FIELDS, tick_mode=True, all_fields=True)
            count = 0
            async for _tick in sub:
                count += 1
                if count >= WARMUP_TICKS:
                    break
            print(f"[repro] received {count} ticks, unsubscribing and shutting down")
            await sub.unsubscribe()
            xbbg.shutdown()

        asyncio.run(safe_run())
        print("[repro] clean exit")
        return

    # UNSAFE mode: run event loop in daemon thread, exit main thread while streaming.
    # The daemon thread has an active __anext__ tokio future calling Python::attach()
    # to convert RecordBatches. When the main thread exits, Py_Finalize races with
    # the tokio worker thread's Python::attach() call.
    ready = threading.Event()
    t = threading.Thread(target=run_loop, args=(ready,), daemon=True)
    t.start()

    print(f"[repro] waiting for {WARMUP_TICKS} ticks to confirm active streaming...")
    if not ready.wait(timeout=60):
        print("[repro] timeout waiting for ticks -- Bloomberg may not be streaming")
        sys.exit(0)

    # Stream is actively receiving ticks. The daemon thread has a pending __anext__
    # on the tokio runtime. Now let more data flow in to keep the tokio task busy.
    print(f"[repro] streaming for {STREAM_SECONDS}s more to keep tokio tasks active...")
    time.sleep(STREAM_SECONDS)

    # Exit main thread. This triggers:
    # 1. atexit -> signal_shutdown() (non-blocking)
    # 2. Py_Finalize -> interpreter teardown
    # 3. Daemon thread's tokio future calls Python::attach() -> PANIC
    print("[repro] main thread exiting -- Py_Finalize will race with tokio workers...")


if __name__ == "__main__":
    main()

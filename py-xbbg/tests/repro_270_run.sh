#!/usr/bin/env bash
# Run repro_270_shutdown_panic.py multiple times to catch the intermittent panic.
# The panic shows on stderr as a Rust thread panic, not a Python exception.
#
# Usage:
#   cd /path/to/xbbg
#   bash py-xbbg/tests/repro_270_run.sh          # unsafe (should eventually panic)
#   bash py-xbbg/tests/repro_270_run.sh --safe    # safe   (should never panic)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

MAX_RUNS=10
EXTRA_ARGS="${*}"
PANIC_COUNT=0
CRASH_COUNT=0

export DYLD_LIBRARY_PATH="${DYLD_LIBRARY_PATH:-}:vendor/blpapi-sdk/3.26.1.1/Darwin"

echo "=== Issue #270 repro runner ==="
echo "Runs: up to $MAX_RUNS | Args: ${EXTRA_ARGS:-<none>}"
echo ""

for i in $(seq 1 "$MAX_RUNS"); do
    echo "--- Run $i/$MAX_RUNS ---"
    STDERR_FILE=$(mktemp)

    # Run the script, capturing stderr separately to detect Rust panics.
    # Allow non-zero exit (the panic causes a non-zero exit).
    set +e
    .venv/bin/python3 py-xbbg/tests/repro_270_shutdown_panic.py $EXTRA_ARGS 2>"$STDERR_FILE"
    EXIT_CODE=$?
    set -e

    STDERR_CONTENT=$(cat "$STDERR_FILE")
    rm -f "$STDERR_FILE"

    if echo "$STDERR_CONTENT" | grep -q "thread.*panicked"; then
        PANIC_COUNT=$((PANIC_COUNT + 1))
        echo "  *** PANIC DETECTED (exit=$EXIT_CODE) ***"
        echo "$STDERR_CONTENT" | grep "thread.*panicked" | head -3 | sed 's/^/  stderr: /'
    elif [ "$EXIT_CODE" -ne 0 ]; then
        CRASH_COUNT=$((CRASH_COUNT + 1))
        echo "  Non-zero exit ($EXIT_CODE) without panic string"
        [ -n "$STDERR_CONTENT" ] && echo "$STDERR_CONTENT" | head -3 | sed 's/^/  stderr: /'
    else
        echo "  Clean exit"
    fi
    echo ""
done

echo "=== Summary ==="
echo "Total runs:  $MAX_RUNS"
echo "Panics:      $PANIC_COUNT"
echo "Other crash: $CRASH_COUNT"
echo "Clean exits: $((MAX_RUNS - PANIC_COUNT - CRASH_COUNT))"

if [ "$PANIC_COUNT" -gt 0 ]; then
    echo ""
    echo "Issue #270 REPRODUCED ($PANIC_COUNT/$MAX_RUNS runs panicked)"
    exit 1
else
    echo ""
    echo "No panics detected in $MAX_RUNS runs"
    exit 0
fi

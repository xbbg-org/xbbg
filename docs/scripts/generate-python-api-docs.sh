#!/bin/bash
# Generate Python API documentation from docstrings using pydoc-markdown.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DOCS_DIR")"
API_DIR="$DOCS_DIR/src/content/docs/python/api"

if ! command -v pydoc-markdown >/dev/null 2>&1; then
    echo "pydoc-markdown is required. Run docs commands through the pixi docs environment." >&2
    echo "Example: pixi run -e docs docs-build" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
mkdir -p "$API_DIR"

echo "Generating Python API documentation..."

modules=("blp" "services" "exceptions" "schema")
titles=("Bloomberg Data API" "Services and Enums" "Exceptions" "Schema Introspection")
descriptions=(
    "Core API functions for Bloomberg data (bdp, bdh, bds, bdib, bdtick)"
    "Bloomberg service definitions, operations, and enums"
    "Bloomberg API exception hierarchy and error handling"
    "Bloomberg schema introspection and stub generation"
)

for i in "${!modules[@]}"; do
    module="${modules[$i]}"
    title="${titles[$i]}"
    desc="${descriptions[$i]}"
    outfile="$API_DIR/$module.md"

    echo "  Generating $module.md..."
    module_output="$(pydoc-markdown -I py-xbbg/src -m "xbbg.$module" 2>/dev/null)"

    {
        echo "---"
        echo "title: $title"
        echo "description: $desc"
        echo "---"
        echo ""
        printf '%s\n' "$module_output" | grep -v "^\[WARNING" || true
    } > "$outfile"
done

echo "Done! Generated ${#modules[@]} Python API docs in $API_DIR"
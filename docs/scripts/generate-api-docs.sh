#!/bin/bash
# Generate API documentation from Python docstrings using pydoc-markdown

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DOCS_DIR")"
API_DIR="$DOCS_DIR/src/content/docs/api"

cd "$PROJECT_ROOT"

echo "Generating API documentation..."

# Generate docs for each module
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

    # Generate frontmatter + content
    {
        echo "---"
        echo "title: $title"
        echo "description: $desc"
        echo "---"
        echo ""
        uv run --no-project pydoc-markdown -I py-xbbg/src -m "xbbg.$module" 2>/dev/null | grep -v "^\[WARNING"
    } > "$outfile"
done

echo "Done! Generated ${#modules[@]} API docs in $API_DIR"

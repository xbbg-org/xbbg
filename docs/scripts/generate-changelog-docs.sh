#!/bin/bash
# Generate the public changelog page from the repository root CHANGELOG.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DOCS_DIR")"
CHANGELOG_SRC="$PROJECT_ROOT/CHANGELOG.md"
CHANGELOG_DOC="$DOCS_DIR/src/content/docs/releases/changelog.mdx"

if [[ ! -f "$CHANGELOG_SRC" ]]; then
    echo "Missing changelog source: $CHANGELOG_SRC" >&2
    exit 1
fi

{
    echo "---"
    echo "title: Changelog"
    echo "description: Release notes synced from the repository root CHANGELOG.md"
    echo "---"
    echo
    echo "_This page is generated from the repository root [CHANGELOG.md](https://github.com/alpha-xone/xbbg/blob/main/CHANGELOG.md) during docs builds._"
    echo
    tail -n +3 "$CHANGELOG_SRC"
} > "$CHANGELOG_DOC"

echo "Synced changelog docs from $CHANGELOG_SRC"

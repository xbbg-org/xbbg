#!/bin/bash
# Script to test xbbg 0.7.7 using uv
# This script creates a virtual environment, installs xbbg 0.7.7, and runs the test

set -e

echo "=========================================="
echo "xbbg 0.7.7 Test Script"
echo "=========================================="
echo ""

# Create a temporary virtual environment
VENV_DIR=".venv_xbbg_0.7.7"
echo "Creating virtual environment: $VENV_DIR"
uv venv "$VENV_DIR"

# Activate virtual environment (Windows vs Unix)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi

echo ""
echo "Installing xbbg==0.7.7..."
uv pip install xbbg==0.7.7

echo ""
echo "Verifying installed version..."
python -c "import importlib.metadata; print(f'xbbg version: {importlib.metadata.version(\"xbbg\")}')"

echo ""
echo "Installing pandas (required dependency)..."
uv pip install pandas

echo ""
echo "Running test script..."
# Get the script directory (where this .sh file is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "$SCRIPT_DIR/test_xbbg_0.7.7.py"

echo ""
echo "Cleaning up..."
deactivate
rm -rf "$VENV_DIR"

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="


# PowerShell script to test latest xbbg using uv
# This script creates a virtual environment, installs latest xbbg, and runs the test

Write-Output "=========================================="
Write-Output "xbbg Latest Version Test Script"
Write-Output "=========================================="
Write-Output ""

# Create a temporary virtual environment
$VENV_DIR = ".venv_xbbg_latest"
Write-Output "Creating virtual environment: $VENV_DIR"
uv venv $VENV_DIR

# Activate virtual environment
Write-Output "Activating virtual environment..."
& "$VENV_DIR\Scripts\Activate.ps1"

Write-Output ""
Write-Output "Installing latest xbbg..."
uv pip install xbbg

Write-Output ""
Write-Output "Installing dependencies..."
uv pip install pandas

Write-Output ""
Write-Output "Installing blpapi..."
uv pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

Write-Output ""
Write-Output "Verifying installed version..."
python -c "import importlib.metadata; print('xbbg version:', importlib.metadata.version('xbbg'))"

Write-Output ""
Write-Output "Running test script..."
Write-Output "[NOTE] test_xbbg_latest.py has been removed. This script is no longer functional."
Write-Output "Please use the test scripts in tests_xbbg_0.7.7 folder instead."
# python test_xbbg_latest.py  # File removed

Write-Output ""
Write-Output "Cleaning up..."
deactivate
Remove-Item -Recurse -Force $VENV_DIR

Write-Output ""
Write-Output "=========================================="
Write-Output "Test Complete"
Write-Output "=========================================="


# PowerShell script to test xbbg 0.7.7 using uv
# This script creates a virtual environment, installs xbbg 0.7.7, and runs the test

Write-Output "=========================================="
Write-Output "xbbg 0.7.7 Test Script"
Write-Output "=========================================="
Write-Output ""

# Create a temporary virtual environment
$VENV_DIR = ".venv_xbbg_0.7.7"
Write-Output "Creating virtual environment: $VENV_DIR"
uv venv $VENV_DIR

# Activate virtual environment
Write-Output "Activating virtual environment..."
& "$VENV_DIR\Scripts\Activate.ps1"

Write-Output ""
Write-Output "Installing dependencies (pandas first)..."
uv pip install pandas

Write-Output ""
Write-Output "Installing xbbg==0.7.7..."
uv pip install xbbg==0.7.7

Write-Output ""
Write-Output "Installing blpapi..."
uv pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

Write-Output ""
Write-Output "Verifying installed version..."
# Use full path and change to temp directory to avoid importing from current directory
$pythonExe = Join-Path (Resolve-Path $VENV_DIR) "Scripts\python.exe"
Push-Location $env:TEMP
try {
    & $pythonExe -c "import importlib.metadata; print('xbbg version:', importlib.metadata.version('xbbg'))"
} finally {
    Pop-Location
}

Write-Output ""
Write-Output "Running test script..."
# Set PYTHONPATH to empty to prevent importing from current directory
$env:PYTHONPATH = ""
# Get the script directory (where this .ps1 file is located)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $scriptDir "test_xbbg_0.7.7.py"
& $pythonExe $scriptPath

Write-Output ""
Write-Output "Cleaning up..."
deactivate
Remove-Item -Recurse -Force $VENV_DIR

Write-Output ""
Write-Output "=========================================="
Write-Output "Test Complete"
Write-Output "=========================================="


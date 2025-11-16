# PowerShell script to test xbbg 0.7.7 using uv
# This script creates a virtual environment, installs xbbg 0.7.7, and runs the test

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "xbbg 0.7.7 Test Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Create a temporary virtual environment
$VENV_DIR = ".venv_xbbg_0.7.7"
Write-Host "Creating virtual environment: $VENV_DIR" -ForegroundColor Yellow
uv venv $VENV_DIR

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "$VENV_DIR\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Installing dependencies (pandas first)..." -ForegroundColor Yellow
uv pip install pandas

Write-Host ""
Write-Host "Installing xbbg==0.7.7..." -ForegroundColor Yellow
uv pip install xbbg==0.7.7

Write-Host ""
Write-Host "Installing blpapi..." -ForegroundColor Yellow
uv pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

Write-Host ""
Write-Host "Verifying installed version..." -ForegroundColor Yellow
# Use full path and change to temp directory to avoid importing from current directory
$pythonExe = Join-Path (Resolve-Path $VENV_DIR) "Scripts\python.exe"
Push-Location $env:TEMP
try {
    & $pythonExe -c "import importlib.metadata; print('xbbg version:', importlib.metadata.version('xbbg'))"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Running test script..." -ForegroundColor Yellow
# Set PYTHONPATH to empty to prevent importing from current directory
$env:PYTHONPATH = ""
# Get the script directory (where this .ps1 file is located)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $scriptDir "test_xbbg_0.7.7.py"
& $pythonExe $scriptPath

Write-Host ""
Write-Host "Cleaning up..." -ForegroundColor Yellow
deactivate
Remove-Item -Recurse -Force $VENV_DIR

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan


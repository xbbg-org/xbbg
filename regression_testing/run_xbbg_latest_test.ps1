# PowerShell script to test latest xbbg using uv
# This script creates a virtual environment, installs latest xbbg, and runs the test

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "xbbg Latest Version Test Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Create a temporary virtual environment
$VENV_DIR = ".venv_xbbg_latest"
Write-Host "Creating virtual environment: $VENV_DIR" -ForegroundColor Yellow
uv venv $VENV_DIR

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "$VENV_DIR\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Installing latest xbbg..." -ForegroundColor Yellow
uv pip install xbbg

Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
uv pip install pandas

Write-Host ""
Write-Host "Installing blpapi..." -ForegroundColor Yellow
uv pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi

Write-Host ""
Write-Host "Verifying installed version..." -ForegroundColor Yellow
python -c "import importlib.metadata; print('xbbg version:', importlib.metadata.version('xbbg'))"

Write-Host ""
Write-Host "Running test script..." -ForegroundColor Yellow
Write-Host "[NOTE] test_xbbg_latest.py has been removed. This script is no longer functional." -ForegroundColor Yellow
Write-Host "Please use the test scripts in tests_xbbg_0.7.7 folder instead." -ForegroundColor Yellow
# python test_xbbg_latest.py  # File removed

Write-Host ""
Write-Host "Cleaning up..." -ForegroundColor Yellow
deactivate
Remove-Item -Recurse -Force $VENV_DIR

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan


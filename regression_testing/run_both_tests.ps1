# PowerShell script to test both xbbg 0.7.7 and latest version
# This allows easy comparison between versions

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "xbbg Version Comparison Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Testing xbbg 0.7.7..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
powershell -ExecutionPolicy Bypass -File "$scriptDir\run_xbbg_0.7.7_test.ps1"

Write-Host ""
Write-Host ""
Write-Host "Testing xbbg Latest..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
Write-Host "[SKIPPED] test_xbbg_latest.py has been removed. Only testing xbbg 0.7.7." -ForegroundColor Yellow
# powershell -ExecutionPolicy Bypass -File "$scriptDir\run_xbbg_latest_test.ps1"  # Disabled - test file removed

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Comparison Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Review the output above to compare:" -ForegroundColor Green
Write-Host "  - Index type (DatetimeIndex vs regular Index)" -ForegroundColor Green
Write-Host "  - Index value types (date strings vs datetime.date vs Timestamp)" -ForegroundColor Green
Write-Host "  - Column structure (MultiIndex vs single-level for single ticker)" -ForegroundColor Green


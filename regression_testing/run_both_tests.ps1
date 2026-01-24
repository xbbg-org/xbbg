# PowerShell script to test both xbbg 0.7.7 and latest version
# This allows easy comparison between versions

Write-Output "=========================================="
Write-Output "xbbg Version Comparison Test"
Write-Output "=========================================="
Write-Output ""

Write-Output "Testing xbbg 0.7.7..."
Write-Output "----------------------------------------"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
powershell -ExecutionPolicy Bypass -File "$scriptDir\run_xbbg_0.7.7_test.ps1"

Write-Output ""
Write-Output ""
Write-Output "Testing xbbg Latest..."
Write-Output "----------------------------------------"
Write-Output "[SKIPPED] test_xbbg_latest.py has been removed. Only testing xbbg 0.7.7."
# powershell -ExecutionPolicy Bypass -File "$scriptDir\run_xbbg_latest_test.ps1"  # Disabled - test file removed

Write-Output ""
Write-Output "=========================================="
Write-Output "Comparison Complete"
Write-Output "=========================================="
Write-Output ""
Write-Output "Review the output above to compare:"
Write-Output "  - Index type (DatetimeIndex vs regular Index)"
Write-Output "  - Index value types (date strings vs datetime.date vs Timestamp)"
Write-Output "  - Column structure (MultiIndex vs single-level for single ticker)"


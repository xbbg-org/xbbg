# xbbg-cli

Command-line interface for Bloomberg data retrieval.

## Status

🚧 **Placeholder** — pending completion of core Python implementation.

## Planned Usage

```bash
# Reference data
xbbg bdp "AAPL US Equity" --fields PX_LAST,SECURITY_NAME

# Historical data
xbbg bdh "AAPL US Equity" --fields PX_LAST --start 2024-01-01 --end 2024-12-31

# Bulk data
xbbg bds "AAPL US Equity" --fields TOP_20_HOLDERS_PUBLIC_FILINGS

# Intraday bars
xbbg bdib "AAPL US Equity" --interval 5 --start 2024-01-15

# Live streaming
xbbg subscribe "AAPL US Equity" --fields LAST_PRICE,BID,ASK

# Output formats
xbbg bdp "AAPL US Equity" --fields PX_LAST --format csv
xbbg bdp "AAPL US Equity" --fields PX_LAST --format json
```

## Output Formats

- `table` (default) — human-readable table
- `csv` — comma-separated values
- `json` — JSON objects
- `arrow` — Arrow IPC for piping to other tools

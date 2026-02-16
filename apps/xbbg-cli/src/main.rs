// xbbg-cli — Command-line interface for Bloomberg data
//
// Planned usage:
//   xbbg bdp "AAPL US Equity" --fields PX_LAST,SECURITY_NAME
//   xbbg bdh "AAPL US Equity" --fields PX_LAST --start 2024-01-01 --end 2024-12-31
//   xbbg bds "AAPL US Equity" --fields TOP_20_HOLDERS_PUBLIC_FILINGS
//   xbbg bdib "AAPL US Equity" --interval 5 --start 2024-01-15
//   xbbg subscribe "AAPL US Equity" --fields LAST_PRICE,BID,ASK
//
// Output formats: table (default), csv, json, arrow
//
// Status: placeholder — pending completion of core Python implementation.

fn main() {
    println!("xbbg-cli: not yet implemented");
}

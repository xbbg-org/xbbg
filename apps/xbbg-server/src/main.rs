// xbbg-server — HTTP/WebSocket/gRPC gateway for Bloomberg data
//
// Planned endpoints:
//   POST /api/bdp    — reference data
//   POST /api/bdh    — historical data
//   POST /api/bds    — bulk data
//   POST /api/bdib   — intraday bars
//   POST /api/bql    — BQL queries
//   POST /api/bsrch  — Bloomberg search
//   WS   /ws/subscribe — streaming market data
//
// Response formats: JSON (default), Arrow IPC, CSV
// Auth: API key or mTLS
//
// Status: placeholder — pending completion of core Python implementation.

fn main() {
    println!("xbbg-server: not yet implemented");
}

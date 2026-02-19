# xbbg-server

HTTP/WebSocket/gRPC gateway for Bloomberg data. Run one instance, connect from any language.

## Status

🚧 **Placeholder** — pending completion of core Python implementation.

## Planned Features

- **REST API** — `POST /api/bdp`, `/api/bdh`, `/api/bds`, `/api/bdib`, `/api/bql`, `/api/bsrch`
- **WebSocket** — `WS /ws/subscribe` for streaming market data
- **gRPC** — typed service definitions (future)
- **Response formats** — JSON (default), Arrow IPC, CSV
- **Auth** — API key or mTLS
- **Multi-client** — single Bloomberg connection shared across consumers

## Architecture

```
xbbg-core + xbbg-async  (pure Rust engine)
         ↓
   xbbg-server           (this binary — axum web framework)
         ↓
  Any HTTP/WS client     (browser, curl, Python, Go, Java, ...)
```

## Why

Not every consumer needs native bindings. A running `xbbg-server` instance lets
any language or tool access Bloomberg data via api — dashboards, notebooks,
microservices, Excel via Power Query, etc.

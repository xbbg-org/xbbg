# xbbg-server

Async localhost bridge for Bloomberg data backed by `xbbg-async`.

## Transport split

- **HTTP** for async request submission and polling
- **WebSocket** for subscription streams
- **WebSocket** for request lifecycle events

## Endpoints

- `GET /health`
- `POST /requests`
- `GET /requests/:id`
- `GET /requests/:id/result`
- `GET /ws/requests`
- `GET /ws/subscriptions`

## Config

Environment variables:

- `XBBG_BRIDGE_LISTEN` — bridge bind address, default `127.0.0.1:7878`
- `XBBG_HOST` — Bloomberg host, default `127.0.0.1`
- `XBBG_PORT` — Bloomberg port, default `8194`

## Run

```bash
BLPAPI_ROOT=/path/to/blpapi-sdk \
XBBG_HOST=BBG_HOST \
XBBG_PORT=8194 \
cargo run -p xbbg-server
```

## Notes

- request execution is **always async**
- each subscription websocket currently supports **one active subscription session**
- open multiple websockets if you want multiple independent subscription lanes

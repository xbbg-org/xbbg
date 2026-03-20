# @xbbg/bridge

Thin npm wrapper for running the local Rust `xbbg-server` bridge during development.

## Run

```bash
BLPAPI_ROOT=/path/to/blpapi-sdk \
XBBG_HOST=BBG_HOST \
XBBG_PORT=8194 \
node packages/xbbg-bridge/bin/xbbg-bridge.js
```

The wrapper runs:

```bash
cargo run -p xbbg-server --
```

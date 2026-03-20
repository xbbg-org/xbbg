# @xbbg/bridge

npm launcher for the prebuilt `xbbg-server` bridge binary.

## Current model

- resolves a platform-specific `@xbbg/bridge-*` package
- prepares Bloomberg SDK runtime env locally
- launches the packaged `xbbg-server` binary

## Build the current platform binary locally

```bash
cd packages/xbbg-bridge
BLPAPI_ROOT=/path/to/blpapi-sdk npm run build:binary
```

## Run

```bash
BLPAPI_ROOT=/path/to/blpapi-sdk XBBG_HOST=BBG_HOST XBBG_PORT=8194 node packages/xbbg-bridge/bin/xbbg-bridge.js
```

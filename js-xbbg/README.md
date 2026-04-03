# @xbbg/core

Bloomberg data API for Node.js — powered by Rust.

## Status

🚧 **Experimental alpha** — native N-API bindings are implemented, high-level API is in active development.

## Install

Supported prebuilt addon targets:
- macOS arm64
- Linux x64
- Windows x64

```bash
bun add @xbbg/core
# or
npm install @xbbg/core
```

`@xbbg/core` loads a packaged native `napi_xbbg.node` addon via platform-specific optional dependencies on supported targets. If no packaged addon is available for your platform, build from source locally instead.

## Local Development

```bash
# Preferred: build and copy js-xbbg/napi_xbbg.node into the package directory
npm --prefix js-xbbg run build

# Lower-level Rust build (useful while hacking on napi-xbbg itself)
cargo build -p napi-xbbg

# Stage the current platform package template with the built addon
npm --prefix js-xbbg run stage:native-package

# Run JS smoke test from js-xbbg/
npm test
```

The JS package automatically loads a local `js-xbbg/napi_xbbg.node` addon first, then falls back to packaged optional native dependencies for supported platforms.

## Planned Usage

```typescript
import * as xbbg from '@xbbg/core';

xbbg.configure('localhost', 8194);

// Python-style blp namespace
const hist = await xbbg.blp.abdh(['AAPL US Equity'], ['PX_LAST'], '2024-01-01', '2024-12-31');
const ref = await xbbg.blp.abdp(['AAPL US Equity'], ['PX_LAST', 'SECURITY_NAME']);
const bulk = await xbbg.blp.abds(['ES1 Index'], ['FUT_CHAIN_LAST_TRADE_DATES']);
const bars = await xbbg.blp.abdib('AAPL US Equity', '2024-12-01', 5);
const ticks = await xbbg.blp.abdtick('AAPL US Equity', '2024-12-01T09:30:00', '2024-12-01T10:00:00');

// Live streaming
const sub = await xbbg.blp.asubscribe(['AAPL US Equity'], ['LAST_PRICE', 'BID', 'ASK']);
for await (const tick of sub) {
  console.log(tick);
}

// CDX analytics
const cdxInfo = await xbbg.ext.cdx.acdx_info('CDX IG CDSI GEN 5Y Corp');
const cdxPricing = await xbbg.ext.cdx.acdx_pricing('CDX IG CDSI GEN 5Y Corp');
const cdxRisk = await xbbg.ext.cdx.acdx_risk('CDX IG CDSI GEN 5Y Corp');
```

## Features (planned)

- Native N-API bindings (no HTTP overhead)
- Zero-copy Arrow buffers via `apache-arrow`
- Async/await with proper backpressure
- TypeScript-first with full type definitions
- Cross-platform prebuilt addon packaging: macOS arm64, Linux x64, Windows x64

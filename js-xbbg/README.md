# @xbbg/core

Bloomberg data API for Node.js — powered by Rust.

## Status

🚧 **Experimental alpha** — native N-API bindings are implemented, high-level API is in active development.

## Local Development

```bash
# Build native addon from workspace root
cargo build -p napi-xbbg

# Run JS smoke test from js-xbbg/
npm test
```

The JS package automatically loads the built `.node` addon from common workspace paths (`target/debug` and `target/release`).

## Planned Usage

```typescript
import * as xbbg from '@xbbg/core';

xbbg.configure('localhost', 8194);

// Python-style blp namespace
const hist = await xbbg.blp.abdh(['AAPL US Equity'], ['PX_LAST'], '2024-01-01', '2024-12-31');
const ref = await xbbg.blp.abdp(['AAPL US Equity'], ['PX_LAST', 'SECURITY_NAME']);
const bulk = await xbbg.blp.abds(['ES1 Index'], ['FUT_CHAIN_LAST_TRADE_DATES']);
const bars = await xbbg.blp.abdib('AAPL US Equity', '2024-12-01', 5);
const ticks = await xbbg.blp.abdtick('AAPL US Equity', '2024-12-01 09:30', '2024-12-01 10:00');

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
- Cross-platform: Linux x64, Windows x64

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
import { connect, bdp, bdh, subscribe } from '@xbbg/core';

// Connect to Bloomberg
const session = await connect();

// Reference data
const df = await bdp(['AAPL US Equity'], ['PX_LAST', 'SECURITY_NAME']);

// Historical data
const hist = await bdh(['AAPL US Equity'], ['PX_LAST'], {
  start: '2024-01-01',
  end: '2024-12-31',
});

// Streaming
const sub = subscribe(['AAPL US Equity'], ['LAST_PRICE', 'BID', 'ASK']);
for await (const tick of sub) {
  console.log(tick);
}
```

## Features (planned)

- Native N-API bindings (no HTTP overhead)
- Zero-copy Arrow buffers via `apache-arrow`
- Async/await with proper backpressure
- TypeScript-first with full type definitions
- Cross-platform: Linux x64, Windows x64

# napi-xbbg

Node.js bindings for the xbbg Bloomberg engine via [napi-rs](https://napi.rs).

## Status

🚧 **Placeholder** — pending completion of core Python implementation.

## Planned Features

- Async `bdp`/`bdh`/`bds`/`bdib` returning Arrow buffers
- Streaming market data via `EventEmitter` or `ReadableStream`
- Zero-copy Arrow interop with `apache-arrow` npm package
- Auto-generated TypeScript definitions
- Cross-platform npm packages (Linux x64, Windows x64)

## Architecture

```
xbbg-core + xbbg-async  (pure Rust engine)
         ↓
    napi-xbbg            (this crate — thin N-API wrapper)
         ↓
     js-xbbg             (npm package + TS types)
```

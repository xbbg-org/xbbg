# xbbg-sys

Unified FFI abstraction layer over `blpapi-sys` (real Bloomberg SDK) and `datamock` (mock backend).

Downstream crates (`xbbg-core`) depend on `xbbg-sys` and get the same `blpapi_*` symbols regardless of which backend is active.

## Features

| Feature | Backend | Status |
|---------|---------|--------|
| `live` (default) | `blpapi-sys` — real Bloomberg C++ SDK | ✅ Production |
| `mock` | `datamock` — lightweight test double | 🚧 Not yet production-ready |

Features are mutually exclusive. Enabling both is a compile error.

> **Note**: The `mock` feature is currently disabled with `compile_error!`. The datamock backend has known ABI mismatches and incomplete stubs. Use `live` only.

## Crate structure

```
xbbg-sys/
├── Cargo.toml      Features (mock/live), optional deps on datamock + blpapi-sys
├── build.rs        Bindgen for datamock header (mock mode only)
└── src/
    ├── lib.rs      Feature gates, backend selection, re-exports
    ├── shim.rs     Signature adapters: datamock API → Bloomberg API (mock only)
    └── stubs.rs    No-op stubs for APIs datamock doesn't implement (mock only)
```

## How it works

### Live mode (default)

Thin re-export — `xbbg_sys::*` is just `blpapi_sys::*`:

```
xbbg-sys (live) ──re-export──▶ blpapi-sys ──FFI──▶ Bloomberg C++ SDK
```

### Mock mode (disabled)

Three-layer symbol resolution with precedence:

```
xbbg-sys (mock)
  ├── shim.rs      Signature adapters (highest priority)
  ├── stubs.rs     No-op stubs for missing APIs
  └── bindings.rs  Bindgen output from datamock header (lowest priority)
        │
        ▼
  datamock C++ library (static link)
```

The `build.rs` uses bindgen with a `RenameCallback` to transform `datamock_*` symbols to `blpapi_*` names. Functions with signature mismatches between datamock and Bloomberg are blocklisted from bindgen and provided by `shim.rs` instead.

## Consumers

Only `xbbg-core` depends on this crate directly. All other crates in the workspace consume Bloomberg FFI through `xbbg-core`'s safe Rust abstractions.

## Safety

All APIs are `unsafe` C FFI. Safe wrappers are in `xbbg-core`.

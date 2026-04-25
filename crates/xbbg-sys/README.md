# xbbg-sys

FFI abstraction layer over `blpapi-sys`, the Bloomberg SDK C bindings used by `xbbg-core`.

Downstream crates depend on `xbbg-sys` instead of directly on `blpapi-sys` so the workspace has one FFI import boundary.

## Features

| Feature | Backend | Status |
|---------|---------|--------|
| `live` (default) | `blpapi-sys` — real Bloomberg C++ SDK | Production |

## Crate structure

```text
xbbg-sys/
├── Cargo.toml      Live feature and optional dependency on blpapi-sys
├── build.rs        No-op build script; blpapi-sys owns binding generation
└── src/
    └── lib.rs      Feature gate and re-export of blpapi-sys
```

## How it works

Thin re-export — `xbbg_sys::*` is `blpapi_sys::*`:

```text
xbbg-sys ──re-export──▶ blpapi-sys ──FFI──▶ Bloomberg C++ SDK
```

## Consumers

Only `xbbg-core` depends on this crate directly. All other crates in the workspace consume Bloomberg FFI through `xbbg-core`'s safe Rust abstractions.

## Safety

All APIs are `unsafe` C FFI. Safe wrappers are in `xbbg-core`.

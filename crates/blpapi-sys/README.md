# blpapi-sys

Unsafe, zero-policy FFI bindings to Bloomberg's C API (`blpapi_*`), generated at build time.

- `#![no_std]` — no runtime dependencies beyond the Bloomberg SDK
- Bindings auto-generated via bindgen from SDK headers; nothing checked in
- Exposes raw types, constants, and functions only — no wrappers, no ownership logic

## Crate structure

```
blpapi-sys/
├── Cargo.toml      Features (static/dynamic), bindgen + cty deps
├── build.rs        SDK discovery, bindgen generation, link directives
└── src/
    └── lib.rs      include!(bindings.rs) — 9 lines
```

## Linking

- Default: dynamic linking
- `--features static`: static linking
- Link name defaults:
  - Windows x64: `blpapi3_64`
  - Windows x86: `blpapi3_32`
  - Linux/macOS: `blpapi3`
- Override with `BLPAPI_LINK_LIB_NAME` env var

## SDK discovery (precedence)

| Priority | Environment variable(s) | Notes |
|----------|------------------------|-------|
| 1 | `BLPAPI_INCLUDE_DIR` + `BLPAPI_LIB_DIR` | Explicit paths (CI/prod) |
| 2 | `BLPAPI_ROOT` | Derives `include/` and `lib/` from root |
| 3 | `XBBG_DEV_SDK_ROOT` | Dev-only, same derivation as above |

The build script tries these layouts under a root directory:
- `<root>/include` + `<root>/lib`
- `<root>/include` + `<root>/lib/win64` (or `win32`)
- `<root>/Include` + `<root>/Lib`

Build requires SDK **headers** and the **import library**. The runtime DLL/so/dylib is not required at build time.

## Dev / CI usage

**Dev**: set `XBBG_DEV_SDK_ROOT` to the SDK root, then build the workspace.

**CI build**: set `BLPAPI_ROOT` or `BLPAPI_INCLUDE_DIR`/`BLPAPI_LIB_DIR`.

**CI runtime/tests**: install the official `blpapi` Python package and add its binary directory to the loader path:

```bash
uv pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi
```

- Windows (Py≥3.8): `os.add_dll_directory(<package_dir>)`
- Linux/macOS: add the package directory to `LD_LIBRARY_PATH`/`DYLD_LIBRARY_PATH`

## Safety

All APIs are `unsafe` and follow the C ABI. Nothing is marked `Send`/`Sync` unless guaranteed by the C SDK.

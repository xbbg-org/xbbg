# blpapi-sys

Unsafe, zero-policy FFI bindings to Bloomberg's C API (blpapi_*), generated at build time.

- Exposes raw types, constants, and functions only
- No allocation, no wrappers, no ownership logic
- Bindings generated locally via bindgen; no Bloomberg headers or generated bindings are checked in

## Linking

- Default dynamic linking; `--features static` opts in to static
- Link name defaults:
  - Windows: `blpapi3_64`
  - Unix/macOS: `blpapi3`
- Override with `BLPAPI_LINK_LIB_NAME`

## SDK discovery (precedence)

1. `BLPAPI_INCLUDE_DIR` and `BLPAPI_LIB_DIR`
2. `BLPAPI_ROOT` (derive `include/` and `lib/`)
3. `XBBG_DEV_SDK_ROOT` (dev-only, derive `include/` and `lib/`)

Build requires SDK headers and the import library. The runtime DLL/so/dylib is not required at build time.

## Dev / CI usage

- Dev: set `XBBG_DEV_SDK_ROOT` to the SDK root; then build the workspace.
- CI build: set `BLPAPI_ROOT` or `BLPAPI_INCLUDE_DIR`/`BLPAPI_LIB_DIR` (these can be loaded via your `.env` loader before invoking Cargo).
- CI runtime/tests: install the official `blpapi` Python package and add its binary directory to the loader path before importing your extension.
  - `uv pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi`
  - Or: `pip install --index-url https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi`
  - Windows (Py>=3.8): `os.add_dll_directory(<package_dir>)`
  - Linux/macOS: add the package directory to `LD_LIBRARY_PATH`/`DYLD_LIBRARY_PATH`

## Safety

All APIs are unsafe and follow the C ABI. Nothing is marked Send/Sync unless guaranteed by the C API.



# xbbg-sys Integration Plan

## Context

### Original Request
Create a unified xbbg-sys crate that abstracts over blpapi-sys (real Bloomberg) and datamock-sys (mock) to enable testing without a Bloomberg Terminal while keeping the real SDK for production builds.

### Interview Summary
- Default backend: mock (datamock) for CI/tests
- live feature enables real Bloomberg backend for local testing  
- Final package uses live only - no datamock in release

### Momus Review Issues Addressed
1. CorrelationId helpers exist but struct layout incompatible - MUST fix layout
2. Pointer correlation IDs not supported in datamock - MUST add support
3. Feature propagation chain missing - MUST define pyo3-xbbg -> xbbg-async -> xbbg-core -> xbbg-sys
4. Stub surface area underspecified - MUST list concrete stubs

---

## Work Objectives

### Definition of Done
- [ ] cargo build -p xbbg-sys succeeds with default features (mock)
- [ ] cargo build -p xbbg-sys --no-default-features --features live succeeds  
- [ ] cargo build -p xbbg-core succeeds with default features (mock)
- [ ] cargo test -p datamock passes
- [ ] Pointer correlation IDs work in mock mode

### Must Have
- Binary-compatible CorrelationId layout (bitfields + ManagedPtr union)
- Pointer correlation ID support in datamock C API
- blpapiext_cid_* helpers in xbbg-sys (aliased from datamockext_cid_*)
- Feature propagation: pyo3-xbbg -> xbbg-async -> xbbg-core -> xbbg-sys
- Concrete stub list for missing APIs
- Mutual exclusivity enforcement

### Must NOT Have  
- NO modifications to blpapi-sys crate
- NO modifications to datamock-sys crate
- NO runtime backend switching
- NO new Bloomberg references in datamock comments

---

## Feature Propagation Matrix

pyo3-xbbg:
  features: mock (default), live
  propagates to: xbbg-async/mock, xbbg-async/live

xbbg-async:
  features: mock (default), live
  propagates to: xbbg-core/mock, xbbg-core/live

xbbg-core:
  features: mock (default), live
  propagates to: xbbg-sys/mock, xbbg-sys/live

xbbg-sys:
  features: mock (default), live
  mock -> datamock-sys
  live -> blpapi-sys

---

## Stub List (Mock Mode)

APIs missing from datamock that xbbg-core uses:

Schema/Introspection (stub with error returns):
- blpapi_SchemaElementDefinition_* -> return NULL/error
- blpapi_SchemaTypeDefinition_* -> return NULL/error  
- blpapi_Operation_* -> return NULL/error

Logging (stub as no-op):
- blpapi_Logging_* -> no-op

Identity/Auth (stub with success):
- blpapi_Session_createIdentity -> return dummy handle
- blpapi_Session_generateAuthorizedIdentity -> return success

Request Templates (stub with error):
- blpapi_Session_createSnapshotRequestTemplate -> return NULL

Advanced SessionOptions (stub as no-op setters):
- blpapi_SessionOptions_set* for advanced options -> no-op

---

## TODOs

- [x] 1. Fix datamock_CorrelationId_t layout AND pointer ID support

  What to do:
  - Update datamock_CorrelationId_t to use bitfields (8+4+16+4 bits)
  - Add datamock_ManagedPtr_t struct for union compatibility
  - Fix pointer correlation ID handling in datamock C API
  - Add datamockext_cid_* helpers matching blpapiext_cid_* signatures

  References:
  - crates/datamock/cpp/include/datamock/datamock_c_api.h:95-104 (current layout)
  - crates/datamock/cpp/src/datamock_c_api.cpp:224-227,865-867 (INT-only to fix)
  - vendor/blpapi/blpapi_cpp/include/blpapi_correlationid.h:90-100 (target)
  - crates/blpapi-sys/src/xb_ext.c (helper signatures)

  Acceptance Criteria:
  - [ ] datamock_CorrelationId_t uses bitfields
  - [ ] datamock_ManagedPtr_t defined
  - [ ] datamockext_cid_from_ptr and get_ptr implemented
  - [ ] Pointer CIDs work through send/receive cycle
  - [ ] cargo build -p datamock succeeds

  Commit: NO (groups with task 2)

---

- [x] 2. Rebuild datamock and verify pointer CID tests

  What to do:
  - Rebuild datamock to regenerate bindings
  - Add test for pointer correlation ID round-trip
  - Verify all existing tests pass

  Acceptance Criteria:
  - [ ] cargo build -p datamock succeeds
  - [ ] cargo test -p datamock passes

  Commit: fix(datamock): fix CorrelationId layout and add pointer ID support

---

- [ ] 3. Create xbbg-sys crate with bindgen callbacks and stubs

  What to do:
  - Create crates/xbbg-sys directory
  - Create Cargo.toml with features mock (default) and live
  - Create build.rs with bindgen ParseCallbacks to rename datamock to blpapi
  - Create src/lib.rs with conditional includes
  - Create src/stubs.rs with mock-mode stub implementations
  - Re-export blpapiext_cid_* as aliases to datamockext_cid_*

  Acceptance Criteria:
  - [ ] xbbg-sys crate created
  - [ ] Bindgen renames work
  - [ ] Stubs defined
  - [ ] cargo build -p xbbg-sys succeeds (mock and live)
  - [ ] cargo build -p xbbg-sys --features mock,live fails

  Commit: feat(xbbg-sys): add unified FFI crate with stubs

---

- [ ] 4. Update xbbg-core to use xbbg-sys

  What to do:
  - Update Cargo.toml with features mock/live
  - Update all 20 files: blpapi_sys -> xbbg_sys

  Acceptance Criteria:
  - [ ] cargo build -p xbbg-core succeeds (mock and live)

  Commit: NO (groups with task 7)

---

- [ ] 5. Update xbbg-async with feature propagation

  Acceptance Criteria:
  - [ ] cargo build -p xbbg-async succeeds

  Commit: NO (groups with task 7)

---

- [ ] 6. Update pyo3-xbbg with feature propagation  

  Acceptance Criteria:
  - [ ] cargo build -p pyo3-xbbg succeeds

  Commit: NO (groups with task 7)

---

- [ ] 7. Update workspace Cargo.toml

  Acceptance Criteria:
  - [ ] cargo build --workspace succeeds

  Commit: refactor: use xbbg-sys unified backend across workspace

---

- [ ] 8. Final verification

  Acceptance Criteria:
  - [ ] cargo build --workspace succeeds
  - [ ] cargo test -p datamock passes
  - [ ] Both backends build
  - [ ] Feature mutual exclusivity works
  - [ ] No blpapi_sys references remain

---

## Success Criteria

Verification Commands:
cargo build --workspace
cargo test -p datamock
cargo build -p xbbg-sys
cargo build -p xbbg-sys --no-default-features --features live
cargo build -p xbbg-sys --features mock,live  # Should fail

Final Checklist:
- [ ] CorrelationId layout fixed
- [ ] Pointer CIDs work in mock mode
- [ ] Feature propagation complete
- [ ] All stubs implemented
- [ ] Both backends build

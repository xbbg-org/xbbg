# Learnings - xbbg-sys Integration

## [2026-01-10] Tasks 1-2: CorrelationId Layout Fix and Pointer Support

### Key Discoveries

1. **Bitfield Struct Layout in Rust FFI**
   - C bitfields cannot be directly initialized from Rust
   - Bindgen generates `_bitfield_align_1` and `_bitfield_1` fields
   - Solution: Use `std::mem::zeroed()` + helper functions instead of struct literals
   - Pattern: `let mut cid = std::mem::zeroed::<datamock_CorrelationId_t>(); datamock_CorrelationId_setInt(&mut cid, value);`

2. **ManagedPtr_t Structure**
   - Bloomberg's ptrValue is NOT just `void*` - it's a struct with:
     - `void* pointer` - the actual pointer
     - `void* userData[4]` - 32 bytes of user data on 64-bit
     - `void (*manager)(void*, void*)` - cleanup function pointer
   - This is for reference counting and custom cleanup
   - datamock doesn't need full functionality but MUST match layout for ABI compatibility

3. **Pointer CID Sites Fixed**
   - Three functions only checked INT correlation IDs:
     - `datamock_Session_openServiceAsync` (line ~224)
     - `datamock_Session_sendRequest` (line ~258)
     - `datamock_SubscriptionList_add` (line ~865)
   - Pattern: Added `else if (correlationId->valueType == DATAMOCK_CORRELATION_TYPE_POINTER)` branches
   - Each creates BEmu `CorrelationId(pointer)` constructor

4. **Message Correlation ID Extraction**
   - **CRITICAL BUG FOUND**: `datamock_Message_correlationId` hardcoded INT type
   - BEmu's `CorrelationId` class has `valueType()` method returning enum
   - Fixed to check type and call appropriate accessor (`asInteger()` or `asPointer()`)
   - This was blocking pointer CID round-trip

### Successful Patterns

- **Helper Functions**: `datamockext_cid_from_ptr` and `datamockext_cid_get_ptr` match blpapiext signatures
- **Test Pattern**: Pointer round-trip test verifies:
  1. Create pointer CID with unique address
  2. Send request with pointer CID
  3. Receive response and extract CID
  4. Verify type is POINTER
  5. Verify pointer value matches original

### Build Commands
```bash
cargo build -p datamock  # Rebuilds C++ and regenerates bindings
cargo test -p datamock   # Runs all 9 tests (8 original + 1 new pointer test)
```

### Files Modified
- `crates/datamock/cpp/include/datamock/datamock_c_api.h` - Struct layout + helper declarations
- `crates/datamock/cpp/src/datamock_c_api.cpp` - Helper implementations + 3 INT-only sites + Message extraction
- `crates/datamock/src/lib.rs` - Fixed 6 test cases to use zeroed() + added pointer round-trip test

### Test Results
- All 9 tests pass
- Pointer CID successfully round-trips through send/receive cycle
- Build time: ~47 seconds (C++ compilation)

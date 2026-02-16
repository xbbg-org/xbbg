// napi-xbbg — Node.js bindings for xbbg Bloomberg engine
//
// This crate will expose xbbg-core and xbbg-async to Node.js via napi-rs.
// Planned features:
//   - bdp/bdh/bds/bdib as async JS functions returning Arrow buffers
//   - Streaming subscriptions via EventEmitter or ReadableStream
//   - Zero-copy Arrow interop with apache-arrow npm package
//   - TypeScript type definitions auto-generated from Rust types
//
// Status: placeholder — pending completion of core Python implementation.

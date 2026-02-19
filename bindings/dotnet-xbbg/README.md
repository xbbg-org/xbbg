# dotnet-xbbg

C#/.NET bindings for the xbbg Bloomberg engine via [csbindgen](https://github.com/Cysharp/csbindgen).

## Status

🚧 **Placeholder** — pending completion of core Python implementation.

## Planned Features

- C-ABI exports for all Bloomberg API functions
- NuGet package with idiomatic C# wrappers
- Async `Task` support for all data retrieval functions
- Apache Arrow IPC for zero-copy data transfer
- Excel add-in compatibility

## Architecture

```
xbbg-core + xbbg-async  (pure Rust engine)
         ↓
   dotnet-xbbg           (this crate — C-ABI exports)
         ↓
  XbbgSharp.dll          (NuGet package + C# wrappers)
```

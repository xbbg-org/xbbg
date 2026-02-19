# datamock

A mock market data API for testing xbbg without requiring a Bloomberg Terminal connection.

## Purpose

This crate provides a mock implementation of market data services for testing purposes only. It allows xbbg tests to run in CI/CD environments and on developer machines without Bloomberg connectivity.

## Supported Features

- **Reference Data** - `ReferenceDataRequest`
- **Historical Data** - `HistoricalDataRequest`
- **Intraday Bars** - `IntradayBarRequest`
- **Intraday Ticks** - `IntradayTickRequest`
- **Subscriptions** - Real-time market data simulation via `EventHandler`

## Building

```bash
cargo build -p datamock
```

## Requirements

- Rust 1.70+
- C++17 compatible compiler

## Disclaimer

This library is for **testing purposes only**. It is not affiliated with, endorsed by, or connected to Bloomberg L.P. in any way.

"Bloomberg" is a trademark of Bloomberg Finance L.P. This project does not use any Bloomberg proprietary code or SDK components. The mock API is an independent implementation that mimics the general structure of market data APIs for testing convenience.

## Third-Party Code

This crate includes code derived from [BEmu](https://bemu.codeplex.com/) by Jordan Robinson, licensed under the Microsoft Public License (Ms-PL). See [license.md](license.md) for the full license text.

### Original BEmu Copyright Notice

```
Copyright (c) 2013 Jordan Robinson. All rights reserved.

The use of this software is governed by the Microsoft Public License
which is included with this distribution.
```

## API Compatibility with Bloomberg BLPAPI

The datamock C API is designed to be compatible with the real Bloomberg BLPAPI C interface. Most functions have matching signatures and behavior.

### C API Compatibility

The following C API functions are fully compatible:

- **Session**: `create`, `destroy`, `start`, `stop`, `openService`, `getService`, `sendRequest`, `nextEvent`
- **Element**: `isNull`, `isArray`, `numValues`, `numElements`, `hasElement`, `getElement`, `getValueAs*`, `toJson`
- **Message**: `elements`, `correlationId`, `numCorrelationIds`, `typeString`
- **Datetime**: struct uses `milliSeconds` (capital S) matching BLPAPI

### JSON Serialization

The `datamock_Element_toJson()` function is fully implemented and compatible with `blpapi_Element_toJson()`. This enables xbbg's JSON-based response parsing to work with datamock:

```c
// Callback to collect JSON output
int json_writer(const char* data, int length, void* stream) {
    // Append data to your buffer
    return 0;
}

// Serialize element to JSON
datamock_Element_toJson(element, json_writer, &buffer);
```

The JSON serialization supports all BLPAPI data types including nested sequences and complex types.

### C++ API Differences (BEmu internals)

The underlying BEmu C++ library has some differences from the real BLPAPI C++ API. These are abstracted away by the C API, but if you're working with the C++ code directly:

| Feature | Real BLPAPI C++ | BEmu C++ (datamock) |
|---------|-----------------|---------------------|
| `Datetime::milliSeconds()` | Capital 'S' | `milliseconds()` lowercase |
| `Request::asElement()` | Returns Element | ✅ Fully implemented |
| Multiple correlation IDs | `correlationId(index)` | Single `correlationId()` |

### Request.asElement() Support

The `Request::asElement()` method is fully implemented for all request types:

- `HistoricalDataRequest`
- `ReferenceDataRequest`
- `IntradayBarRequest`
- `IntradayTickRequest`

The C API function `datamock_Request_getElement()` returns an Element view of the request, enabling introspection and JSON serialization of request parameters:

```c
datamock_Element* element = NULL;
int result = datamock_Request_getElement(request, &element);
if (result == DATAMOCK_OK) {
    // Serialize request to JSON
    datamock_Element_toJson(element, json_writer, &buffer);
}
```

### SessionOptions API

| Feature | Real BLPAPI | datamock |
|---------|-------------|----------|
| Auth options | Full authentication support | Stub only (no-op) |
| TLS config | Full TLS support | Not implemented |

### Subscription API

| Feature | Real BLPAPI | datamock |
|---------|-------------|----------|
| Real-time data | Actual market data | Simulated/random data |
| Throttling | Server-side limits | None |

### Known Limitations

1. **No authentication** - Sessions always "connect" successfully
2. **Simulated data only** - Market data is randomly generated, not real
3. **Simplified threading** - Event dispatch is single-threaded
4. **No partial responses** - Large requests won't be chunked
5. **Limited error simulation** - Most error paths not implemented

## License

Microsoft Public License (Ms-PL) - see [license.md](license.md)

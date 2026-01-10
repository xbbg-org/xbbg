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

## API Differences from Bloomberg BLPAPI

datamock (BEmu) provides a simplified mock of the Bloomberg API. When writing code that targets both real BLPAPI and datamock, be aware of these differences:

### Message API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Correlation IDs per message | Multiple (`numCorrelationIds()`, `correlationId(index)`) | Single (`correlationId()` takes no arguments) |
| Topic name return type | `std::string` | `const char*` |

```cpp
// Real BLPAPI
for (size_t i = 0; i < msg.numCorrelationIds(); ++i) {
    CorrelationId cid = msg.correlationId(i);
}

// datamock - only one correlation ID
CorrelationId cid = msg.correlationId();
```

### Request API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Convert to Element | `request.asElement()` | Not available - use `append()`/`set()` directly |

```cpp
// Real BLPAPI
Element securities = request.asElement().getElement("securities");

// datamock - work with Request directly
request.append("securities", "AAPL US Equity");
```

### Service API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Service name return type | `std::string` | `const char*` |

### Datetime API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Milliseconds accessor | `milliSeconds()` | `milliseconds()` (lowercase 's') |

```cpp
// Real BLPAPI
int ms = datetime.milliSeconds();

// datamock
int ms = datetime.milliseconds();
```

### Element API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Null check | `element.isNull()` | `element.IsNull()` (capital 'I') |
| Array check | `element.isArray()` | `element.IsArray()` (capital 'I') |

### SessionOptions API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Auth options | Full authentication support | Stub only (`setAuthenticationOptions` exists but is no-op) |
| TLS config | Full TLS support | Not implemented |

### Subscription API

| Feature | Real BLPAPI | datamock (BEmu) |
|---------|-------------|-----------------|
| Real-time data | Actual market data | Simulated/random data |
| Throttling | Server-side limits | None |

### Writing Compatible Code

For code that must work with both real BLPAPI and datamock, use feature flags or abstraction layers:

```rust
#[cfg(feature = "mock")]
use datamock_sys as blp;

#[cfg(not(feature = "mock"))]
use blpapi_sys as blp;
```

### Known Limitations

1. **No authentication** - Sessions always "connect" successfully
2. **Simulated data only** - Market data is randomly generated, not real
3. **Simplified threading** - Event dispatch is single-threaded
4. **No partial responses** - Large requests won't be chunked
5. **Limited error simulation** - Most error paths not implemented

## License

Microsoft Public License (Ms-PL) - see [license.md](license.md)

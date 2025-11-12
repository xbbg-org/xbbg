# Core Concepts

- Borrowed vs owned lifetimes: `Event` owns message buffers; use `MessageRef` during iteration and upgrade to `MessageOwned` to send across threads or outlive the `Event`.
- CorrelationId: use `CorrelationId::U64` or `CorrelationId::Tag`, the latter keeps backing memory in the library while in-flight.
- Event types match the BLPAPI C++ enums and drive control-flow (REQUEST_STATUS, PARTIAL_RESPONSE, RESPONSE, SUBSCRIPTION_STATUS, SUBSCRIPTION_DATA, etc.).



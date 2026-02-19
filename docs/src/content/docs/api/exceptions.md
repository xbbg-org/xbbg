---
title: Exceptions
description: Bloomberg API exception hierarchy and error handling
---

<a id="xbbg.exceptions"></a>

# xbbg.exceptions

Bloomberg API exception hierarchy.

All xbbg exceptions inherit from BlpError, allowing users to catch all
Bloomberg-related errors with a single except clause.

**Example**:

  try:
  df = await xbbg.abdp(['INVALID'], ['PX_LAST'])
  except BlpRequestError as e:
  print(f"Request failed: {e}")
  except BlpError as e:
  print(f"Bloomberg error: {e}")

<a id="xbbg.exceptions.BlpError"></a>

## BlpError Objects

```python
class BlpError(Exception)
```

Base exception for all Bloomberg API errors.

<a id="xbbg.exceptions.BlpSessionError"></a>

## BlpSessionError Objects

```python
class BlpSessionError(BlpError)
```

Session lifecycle errors (start, connect, service open).

<a id="xbbg.exceptions.BlpRequestError"></a>

## BlpRequestError Objects

```python
class BlpRequestError(BlpError)
```

Request-level errors from the Bloomberg API.

**Attributes**:

- `service` - The Bloomberg service URI (e.g., "//blp/refdata").
- `operation` - The request operation name (e.g., "ReferenceDataRequest").
- `request_id` - Optional correlation ID for debugging.
- `code` - Optional Bloomberg error code.

<a id="xbbg.exceptions.BlpSecurityError"></a>

## BlpSecurityError Objects

```python
class BlpSecurityError(BlpRequestError)
```

Invalid or inaccessible security identifier.

<a id="xbbg.exceptions.BlpFieldError"></a>

## BlpFieldError Objects

```python
class BlpFieldError(BlpRequestError)
```

Invalid or inaccessible field.

<a id="xbbg.exceptions.BlpValidationError"></a>

## BlpValidationError Objects

```python
class BlpValidationError(BlpError)
```

Request validation errors.

Raised when request parameters fail validation against Bloomberg schemas.
Includes helpful suggestions for typos and invalid enum values.

**Attributes**:

- `message` - Human-readable error description.
- `element` - The element name that caused the error (if available).
- `suggestion` - Suggested correction for typos (if available).
- `valid_values` - List of valid values for enum fields (if available).
  

**Example**:

  try:
  df = xbbg.bdp('AAPL US Equity', 'PX_LAST', periodictySelection='DAILY')
  except BlpValidationError as e:
  if e.suggestion:
  print(f"Did you mean '{e.suggestion}'?")

<a id="xbbg.exceptions.BlpValidationError.from_rust_error"></a>

#### from\_rust\_error

```python
@classmethod
def from_rust_error(cls, message: str) -> BlpValidationError
```

Parse a Rust validation error message.

Extracts element name and suggestion from formatted error messages.

<a id="xbbg.exceptions.BlpTimeoutError"></a>

## BlpTimeoutError Objects

```python
class BlpTimeoutError(BlpError)
```

Request timeout.

<a id="xbbg.exceptions.BlpInternalError"></a>

## BlpInternalError Objects

```python
class BlpInternalError(BlpError)
```

Internal errors (should not happen in normal operation).

If you encounter this error, please report it as a bug.


---
title: Schema Introspection
description: Bloomberg schema introspection and stub generation
---

<a id="xbbg.schema"></a>

# xbbg.schema

Bloomberg schema introspection and stub generation.

This module provides access to cached Bloomberg service schemas
and can generate Python type stubs for IDE autocomplete support.

**Example**:

  >>> import xbbg
  >>> from xbbg.schema import get_schema, list_operations
  >>>
  >>> # Get schema for a service
  >>> schema = await get_schema("//blp/refdata")
  >>>
  >>> # List available operations
  >>> ops = await list_operations("//blp/refdata")
  >>> print(ops)  # ['ReferenceDataRequest', 'HistoricalDataRequest', ...]
  >>>
  >>> # Get enum values for an element
  >>> values = await get_enum_values("//blp/refdata", "ReferenceDataRequest", "periodicitySelection")

<a id="xbbg.schema.ElementInfo"></a>

## ElementInfo Objects

```python
@dataclass
class ElementInfo()
```

Schema element information.

<a id="xbbg.schema.ElementInfo.from_dict"></a>

#### from\_dict

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> ElementInfo
```

Create from dictionary (parsed JSON).

<a id="xbbg.schema.OperationSchema"></a>

## OperationSchema Objects

```python
@dataclass
class OperationSchema()
```

Schema for a service operation.

<a id="xbbg.schema.OperationSchema.from_dict"></a>

#### from\_dict

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> OperationSchema
```

Create from dictionary (parsed JSON).

<a id="xbbg.schema.ServiceSchema"></a>

## ServiceSchema Objects

```python
@dataclass
class ServiceSchema()
```

Schema for a Bloomberg service.

<a id="xbbg.schema.ServiceSchema.from_dict"></a>

#### from\_dict

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> ServiceSchema
```

Create from dictionary (parsed JSON).

<a id="xbbg.schema.ServiceSchema.from_json"></a>

#### from\_json

```python
@classmethod
def from_json(cls, json_str: str) -> ServiceSchema
```

Create from JSON string.

<a id="xbbg.schema.ServiceSchema.get_operation"></a>

#### get\_operation

```python
def get_operation(name: str) -> OperationSchema | None
```

Get an operation by name.

<a id="xbbg.schema.aget_schema"></a>

#### aget\_schema

```python
async def aget_schema(service: str) -> ServiceSchema
```

Get schema for a service (async).

Loads from cache if available, otherwise introspects the service.

**Arguments**:

- `service` - Service URI (e.g., "//blp/refdata")
  

**Returns**:

  ServiceSchema object with operations and element definitions.

<a id="xbbg.schema.aget_operation"></a>

#### aget\_operation

```python
async def aget_operation(service: str, operation: str) -> OperationSchema
```

Get schema for a specific operation (async).

**Arguments**:

- `service` - Service URI (e.g., "//blp/refdata")
- `operation` - Operation name (e.g., "ReferenceDataRequest")
  

**Returns**:

  OperationSchema object with request/response definitions.

<a id="xbbg.schema.alist_operations"></a>

#### alist\_operations

```python
async def alist_operations(service: str) -> list[str]
```

List all operations for a service (async).

**Arguments**:

- `service` - Service URI (e.g., "//blp/refdata")
  

**Returns**:

  List of operation names.

<a id="xbbg.schema.aget_enum_values"></a>

#### aget\_enum\_values

```python
async def aget_enum_values(service: str, operation: str,
                           element: str) -> list[str] | None
```

Get valid enum values for an element (async).

**Arguments**:

- `service` - Service URI
- `operation` - Operation name
- `element` - Element name
  

**Returns**:

  List of valid enum values, or None if not an enum.

<a id="xbbg.schema.alist_valid_elements"></a>

#### alist\_valid\_elements

```python
async def alist_valid_elements(service: str,
                               operation: str) -> list[str] | None
```

List all valid element names for an operation (async).

**Arguments**:

- `service` - Service URI
- `operation` - Operation name
  

**Returns**:

  List of valid element names.

<a id="xbbg.schema.get_schema"></a>

#### get\_schema

```python
def get_schema(service: str) -> ServiceSchema
```

Get schema for a service (sync wrapper).

<a id="xbbg.schema.get_operation"></a>

#### get\_operation

```python
def get_operation(service: str, operation: str) -> OperationSchema
```

Get schema for a specific operation (sync wrapper).

<a id="xbbg.schema.list_operations"></a>

#### list\_operations

```python
def list_operations(service: str) -> list[str]
```

List all operations for a service (sync wrapper).

<a id="xbbg.schema.get_enum_values"></a>

#### get\_enum\_values

```python
def get_enum_values(service: str, operation: str,
                    element: str) -> list[str] | None
```

Get valid enum values for an element (sync wrapper).

<a id="xbbg.schema.list_valid_elements"></a>

#### list\_valid\_elements

```python
def list_valid_elements(service: str, operation: str) -> list[str] | None
```

List all valid element names for an operation (sync wrapper).

<a id="xbbg.schema.list_cached_schemas"></a>

#### list\_cached\_schemas

```python
def list_cached_schemas() -> list[str]
```

List all cached service URIs.

<a id="xbbg.schema.invalidate_schema"></a>

#### invalidate\_schema

```python
def invalidate_schema(service: str) -> None
```

Invalidate a cached schema.

<a id="xbbg.schema.clear_schema_cache"></a>

#### clear\_schema\_cache

```python
def clear_schema_cache() -> None
```

Clear all cached schemas.

<a id="xbbg.schema.generate_stubs"></a>

#### generate\_stubs

```python
def generate_stubs(service: str, output_dir: Path | str | None = None) -> str
```

Generate Python type stubs for a service.

Creates .pyi files with TypedDict definitions for request/response types.
Stubs are generated locally for IDE support - never committed to repos.

**Arguments**:

- `service` - Service URI (e.g., "//blp/refdata")
- `output_dir` - Output directory (default: ~/.xbbg/stubs/)
  

**Returns**:

  Path to the generated stub file.


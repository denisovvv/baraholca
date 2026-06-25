# Python Typing Guide

## Purpose

Typing in Python is not just a formal requirement for static analysis.  
It is a way to make code:

- easier to read;
- easier to change safely;
- easier to review;
- harder to misuse;
- less dependent on implicit assumptions.

The main rule is simple:

**every function, DTO, and query contract must clearly describe what data it accepts and what it returns.**

---

## Core Principles

1. Every function argument must be explicitly typed.
2. Every function return value must be explicitly typed.
3. Function signatures must use vivid and concrete types.
4. If a function has more than 5 arguments, those arguments must be wrapped into a DTO.
5. All complex entities must be represented as DTOs.
6. DTOs must be declared with `@dataclass(slots=True)` by default.
7. ORM query filters must be typed through dedicated filter DTOs.
8. `Any` must be minimized and kept only near technical boundaries.

---

## 1. Type Every Function Argument and Return Value

Every function must have an explicit and readable signature.

### Bad

``` python
def build_user(data):
    ...
````

### Good

```python
def build_user(data: dict[str, str]) -> UserDto:
    ...
```

### Good

```python
def get_names(users: list[UserDto]) -> list[str]:
    ...
```

A function signature must allow the reader to understand:

* what exactly comes in;
* what exactly goes out;
* what collection is used;
* what element type is stored inside that collection.

### Bad

```python
def process(data: Any) -> Any:
    ...
```

```python
def process(data: dict) -> list:
    ...
```

### Good

```python
def process(data: dict[str, str]) -> list[ProcessedItemDto]:
    ...
```

---

## 2. Use Concrete and Vivid Types in Signatures

Do not use vague container types when a more precise type can be written.

Prefer:

* `list[str]`
* `list[UserDto]`
* `dict[str, int]`
* `dict[str, UserDto]`
* `set[EntityId]`
* `tuple[str, int]`

### Good

```python
def collect_ids(users: list[UserDto]) -> list[int]:
    ...
```

```python
def build_index(users: list[UserDto]) -> dict[int, UserDto]:
    ...
```

```python
def get_usernames(mapping: dict[str, UserDto]) -> list[str]:
    ...
```

### Bad

```python
def collect_ids(users: list) -> list:
    ...
```

```python
def build_index(users: list[Any]) -> dict[Any, Any]:
    ...
```

```python
def get_usernames(mapping: dict) -> list[str]:
    ...
```

The signature must describe the real data shape, not an approximate one.

---

## 3. If a Function Has More Than 5 Arguments, Use a DTO

If a function has more than 4 arguments, those arguments must be grouped into a DTO.

DTOs for this purpose must be defined with `@dataclass(slots=True)`.

### Bad

```python
def create_user(
    name: str,
    email: str,
    age: int,
    is_active: bool,
    role: str,
) -> UserDto:
    ...
```

### Good

```python
from dataclasses import dataclass

@dataclass(slots=True)
class CreateUserDto:
    name: str
    email: str
    age: int
    is_active: bool
    role: str


def create_user(data: CreateUserDto) -> UserDto:
    ...
```

### Why this rule exists

* the function signature stays short and readable;
* related fields are grouped into one meaningful object;
* new fields can be added with less damage to call sites;
* the data contract becomes explicit.

---

## 4. All Complex Entities Must Be Represented as DTOs

Any complex structure must be represented as a DTO instead of a raw dictionary or a loose group of primitive values.

This includes:

* request bodies;
* data for create operations;
* data for update operations;
* return values from functions;
* service-layer payloads;
* command/query objects;
* filter objects.

A DTO should be used whenever an object:

* contains more than one field;
* contains more than one simple type;
* represents a meaningful business structure.

### Bad

```python
def create_order(data: dict[str, Any]) -> dict[str, Any]:
    ...
```

### Good

```python
from dataclasses import dataclass

@dataclass(slots=True)
class CreateOrderDto:
    customer_id: int
    product_ids: list[int]
    comment: str | None


@dataclass(slots=True)
class OrderDto:
    id: int
    customer_id: int
    status: str
    total_amount: float


def create_order(data: CreateOrderDto) -> OrderDto:
    ...
```

This removes ambiguity and makes the contract stable and discoverable.

---

## 5. DTOs Must Use `@dataclass(slots=True)`

DTOs should be declared with `@dataclass(slots=True)` by default.

### Example

```python
from dataclasses import dataclass

@dataclass(slots=True)
class UserDto:
    id: int
    name: str
    email: str
```

### Why `slots=True` should be used

* prevents accidental creation of undeclared attributes;
* makes DTOs stricter;
* reduces memory overhead;
* communicates that DTOs are fixed contracts, not dynamic containers.

DTOs are not bags of fields.
They are typed contracts.

---

## 6. Keep Primitive Arguments Only for Small and Simple Functions

Primitive parameters are fine for very small functions with a narrow purpose.

### Good

```python
def normalize_name(name: str) -> str:
    ...
```

But once the data becomes business-level and multi-field, it must be wrapped into a DTO.

### Bad

```python
def register_platform_connection(
    platform_id: int,
    zone_id: int,
    name: str,
    connection_url: str,
    is_active: bool,
    timeout: int,
) -> PlatformConnectionDto:
    ...
```

### Good

```python
from dataclasses import dataclass

@dataclass(slots=True)
class CreatePlatformConnectionDto:
    platform_id: int
    zone_id: int
    name: str
    connection_url: str
    is_active: bool
    timeout: int


def register_platform_connection(
    data: CreatePlatformConnectionDto,
) -> PlatformConnectionDto:
    ...
```

---

## 7. Return Typed Objects, Not Anonymous Structures

If a function returns meaningful business data, it should return a DTO instead of an anonymous dictionary.

### Bad

```python
def get_user_profile(user_id: int) -> dict[str, str | int | bool]:
    ...
```

### Good

```python
from dataclasses import dataclass

@dataclass(slots=True)
class UserProfileDto:
    id: int
    username: str
    age: int
    is_active: bool


def get_user_profile(user_id: int) -> UserProfileDto:
    ...
```

A dictionary is acceptable only when the dictionary itself is the true domain shape.
In all other cases, prefer a DTO.

---

## 8. Minimize `Any`

`Any` should be treated as an escape hatch, not as a normal type.

It is acceptable only near boundaries such as:

* framework internals;
* third-party libraries without typing;
* raw ORM filter dictionaries;
* temporary compatibility layers.

Even in such places, `Any` must remain local and must not spread into business logic.

### Bad

```python
def execute(data: Any) -> Any:
    ...
```

### Better

```python
def _build_raw_payload(data: UserDto) -> dict[str, Any]:
    ...
```

The goal is simple:

**untyped code may exist at the edges, but core business code must stay typed.**

---

## 9. ORM Query Filters Must Be Typed with Dedicated DTOs

ORM filters must not be passed around as ad hoc dictionaries from higher-level code.

Instead:

* define a dedicated filter DTO;
* keep raw repository filter generation inside that DTO or inside the repository boundary;
* build filter dictionaries in a controlled and typed way.

### Recommended Style

```python
from dataclasses import dataclass
from typing import Any

FilterValue = str | int | bool


def _set_eq(filters: dict[str, Any], field: str, value: FilterValue | None) -> None:
    """Add equality filter if value is provided."""
    if value is not None:
        filters[f"{field}__eq"] = value


def _set_ne(filters: dict[str, Any], field: str, value: FilterValue | None) -> None:
    """Add inequality filter if value is provided."""
    if value is not None:
        filters[f"{field}__ne"] = value


@dataclass(slots=True)
class PlatformConnectionEntityFilter:
    """Filters for PlatformConnectionModel repository queries."""

    id: EntityId | None = None
    id_not: EntityId | None = None
    platform_id: EntityId | None = None
    zone_id: EntityId | None = None
    name: str | None = None
    connection_url: str | None = None

    def as_repository_filters(self) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        _set_eq(filters, "id", self.id)
        _set_ne(filters, "id", self.id_not)
        _set_eq(filters, "platform_id", self.platform_id)
        _set_eq(filters, "zone_id", self.zone_id)
        _set_eq(filters, "name", self.name)
        _set_eq(filters, "connection_url", self.connection_url)
        return filters
```

### Why this approach is preferred

* the filter contract is explicit;
* filter fields are discoverable from the class definition;
* query building is centralized;
* string-based query construction is not scattered across the codebase;
* adding new filters stays predictable and safe.

---

## 10. DTO Names Must Describe Intent

DTO names must explain what the object is for.

### Good Names

* `CreateUserDto`
* `UpdateOrderDto`
* `UserResponseDto`
* `PlatformConnectionEntityFilter`
* `SyncVaultGroupCommand`

### Bad Names

* `Data`
* `Payload`
* `Info`
* `Params`
* `RequestObject`

A good DTO name tells the reader:

* where the object is used;
* what kind of operation it belongs to;
* what kind of data it carries.

---

## 11. DO / DON'T

## DO

* type every function argument;
* type every function return value;
* use explicit container types such as `list[str]` and `dict[str, UserDto]`;
* wrap more than 5 function arguments into a DTO;
* represent complex request and response objects as DTOs;
* use `@dataclass(slots=True)` for DTOs;
* create dedicated filter DTOs for ORM queries;
* keep untyped code only near technical boundaries.

## DON'T

* use untyped function signatures;
* pass around `dict[str, Any]` as a replacement for domain objects;
* return raw dictionaries for meaningful business entities;
* use `list`, `dict`, or `Any` when a precise type can be written;
* build ORM query filters as random dictionaries throughout the codebase;
* create DTOs without a clear business purpose;
* treat DTOs as mutable free-form containers.

---

## 12. Final Rule

Do not let data travel through the system in vague shapes.

Every meaningful structure must have an explicit typed contract.

That means:

* typed function signatures;
* typed DTOs;
* typed filters;
* typed return values;
* predictable data flow between layers.

The more explicit the contract is, the easier the code is to understand, extend, and trust.



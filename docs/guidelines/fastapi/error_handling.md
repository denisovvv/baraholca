# Python and FastAPI Error Handling Rules (Strict)

These rules are mandatory for API services.

## 1. Classify errors into two categories only

Every failure must be treated as either:

- domain/business error: expected rule violation
- unexpected/system error: infrastructure failure or bug

Business errors are returned as mapped 4xx responses.
Unexpected errors are logged with traceback and returned as 500.

## 2. Business logic must not raise transport exceptions

Required:

- raise domain exceptions in services and domain layer
- map domain exceptions to HTTP in API layer only

Forbidden:

- raising `HTTPException` from service/domain code

## 3. Use one exception hierarchy

Define and reuse a shared hierarchy, for example:

```python
class AppError(Exception):
    error_code = "app_error"


class DomainError(AppError):
    error_code = "domain_error"


class NotFoundError(DomainError):
    error_code = "not_found"


class ConflictError(DomainError):
    error_code = "conflict"
```

Required:

- domain exceptions must have stable machine-readable error codes
- exception class names must reflect business language

## 4. Validate business invariants explicitly

Use named guard helpers for important business checks.

```python
def _raise_if_order_already_paid(order: Order) -> None:
    if order.status == "paid":
        raise OrderAlreadyPaidError("order_already_paid")
```

Required:

- fail fast at invariant boundaries
- keep checks reusable and clearly named

## 5. Map exceptions to responses in one place

Use global exception handlers/middleware as the single mapping layer.

Required:

- one mapping strategy for the whole service
- no endpoint-level repeated `try/except` for common domain errors

## 6. Keep one response error contract

All error responses must follow one schema.

```json
{
  "error": {
    "code": "user_not_found",
    "message": "User not found"
  }
}
```

Required:

- stable `error.code` for client logic
- human-readable `error.message`

Forbidden:

- mixing multiple error shapes across endpoints

## 7. Never leak internals to clients

Forbidden in API responses:

- SQL errors
- tracebacks
- raw provider/library errors
- internal stack details

Internal details belong in logs only.

## 8. Wrap low-level exceptions at boundaries

Translate infrastructure exceptions into application/domain exceptions.

```python
try:
    repo.create_user(email)
except IntegrityError as exc:
    raise EmailAlreadyExistsError("email_already_exists") from exc
```

Required:

- preserve causality with `raise ... from exc`
- keep low-level exception types from escaping domain boundaries

## 9. Logging policy is strict

Required:

- log unexpected errors with traceback (`logger.exception`)
- keep domain error logging low-noise (usually warning/info or no log)
- include request context for unexpected failures

Forbidden:

- error-level logging for every expected business rejection
- swallowing exceptions without logging or mapping

## 10. Endpoints must stay thin

Endpoints should only:

- parse/validate request
- call service
- return mapped response

Forbidden:

- embedding business decision logic in endpoints
- ad-hoc domain checks in route handlers

## 11. Error paths are mandatory test scope

For each endpoint/use case, tests must cover:

- representative domain 4xx errors
- one unexpected 500 path
- response contract shape and error code

## 12. Anti-patterns (not allowed)

- `except Exception: pass`
- bare `except:`
- raise new exception without preserving cause where cause matters
- returning different error shapes for similar failures
- using free-text messages as the only client contract

## 13. Pre-merge checklist

Before merge, confirm:

- domain and system errors are clearly separated
- transport exceptions are not raised in domain/services
- exception-to-HTTP mapping is centralized
- error response schema is consistent
- internals are not exposed to clients
- key error paths are covered by tests

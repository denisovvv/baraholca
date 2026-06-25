# Django and DRF Error Handling Rules (Strict)

These rules are mandatory for DRF API services. They mirror the principles of the
FastAPI error handling rules (two error categories, domain exceptions separate
from transport, one error contract, no internal leaks) using DRF-idiomatic
mechanisms instead of FastAPI `HTTPException` and middleware.

## 1. Classify errors into two categories only

Every failure must be treated as either:

- domain/business error: an expected rule violation
- unexpected/system error: an infrastructure failure or bug

Business errors are mapped to 4xx responses.
Unexpected errors are logged with traceback and returned as 500.

## 2. Business logic must not raise transport exceptions

Required:

- raise domain exceptions in services and the domain layer
- map domain exceptions to HTTP responses only at the DRF boundary
  (custom `exception_handler` or serializer validation)

Forbidden:

- raising DRF `APIException` (or subclasses like `ValidationError`) from service/domain code
- importing `rest_framework` exceptions into the domain layer

## 3. Use one exception hierarchy

Define and reuse a shared hierarchy of plain Python exceptions, independent of DRF:

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

- domain exceptions have stable machine-readable error codes
- exception class names reflect business language

## 4. Validate business invariants explicitly

Use named guard helpers for important business checks.

```python
def _raise_if_order_already_paid(order: Order) -> None:
    if order.status == "paid":
        raise ConflictError("order_already_paid")
```

Required:

- fail fast at invariant boundaries
- keep checks reusable and clearly named

## 5. Map exceptions to responses in one place

Use a custom DRF `EXCEPTION_HANDLER` as the single mapping layer between domain
exceptions and HTTP responses.

```python
# config/settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.common.exception_handler.domain_exception_handler",
}
```

```python
# apps/common/exception_handler.py
def domain_exception_handler(exc, context):
    if isinstance(exc, NotFoundError):
        return _get_error_response(exc.error_code, str(exc), status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ConflictError):
        return _get_error_response(exc.error_code, str(exc), status.HTTP_409_CONFLICT)
    return drf_exception_handler(exc, context)
```

Required:

- one mapping strategy for the whole service
- no per-view repeated `try/except` for common domain errors

Forbidden:

- mapping domain errors to HTTP inside individual views
- duplicating the same domain-to-status mapping across views

## 6. Keep one response error contract

All error responses must follow one schema.

```json
{
  "error": {
    "code": "order_already_paid",
    "message": "Order is already paid"
  }
}
```

Required:

- a stable `error.code` for client logic
- a human-readable `error.message`

Forbidden:

- mixing multiple error shapes across endpoints
- returning DRF's default `{"detail": ...}` for some errors and a custom shape for others

## 7. Never leak internals to clients

Forbidden in API responses:

- SQL errors
- tracebacks
- raw provider/library errors
- internal stack details

Internal details belong in logs only. With `DEBUG = False` Django already hides
tracebacks; the exception handler must not reintroduce them into responses.

## 8. Wrap low-level exceptions at boundaries

Translate infrastructure exceptions (ORM, cache, external clients) into
application/domain exceptions at the repository/service boundary.

```python
try:
    user = User.objects.get(phone=phone)
except User.DoesNotExist as exc:
    raise NotFoundError("user_not_found") from exc
```

Required:

- preserve causality with `raise ... from exc`
- keep low-level exception types (`DoesNotExist`, `IntegrityError`) from escaping the domain boundary
- prefer generic, reusable exceptions (`NotFoundError`) over one class per entity;
  carry the specifics in the error code (`user_not_found`, `order_not_found`), not in a new class

Forbidden:

- creating a separate exception class per business entity when a generic one fits
- letting `Model.DoesNotExist` or `IntegrityError` propagate to views as control flow

## 9. Logging policy is strict

Required:

- log unexpected errors with traceback (`logger.exception`)
- keep domain error logging low-noise (usually warning/info or no log)
- include request context for unexpected failures

Forbidden:

- error-level logging for every expected business rejection
- swallowing exceptions without logging or mapping

## 10. Views and serializers stay thin

A view should only:

- parse/validate the request (serializer)
- call the service
- return the mapped response

Forbidden:

- embedding business decision logic in views
- ad-hoc domain checks in route handlers
- using serializer `validate_*` methods for cross-entity business rules that belong in services

## 11. Error paths are mandatory test scope

For each endpoint/use case, tests must cover:

- the success result, asserting the entire returned payload to ensure the
  response contract is correct (not just one or two fields)
- representative domain 4xx errors
- one unexpected 500 path
- the response contract shape and error code

DRF `APITestCase` is the entry point for these tests.

## 12. Anti-patterns — YOU MUST NEVER DO THE FOLLOWING

The following are strictly forbidden. An AI agent MUST NEVER produce code that
does any of these:

- YOU MUST NEVER write `except Exception: pass`
- YOU MUST NEVER write a bare `except:`
- YOU MUST NEVER raise a new exception without preserving the cause where the cause matters
- YOU MUST NEVER return different error shapes for similar failures
- YOU MUST NEVER raise DRF exceptions from the domain layer
- YOU MUST NEVER catch `DoesNotExist` in views as normal control flow

# Python Testing Rules (Strict)

These rules are mandatory for application tests unless a documented exception is approved in review.

## 1. Test behavior, not implementation

Required:

- verify externally observable behavior
- assert business outcomes, persisted state, and published effects
- keep tests resilient to refactoring

Forbidden:

- asserting that one internal method called another as the main proof of correctness
- coupling tests to private implementation details

## 2. Prefer testing through real entry points

For application behavior, prefer testing through:

- HTTP endpoints
- message handlers
- CLI commands
- public service interfaces

Required:

- exercise the same paths real callers use
- cover routing, validation, business logic, serialization, and infrastructure integration where relevant

Forbidden:

- excessive unit slicing that misses real system behavior

## 3. Use real internal dependencies where practical

Required:

- use real databases, caches, brokers, and other internal infrastructure when the test scope depends on them
- prefer test containers or equivalent isolated environments for integration tests

Why:

- it verifies object mapping and serialization
- it catches configuration and integration failures early
- it reduces false confidence from heavily mocked tests

## 4. Mock only boundaries you do not control

Mocks are acceptable for:

- third-party HTTP APIs
- payment providers
- email or SMS providers
- unstable or expensive external systems
- hard-to-reproduce external failure modes

Forbidden:

- mocking core internal collaborators by default
- using mocks to avoid testing real internal flows

## 5. Keep tests deterministic and isolated

Required:

- isolate state between tests
- control input data and time-sensitive behavior
- make results reproducible locally and in CI

Forbidden:

- hidden shared state between tests
- order-dependent tests
- reliance on random data without controlled seeds or explicit values

## 6. Use factories or builders for test data

Required:

- create reusable factories/builders for common entities and requests
- keep scenario setup concise and readable

Forbidden:

- large repeated setup blocks across tests
- hand-building the same object graphs in many places

## 7. Cover failure paths, not only happy paths

Tests must cover representative negative scenarios, including:

- invalid input
- missing required fields
- permission failures
- duplicates and conflicts
- invalid state transitions
- repeated deliveries or duplicate events
- empty or partial data
- unexpected 500 paths where relevant

See [error_handling.md](/Users/allxndrskllv/PycharmProjects/guidelines-python/error_handling.md) for required error contract behavior.

## 8. Assert side effects, not only responses

When a scenario changes the system, assert the effect completely.

Required where relevant:

- database state changes
- emitted events or messages
- cache updates
- audit records
- queued background tasks

Forbidden:

- treating status code alone as sufficient proof of success

## 9. Protect response and message contracts

Required:

- validate response shape, required fields, and types
- validate serialized event/message structure when other systems depend on it
- prefer asserting the full response body when reasonable

Forbidden:

- checking only one or two fields when the full contract matters
- allowing silent response shape drift

## 10. Structure tests clearly

Use `Arrange`, `Act`, `Assert`.

Required:

- keep setup, action, and assertions visually distinct
- keep one behavior scenario per test where practical

Forbidden:

- mixing setup and assertions into one unreadable flow
- multiple unrelated behaviors in one test

## 11. Name tests by behavior

Required:

- use names that describe the scenario and expected outcome

Forbidden:

- generic names like `test_1`, `test_success`, or `test_service`

## 12. Anti-patterns (not allowed)

- tests that mainly verify mock call counts for internal behavior
- broad fixture magic that hides scenario intent
- assertions so weak that contract regressions pass unnoticed
- tests that depend on execution order
- duplicate setup that should be a factory

## 13. Pre-merge checklist

Before merge, confirm:

- critical behavior is covered through real entry points
- internal infrastructure is tested with real components where it matters
- external dependencies are the only major mocks
- negative paths are covered
- side effects are asserted
- contract responses/messages are protected
- tests are deterministic and readable

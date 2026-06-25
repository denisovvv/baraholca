# Python Clean Code Rules (Strict)

These rules are mandatory for production code unless a documented exception is approved in review.

## 1. Optimize for readability first

Code is read more often than it is written.

Required:

- prefer clear names and straightforward control flow over clever shortcuts
- write code so a new team member can understand intent quickly

Forbidden:

- compact expressions that hide business intent
- tricks that reduce clarity for small line-count savings

## 2. Use intent-revealing names

Required:

- use nouns for data (`user`, `invoice`, `retry_count`)
- use verbs for actions (`load_user`, `validate_input`)
- include domain meaning in names

Forbidden:

- vague names like `data`, `obj`, `tmp`, `stuff`
- misleading abbreviations

## 3. Keep functions focused, small, and single-level

Each function must have one responsibility.

Required:

- keep one abstraction level per function
- prefer guard clauses to deep nesting
- split long functions instead of adding more branches

Forbidden:

- mixing business policy and infrastructure details in one function
- boolean flag arguments that switch behavior
- large argument lists for business operations

## 4. Use explicit domain models and DTOs

Required:

- use explicit DTOs or domain models for structured data
- keep transport schemas, domain entities, and ORM models separated
- use separate input and output DTOs when meaning differs

Forbidden:

- passing raw `dict`/`tuple` payloads across application boundaries
- primitive obsession for domain concepts

## 5. Type annotations are part of the contract

Required:

- type every function argument and return value
- type all public methods
- use precise collection types (`list[str]`, `Mapping[str, str]`)
- model `None` explicitly when possible in returns

Forbidden:

- implicit return types in production code
- broad `Any` without a documented reason
- bare `dict`, `list`, `tuple` when a precise type is known

## 6. Keep condition-heavy logic explicit

Required:

- replace long conditional chains with mappings, policies, or polymorphism when it improves clarity
- raise explicit domain errors for unsupported cases

Forbidden:

- deeply nested conditionals for normal flows
- silent fallback behavior for unknown domain states

## 7. Errors must be explicit and domain-specific

Required:

- raise meaningful custom exceptions for business rule violations
- keep error names aligned with domain language
- preserve root causes with `raise ... from exc` when translating exceptions

Forbidden:

- swallowing exceptions (`except Exception: pass`)
- generic exceptions for known business rules

See [error_handling.md](/Users/allxndrskllv/PycharmProjects/guidelines-python/error_handling.md) for API and logging policy.

## 8. Keep business logic framework-agnostic

Required:

- keep FastAPI/Django/ORM details at the edges
- pass commands/DTOs/interfaces into core services

Forbidden:

- coupling domain functions directly to HTTP/request/ORM primitives

## 9. Control side effects

Required:

- keep pure computations separate from I/O where practical
- isolate side-effect boundaries (DB, network, files, queue)

Forbidden:

- mixing complex business branching and side effects in one dense function

## 10. Remove duplication of knowledge, not by default of syntax

Required:

- remove repeated business rules and repeated domain assumptions
- allow small local duplication when abstraction would reduce readability

Forbidden:

- speculative abstractions added before repeated need exists

## 11. Organize code by feature

Required:

- keep files related to one business feature close together
- keep module boundaries explicit

Forbidden:

- scattering one feature across many unrelated top-level technical folders

## 12. Keep classes cohesive

Required:

- keep one reason to change per class
- split classes with unrelated responsibilities

Forbidden:

- "god objects" with many unrelated methods and dependencies

## 13. Tests must describe behavior

Required:

- use test names that explain expected behavior
- verify business outcomes, not internal call sequences

See [testing.md](/Users/allxndrskllv/PycharmProjects/guidelines-python/testing.md) for strict test policy.

## 14. Consistency is mandatory

Within one repository, be consistent in:

- naming
- typing
- error patterns
- logging and return style
- DTO conventions

Inconsistency is technical debt.

## 15. Do not bypass quality tools by default

`noqa`, `type: ignore`, `pragma: no cover`, and similar suppressions are exceptional.

Required when suppression is unavoidable:

- keep it local and specific
- explain why in code comment
- link it to a concrete limitation (for example, third-party typing issue)

Forbidden:

- broad file-level or config-level suppressions to hide code smells
- repeated suppressions instead of fixing design
- routine `if TYPE_CHECKING:` blocks used to work around circular dependencies instead of fixing module boundaries

## 16. Keep imports at module top level

Required:

- declare dependencies at module top so they are visible immediately
- treat local imports as rare technical exceptions

Allowed local imports only when justified:

- optional dependency not always installed
- heavy dependency used in a narrow path with measured impact

Forbidden:

- local imports to hide circular dependencies or module design issues

## 17. Pre-commit checklist

Before merge, confirm:

- names are clear
- each function has one responsibility
- types are complete and precise
- DTO/model boundaries are explicit
- business errors are explicit
- suppressions are justified and minimal
- tests cover behavior and key failure paths

## 18. Golden rule

Clean code is easy to read, easy to change, and hard to misuse.

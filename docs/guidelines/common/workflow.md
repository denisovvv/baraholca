# Development Workflow Rules (Strict)

These rules describe how work must be done. They apply to every change.

## 1. Git is human-only

**Git operations are performed by a human, never by an AI agent.** An AI agent
MUST NOT run git commands or drive the git history. An AI agent produces code and
tests; the human reviews, commits, and merges them.

## 2. Tests are written with the code

Tests follow `common/testing.md`.

Required:

- add or update tests in the same change as the code
- write tests according to the testing guideline

Forbidden:

- changing behavior without accompanying tests

## 3. Linters and type checks must pass

Required:

- run `ruff` and `mypy` on the changed code
- fix the code so all linters and type checks report no errors

YOU MUST NEVER weaken, disable, or reconfigure a linter rule to make an error go
away. Suppressions (`# noqa`, `# type: ignore`) are exceptional, must be local
and specific, and must carry a comment explaining the concrete reason.

## 4. Code must follow the guidelines

Before a change is considered done, confirm:

- code follows the applicable guidelines (`common/`, and `django/` or `fastapi/`)
- tests are present, written per `common/testing.md`, and pass
- `ruff` and `mypy` report no errors

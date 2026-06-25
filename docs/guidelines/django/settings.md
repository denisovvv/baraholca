# Django Application Settings Rules (Strict)

These rules are mandatory for Django application configuration code. They mirror
the principles of the FastAPI settings rules (typing, domain separation,
validation, no scattered secrets) using Django-idiomatic mechanisms instead of
`pydantic-settings`.

## 1. Single configuration entry point

Required:

- keep all application configuration in the Django settings module (`config/settings.py`)
- read environment-dependent values from environment variables
- keep secrets out of code and out of version control

Forbidden:

- reading configuration from arbitrary places in business code (views, services, models)
- hardcoding secrets (`SECRET_KEY`, database passwords, provider keys) in code
- parallel configuration mechanisms alongside Django settings

## 2. Secrets and environment-dependent values come from environment variables only

Required:

- read `SECRET_KEY`, database credentials, and external service keys via `os.getenv`
- keep critical secrets without a default so the app fails fast when they are missing
- use safe defaults only where a default is genuinely safe (for example `DEBUG` defaults to `False`)

```python
# Good: critical secret without default — fail fast
SECRET_KEY = os.getenv('SECRET_KEY')

# Good: safe default (disabled by default)
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Good: safe default for local development
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
```

Forbidden:

- `SECRET_KEY = 'hardcoded-value'`
- default values for passwords and production secrets
- `DEBUG = True` as a default value

## 3. Convert types explicitly when reading the environment

Environment variables are always strings. Convert them to the required type at
read time, in the settings module — never in business code.

Required:

- `bool` via explicit comparison: `os.getenv('DEBUG', 'False') == 'True'`
- `int` via conversion: `int(os.getenv('DATABASE_PORT', '5432'))`
- lists via `split`: `os.getenv('ALLOWED_HOSTS', '...').split(',')`

Forbidden:

- passing a raw env string where a number or boolean is expected
- converting env value types in services, repositories, or views
- truthy-string checks for booleans (`if os.getenv('DEBUG'):` — the non-empty
  string `'False'` is truthy, which is a bug)

## 4. Separate settings by domain using sections

Django has no settings classes, but separation by responsibility is mandatory.
Group related settings into clearly titled sections of the settings module.

Required:

- one titled section per settings domain (REST framework, JWT, cache, SMS, docs, etc.)
- consistent section ordering and headers across the file

```python
# ============================================================================
# REST Framework
# ============================================================================
REST_FRAMEWORK = { ... }

# ============================================================================
# JWT (simplejwt)
# ============================================================================
SIMPLE_JWT = { ... }

# ============================================================================
# Cache / Redis
# ============================================================================
CACHES = { ... }
```

Forbidden:

- an unstructured dump of unrelated settings
- duplicating the same env reads in multiple places in the file

As the project grows, splitting settings into a package
(`config/settings/base.py`, `config/settings/prod.py`) is allowed — but this is
separation by environment, not abandoning the Django mechanism.

## 5. Scope environment variable names by domain prefix

The equivalent of `env_prefix`, expressed through an environment variable naming
convention.

Required:

- variables of one domain share a common name prefix
  (`DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`)
- the variable name reflects the real meaning of the setting

```dotenv
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_NAME=baraxolka_dev
DATABASE_USER=postgres
DATABASE_PASSWORD=...
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

Forbidden:

- inconsistent naming for variables of one domain
- names that do not reflect meaning (`VAR1`, `DB`, `X`)

## 6. Gate production security settings behind a condition

Settings that must apply only in production (SSL, HSTS, secure cookies) are
enabled by an environment flag so they do not break local development.

Required:

- production security settings under `if not DEBUG:`
- local development works without HTTPS and production restrictions

```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 3600
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

Forbidden:

- unconditionally enabling HTTPS settings (breaks local development)
- secret values or modes hardcoded in code instead of read from the environment

## 7. An environment template is mandatory

Required:

- the repository contains `.env.example` — a template with all variables and no values
- the real `.env` is in `.gitignore` and is never committed
- `.env.example` is committed and documents the required variables

Forbidden:

- committing a real `.env`
- missing template (a new developer does not know what to fill in)

## 8. Anti-patterns — YOU MUST NEVER DO THE FOLLOWING

The following are strictly forbidden. An AI agent MUST NEVER produce code that
does any of these:

- YOU MUST NEVER hardcode secrets in `settings.py`
- YOU MUST NEVER read the same setting via `os.getenv` in multiple places across the codebase
- YOU MUST NEVER read or convert env values in services/views instead of the settings module
- YOU MUST NEVER leave `DEBUG = True` or an empty `SECRET_KEY` as a working state
- YOU MUST NEVER put business logic inside the settings module
- YOU MUST NEVER enable production security settings unconditionally in a way that breaks local development

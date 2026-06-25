# Python Application Settings Rules (Strict)

These rules are mandatory for application configuration code.

## 1. Use `pydantic-settings` only

Required:

- define application configuration with `pydantic-settings`
- inherit all settings classes from `BaseSettings`
- keep settings typed and validated

Forbidden:

- reading application settings directly with `os.getenv()` throughout the codebase
- mixing `dotenv`, ad-hoc parsing, and manual casting with settings classes
- storing configuration in untyped dictionaries

## 2. `model_config` is mandatory in every class

Every settings class must declare its own `model_config`.

```python
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    env_prefix="MVD_",
)
```

These rules are mandatory:

- `env_file` must be `.env`
- `env_file_encoding` must be `utf-8`
- `extra` must be `ignore`
- `env_prefix` must be present in every settings class
- `env_prefix` must be unique for every settings class

Example prefixes:

- `Settings` -> `MVD_`
- `DatabaseSettings` -> `MVD_DB_`
- `KafkaSettings` -> `MVD_KAFKA_`

Forbidden:

- a different encoding
- a different env file
- a different `extra` mode
- missing `env_prefix`
- reusing the same `env_prefix` in multiple classes

## 3. Separate settings by domain

Settings must be split by responsibility.

Required:

- keep general application settings in `Settings`
- keep database settings in a dedicated class such as `DatabaseSettings`
- keep Kafka settings in a dedicated class such as `KafkaSettings`
- create additional settings classes for other domains when needed

Forbidden:

- one giant settings class containing unrelated domains
- mixing database, Kafka, HTTP client, and feature-flag settings into one flat class

## 4. Let `env_prefix` manage prefixes

`env_prefix` is the only allowed prefix mechanism for environment variables.

Required:

- rely on `env_prefix` for domain scoping
- give each settings class its own unique prefix
- keep field names aligned with the real setting meaning

Examples:

- `app_name` -> `MVD_APP_NAME`
- `host` in `DatabaseSettings` -> `MVD_DB_HOST`
- `port` in `DatabaseSettings` -> `MVD_DB_PORT`
- `bootstrap_servers` in `KafkaSettings` -> `MVD_KAFKA_BOOTSTRAP_SERVERS`

Forbidden:

- adding manual prefixes in field names only to repeat `env_prefix`
- managing prefixes through aliases or custom parsing logic
- sharing one prefix across unrelated classes

## 5. Keep settings classes typed and strict

Required:

- use proper Python types for every field
- give safe defaults only where a real default exists
- keep required settings required

Preferred examples:

- `bool` instead of parsing `"true"` manually
- `int` instead of converting string ports in runtime code
- `str | None` only when the value is truly optional

Forbidden:

- parsing and converting env values manually in business code
- using `Any` for settings fields
- making everything optional to avoid validation errors

## 6. Load settings once at the application edge

Settings should be created near startup, dependency wiring, or composition root.

Required:

- instantiate settings in one dedicated module
- define singleton settings objects at the bottom of that module

Forbidden:

- creating new settings objects deep inside business logic
- reading configuration repeatedly in unrelated modules

## 7. Recommended structure

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MVD_",
    )
    app_name: str = "mvd-service"
    debug: bool = False


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MVD_DB_",
    )
    host: str
    port: int = 5432
    name: str
    user: str
    password: str


class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="MVD_KAFKA_",
    )
    bootstrap_servers: str
    username: str | None = None
    password: str | None = None
    user_events_topic: str


settings = Settings()
database_settings = DatabaseSettings()
kafka_settings = KafkaSettings()
```

## 8. Example `.env` layout

```dotenv
MVD_APP_NAME=mvd-service
MVD_DEBUG=false

MVD_DB_HOST=localhost
MVD_DB_PORT=5432
MVD_DB_NAME=app
MVD_DB_USER=postgres
MVD_DB_PASSWORD=postgres

MVD_KAFKA_BOOTSTRAP_SERVERS=localhost:9092
MVD_KAFKA_USERNAME=
MVD_KAFKA_PASSWORD=
MVD_KAFKA_USER_EVENTS_TOPIC=user-events
```

## 9. Anti-patterns (not allowed)

- putting shared `model_config` into a base settings class
- using `db_host` or `kafka_bootstrap_servers` when `env_prefix` already scopes the domain
- reusing one `env_prefix` across multiple settings classes
- omitting `env_prefix` in a settings class
- creating one `Settings` class that contains every field in the system
- reading env vars manually in services, repositories, or endpoints
- placing business logic inside settings classes

## 10. Pre-merge checklist

Before merge, confirm:

- `pydantic-settings` is used
- each settings class defines its own `SettingsConfigDict`
- the fixed `env_file`, `env_file_encoding`, and `extra` values are preserved
- settings are split by domain
- general settings live in `Settings`
- database settings live in `DatabaseSettings`
- Kafka settings live in `KafkaSettings`
- each settings class has a unique `env_prefix`

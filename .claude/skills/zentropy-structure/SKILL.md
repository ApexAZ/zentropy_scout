---
name: zentropy-structure
description: |
  Module organization for Zentropy Scout backend. Load when:
  - Creating new files or modules
  - Deciding where code should live
  - Someone asks "where should I put this" or "project structure"
---

# Zentropy Scout Module Organization

## Backend Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── core/
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── database.py         # Engine, session factory
│   │   └── security.py         # Auth utilities (future)
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── __init__.py         # Export all models
│   │   ├── base.py             # Base class, mixins
│   │   ├── persona.py
│   │   ├── job_posting.py
│   │   └── application.py
│   │
│   ├── schemas/                # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── persona.py          # PersonaCreate, PersonaRead, etc.
│   │   └── job_posting.py
│   │
│   ├── repositories/           # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py             # Generic CRUD base
│   │   ├── persona.py
│   │   └── job_posting.py
│   │
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── extraction.py       # LLM extraction logic
│   │   ├── scoring.py          # Job matching
│   │   └── generation.py       # Resume/cover letter
│   │
│   ├── providers/              # External integrations
│   │   ├── __init__.py
│   │   ├── llm/
│   │   │   ├── base.py         # LLMProvider ABC
│   │   │   ├── claude_sdk.py   # Claude Agent SDK impl
│   │   │   └── anthropic.py    # Direct API impl (future)
│   │   └── embedding/
│   │       ├── base.py
│   │       └── openai.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependency injection
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py       # Aggregate all routers
│   │       ├── personas.py
│   │       └── jobs.py
│   │
│   └── agents/                 # LangGraph agent definitions
│       ├── __init__.py
│       ├── base.py             # Shared agent utilities
│       ├── chat.py
│       ├── onboarding.py
│       ├── scouter.py
│       ├── strategist.py
│       └── ghostwriter.py
│
├── migrations/                 # Alembic migrations
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
│
├── tests/
│   ├── conftest.py             # Fixtures
│   ├── test_personas.py        # Mirror source structure
│   └── test_jobs.py
│
├── pyproject.toml              # Dependencies, ruff config
└── alembic.ini
```

## File Placement Rules

| Code Type | Location | Example |
|-----------|----------|---------|
| ORM model | `app/models/` | `persona.py` |
| Pydantic schema | `app/schemas/` | `persona.py` (PersonaCreate, PersonaRead) |
| DB queries | `app/repositories/` | `persona.py` (PersonaRepository) |
| Business logic | `app/services/` | `extraction.py` |
| API routes | `app/api/v1/` | `personas.py` |
| LLM integration | `app/providers/llm/` | `claude_sdk.py` |
| Agent definitions | `app/agents/` | `scouter.py` |

## Strict Rules

1. **One class per file** (exceptions: small related classes)
2. **Files under 300 lines** — split if larger
3. **No `utils.py` dumping ground** — be specific (`date_utils.py`, `text_utils.py`)
4. **Tests mirror source structure** — `app/services/extraction.py` → `tests/services/test_extraction.py`

## Decision Tree: Where Does This Code Go?

```
Is it a database table definition?
  → app/models/

Is it a request/response shape?
  → app/schemas/

Does it query the database?
  → app/repositories/

Is it business logic using repos + providers?
  → app/services/

Is it an HTTP endpoint?
  → app/api/v1/

Does it call external APIs (LLM, embeddings)?
  → app/providers/

Is it an AI agent with state machine logic?
  → app/agents/
```

---

## Configuration Templates

### pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "zentropy-scout"
version = "0.1.0"
description = "AI-powered job application assistant"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    # Web Framework
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",

    # Database
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pgvector>=0.2.4",

    # LLM Providers
    "anthropic>=0.18.0",
    "openai>=1.12.0",

    # Agent Framework
    "langgraph>=0.0.40",

    # PDF Generation
    "reportlab>=4.1.0",

    # HTTP Client
    "httpx>=0.27.0",

    # Utilities
    "python-dotenv>=1.0.0",
    "tenacity>=8.2.0",
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",

    # Linting & Formatting
    "ruff>=0.2.0",
    "mypy>=1.8.0",

    # Type Stubs
    "types-python-dateutil",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort (import sorting)
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/__init__.py"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
ignore_missing_imports = true
```

### alembic.ini

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### migrations/env.py

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### app/core/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "zentropy_scout"
    database_user: str = "zentropy_user"
    database_password: str = "zentropy_dev_password"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        """Async database URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync database URL for Alembic."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


settings = Settings()
```

### app/core/database.py

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### app/models/base.py

```python
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that adds soft delete capability."""

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None
```

### tests/conftest.py

```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.base import Base

# Use separate test database
TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name,
    f"{settings.database_name}_test"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()
```

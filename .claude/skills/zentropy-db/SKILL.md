---
name: zentropy-db
description: |
  Database patterns for Zentropy Scout. Load this skill when:
  - Creating tables, columns, migrations, or schema changes
  - Working with SQLAlchemy models or Alembic
  - Using pgvector for embeddings or vector search
  - Storing files (BYTEA rule), JSONB fields, or indexes
  - Writing repository classes or database queries
  - Someone asks about "the database", "DB", "postgres", "SQL", or "migration"
---

# Zentropy Scout Database Patterns

## Reference Document
**Read first:** `docs/requirements/REQ-005_database_schema.md`

## Critical Rule: File Storage
**ALL files stored as BYTEA in PostgreSQL.** No S3, no filesystem paths.

```python
# CORRECT
class ResumeVersion(Base):
    pdf_content: Mapped[bytes]  # BYTEA column

# WRONG — never do this
pdf_path: str  # No filesystem paths
s3_key: str    # No S3 references
```

## pgvector Setup

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

class JobPosting(Base):
    __tablename__ = "job_postings"

    # Vector column for culture embeddings (1536 dims = OpenAI)
    job_culture: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=True
    )
```

## Cosine Similarity Search

```python
from sqlalchemy import select

async def find_similar_jobs(
    session: AsyncSession,
    query_vector: list[float],
    limit: int = 10
) -> list[JobPosting]:
    stmt = (
        select(JobPosting)
        .where(JobPosting.job_culture.isnot(None))
        .order_by(JobPosting.job_culture.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
```

## JSONB Columns

```python
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class Persona(Base):
    # Use JSONB for queryable structured data
    skills: Mapped[dict] = mapped_column(JSONB, default=dict)

    # GIN index for JSONB queries
    __table_args__ = (
        Index('ix_persona_skills', skills, postgresql_using='gin'),
    )
```

## Alembic Migration Template

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = '${up_revision}'
down_revision = ${down_revision}
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create table
    op.create_table(
        'table_name',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        # ... more columns
    )

    # Add index
    op.create_index('ix_table_column', 'table_name', ['column'])


def downgrade() -> None:
    # MUST implement downgrade that actually works
    op.drop_index('ix_table_column')
    op.drop_table('table_name')
```

## Migration Rules

1. **One logical change per migration** — Don't combine unrelated changes
2. **Always implement downgrade()** — Must actually reverse the upgrade
3. **Test both directions locally** — `alembic upgrade head` then `alembic downgrade -1`
4. **Never modify pushed migrations** — Create new migration instead

## Common Commands

```bash
# Create new migration
alembic revision --autogenerate -m "add persona table"

# Apply migrations
alembic upgrade head

# Rollback one
alembic downgrade -1

# Show current revision
alembic current

# Show history
alembic history
```

## Database Connection

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/zentropy_scout"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

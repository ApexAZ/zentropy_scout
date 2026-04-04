"""Seed task_routing_config for search_profile_generation task type.

Revision ID: 032_search_profile_routing
Revises: 031_search_bucket_cursors
Create Date: 2026-04-04

REQ-034 §4.3, §11: Insert three task_routing_config rows (one per provider)
for the SEARCH_PROFILE_GENERATION task type. Routes to the same cost tier as
EXTRACTION — cheap/fast models suitable for JSON generation at scale.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "032_search_profile_routing"
down_revision: str = "031_search_bucket_cursors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TASK_TYPE = "search_profile_generation"

# Same cost tier as EXTRACTION — REQ-034 §4.3
_ROUTING: tuple[tuple[str, str], ...] = (
    ("claude", "claude-3-5-haiku-20241022"),
    ("openai", "gpt-4o-mini"),
    ("gemini", "gemini-2.0-flash"),
)

# Ad-hoc table proxy for inserting into existing task_routing_config table
_task_routing_config = sa.table(
    "task_routing_config",
    sa.column("provider", sa.String),
    sa.column("task_type", sa.String),
    sa.column("model", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Insert routing rows for search_profile_generation into task_routing_config."""
    now = datetime.now(UTC)
    op.bulk_insert(
        _task_routing_config,
        [
            {
                "provider": provider,
                "task_type": _TASK_TYPE,
                "model": model,
                "created_at": now,
                "updated_at": now,
            }
            for provider, model in _ROUTING
        ],
    )


def downgrade() -> None:
    """Remove search_profile_generation routing rows from task_routing_config."""
    op.execute(
        sa.text(
            "DELETE FROM task_routing_config WHERE task_type = :task_type"
        ).bindparams(task_type=_TASK_TYPE)
    )

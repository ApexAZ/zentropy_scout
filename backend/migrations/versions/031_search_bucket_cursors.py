"""Add search_bucket to persona_jobs and last_seen_external_ids to polling_configurations.

Revision ID: 031_search_bucket_cursors
Revises: 030_search_profiles
Create Date: 2026-04-03

REQ-034 §6.1, §5.4, §11: Two column additions that support the SearchProfile-driven
fetch pipeline. search_bucket tags each PersonaJob with the bucket that surfaced it
(fit/stretch/manual/pool). last_seen_external_ids is a per-source cursor map used to
skip already-seen job IDs on incremental polls, enabling early-exit deduplication.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "031_search_bucket_cursors"
down_revision: str = "030_search_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERSONA_JOBS = "persona_jobs"
_POLLING_CFG = "polling_configurations"
_CK_SEARCH_BUCKET = "ck_persona_jobs_search_bucket"

# Reusable SQL text fragment (extracted to avoid S1192 string-literal duplication)
_JSONB_EMPTY_OBJ = sa.text("'{}'::jsonb")


def upgrade() -> None:
    """Add search_bucket to persona_jobs and last_seen_external_ids to polling_configurations."""
    # (a) persona_jobs: nullable search_bucket with CHECK constraint.
    # NULL means the job was discovered before search buckets existed (backward compat).
    op.add_column(
        _PERSONA_JOBS,
        sa.Column("search_bucket", sa.String(20), nullable=True),
    )
    op.create_check_constraint(
        _CK_SEARCH_BUCKET,
        _PERSONA_JOBS,
        "search_bucket IN ('fit', 'stretch', 'manual', 'pool')",
    )

    # (b) polling_configurations: per-source cursor map, defaults to empty object.
    # Empty object means "no prior cursor — treat all jobs as new on first poll".
    op.add_column(
        _POLLING_CFG,
        sa.Column(
            "last_seen_external_ids",
            JSONB,
            nullable=False,
            server_default=_JSONB_EMPTY_OBJ,
        ),
    )


def downgrade() -> None:
    """Remove search_bucket from persona_jobs and last_seen_external_ids from polling_configurations."""
    op.drop_column(_POLLING_CFG, "last_seen_external_ids")
    op.drop_constraint(_CK_SEARCH_BUCKET, _PERSONA_JOBS, type_="check")
    op.drop_column(_PERSONA_JOBS, "search_bucket")

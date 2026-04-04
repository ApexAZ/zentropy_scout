"""Create search_profiles table.

Revision ID: 030_search_profiles
Revises: 029_settlement_retry
Create Date: 2026-04-03

REQ-034 §4.2, §11: AI-generated search criteria for a persona, split into
fit_searches and stretch_searches JSONB buckets. One profile per persona
(UNIQUE FK). is_stale flag enables re-generation when persona material
fields change (tracked via persona_fingerprint SHA-256).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "030_search_profiles"
down_revision: str = "029_settlement_retry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "search_profiles"
_UQ_PERSONA = "uq_search_profiles_persona_id"
_FK_PERSONA = "fk_search_profiles_persona_id"
_CK_FIT_ARRAY = "ck_search_profiles_fit_searches_array"
_CK_STRETCH_ARRAY = "ck_search_profiles_stretch_searches_array"

# Reusable SQL text fragments (extracted to avoid S1192 string-literal duplication)
_UUID_DEFAULT = sa.text("gen_random_uuid()")
_JSONB_EMPTY_ARRAY = sa.text("'[]'::jsonb")
_NOW = sa.text("now()")


def upgrade() -> None:
    """Create search_profiles table with JSONB search buckets and staleness tracking."""
    op.create_table(
        _TABLE,
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=_UUID_DEFAULT,
            nullable=False,
        ),
        sa.Column(
            "persona_id",
            UUID(as_uuid=True),
            sa.ForeignKey("personas.id", ondelete="CASCADE", name=_FK_PERSONA),
            nullable=False,
        ),
        # JSONB buckets: list of SearchBucket objects
        sa.Column(
            "fit_searches", JSONB, nullable=False, server_default=_JSONB_EMPTY_ARRAY
        ),
        sa.Column(
            "stretch_searches", JSONB, nullable=False, server_default=_JSONB_EMPTY_ARRAY
        ),
        # SHA-256 hex digest (64 chars) of material persona fields at generation time.
        # Empty string is the valid un-generated default — is_stale guards against
        # false-match comparisons between two un-generated profiles.
        sa.Column(
            "persona_fingerprint",
            sa.String(64),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # is_stale: True until user approves; set True again on persona material change.
        # Defaults to True (safe-fail: treat as stale until proven current).
        sa.Column(
            "is_stale",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        # Timestamps — nullable: profile row may exist before generation/approval
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        # Audit timestamps (updated_at refreshed by ORM onupdate, not a DB trigger)
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_NOW,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_NOW,
        ),
        # One SearchProfile per Persona
        sa.UniqueConstraint("persona_id", name=_UQ_PERSONA),
        # Enforce JSONB array shape at the DB level (defense-in-depth)
        sa.CheckConstraint("jsonb_typeof(fit_searches) = 'array'", name=_CK_FIT_ARRAY),
        sa.CheckConstraint(
            "jsonb_typeof(stretch_searches) = 'array'", name=_CK_STRETCH_ARRAY
        ),
    )


def downgrade() -> None:
    """Drop search_profiles table."""
    op.drop_table(_TABLE)

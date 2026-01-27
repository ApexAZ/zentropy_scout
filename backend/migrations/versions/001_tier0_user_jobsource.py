"""Create Tier 0 tables: User and JobSource.

Revision ID: 001_tier0_user_jobsource
Revises: 000_enable_extensions
Create Date: 2026-01-26

REQ-005 §4.0 User - Auth foundation (minimal for MVP)
REQ-005 §4.4 JobSource - Global registry of job sources
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_tier0_user_jobsource"
down_revision: str | None = "000_enable_extensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # User table - REQ-005 §4.0
    # Minimal auth foundation. MVP uses pre-populated default user.
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_user_email", "users", ["email"], unique=True)

    # JobSource table - REQ-005 §4.4
    # Global registry of job sources. System-managed.
    op.create_table(
        "job_sources",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("api_endpoint", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source_type IN ('API', 'Extension', 'Manual')",
            name="ck_job_sources_source_type",
        ),
    )
    op.create_index("idx_jobsource_name", "job_sources", ["source_name"], unique=True)

    # Seed data for MVP job sources - REQ-005 §4.4
    op.execute(
        """
        INSERT INTO job_sources (source_name, source_type, description, display_order)
        VALUES
            ('Adzuna', 'API', 'Adzuna job aggregator API', 1),
            ('The Muse', 'API', 'The Muse career platform API', 2),
            ('RemoteOK', 'API', 'RemoteOK remote jobs API', 3),
            ('USAJobs', 'API', 'US Government jobs API', 4),
            ('Chrome Extension', 'Extension', 'Browser extension job capture', 5),
            ('Manual', 'Manual', 'User-entered job postings', 6)
    """
    )

    # Seed default user for MVP local mode
    op.execute(
        """
        INSERT INTO users (id, email)
        VALUES ('00000000-0000-0000-0000-000000000001', 'default@local.dev')
    """
    )


def downgrade() -> None:
    op.drop_index("idx_jobsource_name")
    op.drop_table("job_sources")
    op.drop_index("idx_user_email")
    op.drop_table("users")

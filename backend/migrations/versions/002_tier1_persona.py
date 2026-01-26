"""Create Tier 1 table: Persona.

Revision ID: 002_tier1_persona
Revises: 001_tier0_user_jobsource
Create Date: 2026-01-26

REQ-005 §4.1 Persona - Central user profile table.
Note: original_resume_file_id FK added later when ResumeFile table exists.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002_tier1_persona"
down_revision: Union[str, None] = "001_tier0_user_jobsource"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personas",
        # Primary key
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Foreign keys
        sa.Column("user_id", sa.UUID(), nullable=False),
        # original_resume_file_id added in later migration after ResumeFile exists
        # Contact info
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("portfolio_url", sa.String(500), nullable=True),
        # Location
        sa.Column("home_city", sa.String(100), nullable=False),
        sa.Column("home_state", sa.String(100), nullable=False),
        sa.Column("home_country", sa.String(100), nullable=False),
        # Professional info
        sa.Column("professional_summary", sa.Text(), nullable=True),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column("current_role", sa.String(255), nullable=True),
        sa.Column("current_company", sa.String(255), nullable=True),
        # Career targets (JSONB arrays)
        sa.Column("target_roles", JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_skills", JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stretch_appetite", sa.String(20), nullable=False, server_default=sa.text("'Medium'")),
        # Compensation
        sa.Column("minimum_base_salary", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True, server_default=sa.text("'USD'")),
        # Location preferences (JSONB arrays)
        sa.Column("commutable_cities", JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("max_commute_minutes", sa.Integer(), nullable=True),
        sa.Column("remote_preference", sa.String(30), nullable=False, server_default=sa.text("'No Preference'")),
        sa.Column("relocation_open", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("relocation_cities", JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("visa_sponsorship_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        # Work preferences
        sa.Column("industry_exclusions", JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("company_size_preference", sa.String(30), nullable=True),
        sa.Column("max_travel_percent", sa.String(20), nullable=True),
        # Agent settings
        sa.Column("minimum_fit_threshold", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("polling_frequency", sa.String(20), nullable=False, server_default=sa.text("'Daily'")),
        sa.Column("auto_draft_threshold", sa.Integer(), nullable=False, server_default=sa.text("90")),
        # Onboarding state
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("onboarding_step", sa.String(50), nullable=True),
        # Timestamps
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
        # Foreign key constraints
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # Check constraints
        sa.CheckConstraint(
            "stretch_appetite IN ('Low', 'Medium', 'High')",
            name="ck_personas_stretch_appetite",
        ),
        sa.CheckConstraint(
            "remote_preference IN ('Remote Only', 'Hybrid OK', 'Onsite OK', 'No Preference')",
            name="ck_personas_remote_preference",
        ),
        sa.CheckConstraint(
            "company_size_preference IN ('Startup', 'Mid-size', 'Enterprise', 'No Preference') OR company_size_preference IS NULL",
            name="ck_personas_company_size",
        ),
        sa.CheckConstraint(
            "max_travel_percent IN ('None', '<25%', '<50%', 'Any') OR max_travel_percent IS NULL",
            name="ck_personas_max_travel",
        ),
        sa.CheckConstraint(
            "minimum_fit_threshold >= 0 AND minimum_fit_threshold <= 100",
            name="ck_personas_fit_threshold",
        ),
        sa.CheckConstraint(
            "polling_frequency IN ('Daily', 'Twice Daily', 'Weekly', 'Manual Only')",
            name="ck_personas_polling_frequency",
        ),
        sa.CheckConstraint(
            "auto_draft_threshold >= 0 AND auto_draft_threshold <= 100",
            name="ck_personas_auto_draft_threshold",
        ),
    )

    # Indexes
    op.create_index("idx_persona_user", "personas", ["user_id"])
    op.create_index("idx_persona_email", "personas", ["email"])


def downgrade() -> None:
    op.drop_index("idx_persona_email")
    op.drop_index("idx_persona_user")
    op.drop_table("personas")

"""Create Tier 3 tables: Deeper FK dependencies.

Revision ID: 004_tier3_deeper_fk
Revises: 003_tier2_persona_children
Create Date: 2026-01-26

REQ-005 §4.1 Bullet (references WorkHistory)
REQ-005 §4.2 JobVariant (references BaseResume, JobPosting)
REQ-005 §4.3 CoverLetter (references Persona, JobPosting)
REQ-005 §4.4 ExtractedSkill (references JobPosting)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004_tier3_deeper_fk"
down_revision: Union[str, None] = "003_tier2_persona_children"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # PERSONA DOMAIN (REQ-005 §4.1) - Bullet
    # =========================================================================

    op.create_table(
        "bullets",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("work_history_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("skills_demonstrated", JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metrics", sa.String(255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["work_history_id"], ["work_histories.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_bullet_workhistory", "bullets", ["work_history_id"])
    op.create_index("idx_bullet_order", "bullets", ["work_history_id", "display_order"])

    # =========================================================================
    # RESUME DOMAIN (REQ-005 §4.2) - JobVariant
    # =========================================================================

    op.create_table(
        "job_variants",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("base_resume_id", sa.UUID(), nullable=False),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("job_bullet_order", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("modifications_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'Draft'")),
        # Snapshots populated on approval
        sa.Column("snapshot_included_jobs", JSONB(), nullable=True),
        sa.Column("snapshot_job_bullet_selections", JSONB(), nullable=True),
        sa.Column("snapshot_included_education", JSONB(), nullable=True),
        sa.Column("snapshot_included_certifications", JSONB(), nullable=True),
        sa.Column("snapshot_skills_emphasis", JSONB(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # Foreign keys - RESTRICT prevents accidental deletion
        sa.ForeignKeyConstraint(["base_resume_id"], ["base_resumes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="RESTRICT"),
        # Check constraints
        sa.CheckConstraint("status IN ('Draft', 'Approved', 'Archived')", name="ck_jobvariant_status"),
    )
    op.create_index("idx_jobvariant_baseresume", "job_variants", ["base_resume_id"])
    op.create_index("idx_jobvariant_jobposting", "job_variants", ["job_posting_id"])
    op.create_index("idx_jobvariant_status", "job_variants", ["status"])

    # =========================================================================
    # COVER LETTER DOMAIN (REQ-005 §4.3)
    # =========================================================================

    op.create_table(
        "cover_letters",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),  # Linked when Application created
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("achievement_stories_used", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'Draft'")),
        sa.Column("agent_reasoning", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # Foreign keys
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        # application_id FK added later when Application table exists
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="RESTRICT"),
        # Check constraints
        sa.CheckConstraint("status IN ('Draft', 'Approved', 'Archived')", name="ck_coverletter_status"),
    )
    op.create_index("idx_coverletter_persona", "cover_letters", ["persona_id"])
    op.create_index("idx_coverletter_application", "cover_letters", ["application_id"])
    op.create_index("idx_coverletter_jobposting", "cover_letters", ["job_posting_id"])

    # =========================================================================
    # JOB POSTING DOMAIN (REQ-005 §4.4) - ExtractedSkill
    # =========================================================================

    op.create_table(
        "extracted_skills",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("skill_type", sa.String(20), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("years_requested", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.CheckConstraint("skill_type IN ('Hard', 'Soft')", name="ck_extractedskill_type"),
    )
    op.create_index("idx_extractedskill_jobposting", "extracted_skills", ["job_posting_id"])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index("idx_extractedskill_jobposting")
    op.drop_table("extracted_skills")

    op.drop_index("idx_coverletter_jobposting")
    op.drop_index("idx_coverletter_application")
    op.drop_index("idx_coverletter_persona")
    op.drop_table("cover_letters")

    op.drop_index("idx_jobvariant_status")
    op.drop_index("idx_jobvariant_jobposting")
    op.drop_index("idx_jobvariant_baseresume")
    op.drop_table("job_variants")

    op.drop_index("idx_bullet_order")
    op.drop_index("idx_bullet_workhistory")
    op.drop_table("bullets")

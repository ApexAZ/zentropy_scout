"""Create Tier 2 tables: Persona children and Job Posting domain.

Revision ID: 003_tier2_persona_children
Revises: 002_tier1_persona
Create Date: 2026-01-26

REQ-005 §4.1 Persona Domain: WorkHistory, Skill, Education, Certification,
    AchievementStory, VoiceProfile, CustomNonNegotiable, PersonaEmbedding
REQ-005 §4.2 Resume Domain: ResumeFile, BaseResume, PersonaChangeFlag
REQ-005 §4.4 Job Posting Domain: UserSourcePreference, PollingConfiguration, JobPosting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003_tier2_persona_children"
down_revision: str | None = "002_tier1_persona"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # PERSONA DOMAIN (REQ-005 §4.1)
    # =========================================================================

    # WorkHistory
    op.create_table(
        "work_histories",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("company_industry", sa.String(100), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("work_model", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "work_model IN ('Remote', 'Hybrid', 'Onsite')",
            name="ck_workhistory_work_model",
        ),
    )
    op.create_index("idx_workhistory_persona", "work_histories", ["persona_id"])
    op.create_index(
        "idx_workhistory_order", "work_histories", ["persona_id", "display_order"]
    )

    # Skill
    op.create_table(
        "skills",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("skill_type", sa.String(20), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("proficiency", sa.String(20), nullable=False),
        sa.Column("years_used", sa.Integer(), nullable=False),
        sa.Column("last_used", sa.String(20), nullable=False),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint("skill_type IN ('Hard', 'Soft')", name="ck_skill_type"),
        sa.CheckConstraint(
            "proficiency IN ('Learning', 'Familiar', 'Proficient', 'Expert')",
            name="ck_skill_proficiency",
        ),
    )
    op.create_index("idx_skill_persona", "skills", ["persona_id"])
    op.create_index(
        "idx_skill_name", "skills", ["persona_id", "skill_name"], unique=True
    )

    # Education
    op.create_table(
        "educations",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("institution", sa.String(255), nullable=False),
        sa.Column("degree", sa.String(100), nullable=False),
        sa.Column("field_of_study", sa.String(255), nullable=False),
        sa.Column("graduation_year", sa.Integer(), nullable=False),
        sa.Column("gpa", sa.Numeric(3, 2), nullable=True),
        sa.Column("honors", sa.String(255), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_education_persona", "educations", ["persona_id"])

    # Certification
    op.create_table(
        "certifications",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("certification_name", sa.String(255), nullable=False),
        sa.Column("issuing_organization", sa.String(255), nullable=False),
        sa.Column("date_obtained", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("credential_id", sa.String(100), nullable=True),
        sa.Column("verification_url", sa.String(500), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_certification_persona", "certifications", ["persona_id"])

    # AchievementStory
    op.create_table(
        "achievement_stories",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column(
            "skills_demonstrated",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("related_job_id", sa.UUID(), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["related_job_id"], ["work_histories.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "idx_achievementstory_persona", "achievement_stories", ["persona_id"]
    )

    # VoiceProfile
    op.create_table(
        "voice_profiles",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("tone", sa.Text(), nullable=False),
        sa.Column("sentence_style", sa.Text(), nullable=False),
        sa.Column("vocabulary_level", sa.Text(), nullable=False),
        sa.Column("personality_markers", sa.Text(), nullable=True),
        sa.Column(
            "sample_phrases",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "things_to_avoid",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("writing_sample_text", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_voiceprofile_persona", "voice_profiles", ["persona_id"], unique=True
    )

    # CustomNonNegotiable
    op.create_table(
        "custom_non_negotiables",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("filter_name", sa.String(255), nullable=False),
        sa.Column("filter_type", sa.String(20), nullable=False),
        sa.Column("filter_value", sa.Text(), nullable=False),
        sa.Column("filter_field", sa.String(100), nullable=False),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "filter_type IN ('Exclude', 'Require')",
            name="ck_custom_non_negotiable_type",
        ),
    )
    op.create_index(
        "idx_customnonneg_persona", "custom_non_negotiables", ["persona_id"]
    )

    # PersonaEmbedding (with pgvector)
    op.create_table(
        "persona_embeddings",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("embedding_type", sa.String(20), nullable=False),
        sa.Column("vector", Vector(1536), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "embedding_type IN ('hard_skills', 'soft_skills', 'logistics')",
            name="ck_personaembedding_type",
        ),
    )
    op.create_index(
        "idx_personaembedding_persona", "persona_embeddings", ["persona_id"]
    )
    op.create_index(
        "idx_personaembedding_type",
        "persona_embeddings",
        ["persona_id", "embedding_type"],
    )
    # IVFFlat index for vector similarity - requires data to build properly
    # Created separately with op.execute for proper ivfflat syntax
    op.execute(
        """
        CREATE INDEX idx_personaembedding_vector
        ON persona_embeddings
        USING ivfflat (vector vector_cosine_ops)
        WITH (lists = 100)
    """
    )

    # =========================================================================
    # RESUME DOMAIN (REQ-005 §4.2)
    # =========================================================================

    # ResumeFile
    op.create_table(
        "resume_files",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_binary", sa.LargeBinary(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint("file_type IN ('PDF', 'DOCX')", name="ck_resumefile_type"),
    )
    op.create_index("idx_resumefile_persona", "resume_files", ["persona_id"])
    op.create_index(
        "idx_resumefile_active",
        "resume_files",
        ["persona_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # Add original_resume_file_id FK to personas now that ResumeFile exists
    op.add_column(
        "personas", sa.Column("original_resume_file_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_persona_resume_file",
        "personas",
        "resume_files",
        ["original_resume_file_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # BaseResume
    op.create_table(
        "base_resumes",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("role_type", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "included_jobs",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "job_bullet_selections",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "job_bullet_order",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "included_education",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "included_certifications",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "skills_emphasis",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("rendered_document", sa.LargeBinary(), nullable=True),
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'Active'")
        ),
        sa.Column(
            "display_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('Active', 'Archived')", name="ck_baseresume_status"
        ),
        sa.UniqueConstraint("persona_id", "name", name="uq_baseresume_persona_name"),
    )
    op.create_index("idx_baseresume_persona", "base_resumes", ["persona_id"])
    op.create_index(
        "idx_baseresume_primary",
        "base_resumes",
        ["persona_id"],
        postgresql_where=sa.text("is_primary = true"),
    )

    # PersonaChangeFlag
    op.create_table(
        "persona_change_flags",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("item_description", sa.String(500), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'Pending'")
        ),
        sa.Column("resolution", sa.String(30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "change_type IN ('job_added', 'bullet_added', 'skill_added', 'education_added', 'certification_added')",
            name="ck_personachangeflag_change_type",
        ),
        sa.CheckConstraint(
            "status IN ('Pending', 'Resolved')", name="ck_personachangeflag_status"
        ),
        sa.CheckConstraint(
            "resolution IN ('added_to_all', 'added_to_some', 'skipped') OR resolution IS NULL",
            name="ck_personachangeflag_resolution",
        ),
    )
    op.create_index(
        "idx_personachangeflag_persona", "persona_change_flags", ["persona_id"]
    )
    op.create_index(
        "idx_personachangeflag_status",
        "persona_change_flags",
        ["persona_id", "status"],
        postgresql_where=sa.text("status = 'Pending'"),
    )

    # =========================================================================
    # JOB POSTING DOMAIN (REQ-005 §4.4)
    # =========================================================================

    # UserSourcePreference
    op.create_table(
        "user_source_preferences",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("display_order", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "persona_id", "source_id", name="uq_usersourcepref_persona_source"
        ),
    )
    op.create_index(
        "idx_usersourcepref_persona", "user_source_preferences", ["persona_id"]
    )

    # PollingConfiguration
    op.create_table(
        "polling_configurations",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_pollingconfig_persona",
        "polling_configurations",
        ["persona_id"],
        unique=True,
    )
    op.create_index(
        "idx_pollingconfig_nextpoll",
        "polling_configurations",
        ["next_poll_at"],
        postgresql_where=sa.text("next_poll_at IS NOT NULL"),
    )

    # JobPosting
    op.create_table(
        "job_postings",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column(
            "also_found_on",
            JSONB(),
            nullable=True,
            server_default=sa.text("'{\"sources\":[]}'::jsonb"),
        ),
        # Job details
        sa.Column("job_title", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("company_url", sa.String(500), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("work_model", sa.String(20), nullable=True),
        sa.Column("seniority_level", sa.String(20), nullable=True),
        # Compensation
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True),
        # Content
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("culture_text", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("years_experience_min", sa.Integer(), nullable=True),
        sa.Column("years_experience_max", sa.Integer(), nullable=True),
        # Dates
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        # URLs
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("apply_url", sa.String(1000), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        # Status and scoring
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'Discovered'"),
        ),
        sa.Column(
            "is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("stretch_score", sa.Integer(), nullable=True),
        sa.Column("failed_non_negotiables", JSONB(), nullable=True),
        # Deduplication
        sa.Column("description_hash", sa.String(64), nullable=False),
        sa.Column(
            "repost_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "previous_posting_ids",
            JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Ghost detection
        sa.Column(
            "ghost_score", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("ghost_signals", JSONB(), nullable=True),
        # Tracking dates
        sa.Column("first_seen_date", sa.Date(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        # Foreign keys
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="RESTRICT"),
        # Check constraints
        sa.CheckConstraint(
            "work_model IN ('Remote', 'Hybrid', 'Onsite') OR work_model IS NULL",
            name="ck_jobposting_work_model",
        ),
        sa.CheckConstraint(
            "seniority_level IN ('Entry', 'Mid', 'Senior', 'Lead', 'Executive') OR seniority_level IS NULL",
            name="ck_jobposting_seniority",
        ),
        sa.CheckConstraint(
            "status IN ('Discovered', 'Dismissed', 'Applied', 'Expired')",
            name="ck_jobposting_status",
        ),
        sa.CheckConstraint(
            "fit_score >= 0 AND fit_score <= 100 OR fit_score IS NULL",
            name="ck_jobposting_fit_score",
        ),
        sa.CheckConstraint(
            "stretch_score >= 0 AND stretch_score <= 100 OR stretch_score IS NULL",
            name="ck_jobposting_stretch_score",
        ),
        sa.CheckConstraint(
            "ghost_score >= 0 AND ghost_score <= 100", name="ck_jobposting_ghost_score"
        ),
    )
    op.create_index("idx_jobposting_persona", "job_postings", ["persona_id"])
    op.create_index("idx_jobposting_status", "job_postings", ["persona_id", "status"])
    op.create_index("idx_jobposting_source", "job_postings", ["source_id"])
    op.create_index(
        "idx_jobposting_external", "job_postings", ["source_id", "external_id"]
    )
    op.create_index("idx_jobposting_hash", "job_postings", ["description_hash"])
    op.create_index("idx_jobposting_company", "job_postings", ["company_name"])
    op.create_index(
        "idx_jobposting_fitscore",
        "job_postings",
        ["persona_id", sa.text("fit_score DESC")],
        postgresql_where=sa.text("status = 'Discovered'"),
    )


def downgrade() -> None:
    # Drop in reverse order of creation
    # Job Posting Domain
    op.drop_index("idx_jobposting_fitscore")
    op.drop_index("idx_jobposting_company")
    op.drop_index("idx_jobposting_hash")
    op.drop_index("idx_jobposting_external")
    op.drop_index("idx_jobposting_source")
    op.drop_index("idx_jobposting_status")
    op.drop_index("idx_jobposting_persona")
    op.drop_table("job_postings")

    op.drop_index("idx_pollingconfig_nextpoll")
    op.drop_index("idx_pollingconfig_persona")
    op.drop_table("polling_configurations")

    op.drop_index("idx_usersourcepref_persona")
    op.drop_table("user_source_preferences")

    # Resume Domain
    op.drop_index("idx_personachangeflag_status")
    op.drop_index("idx_personachangeflag_persona")
    op.drop_table("persona_change_flags")

    op.drop_index("idx_baseresume_primary")
    op.drop_index("idx_baseresume_persona")
    op.drop_table("base_resumes")

    # Remove FK from personas before dropping resume_files
    op.drop_constraint("fk_persona_resume_file", "personas", type_="foreignkey")
    op.drop_column("personas", "original_resume_file_id")

    op.drop_index("idx_resumefile_active")
    op.drop_index("idx_resumefile_persona")
    op.drop_table("resume_files")

    # Persona Domain (reverse order)
    op.drop_index("idx_personaembedding_vector", "persona_embeddings")
    op.drop_index("idx_personaembedding_type")
    op.drop_index("idx_personaembedding_persona")
    op.drop_table("persona_embeddings")

    op.drop_index("idx_customnonneg_persona")
    op.drop_table("custom_non_negotiables")

    op.drop_index("idx_voiceprofile_persona")
    op.drop_table("voice_profiles")

    op.drop_index("idx_achievementstory_persona")
    op.drop_table("achievement_stories")

    op.drop_index("idx_certification_persona")
    op.drop_table("certifications")

    op.drop_index("idx_education_persona")
    op.drop_table("educations")

    op.drop_index("idx_skill_name")
    op.drop_index("idx_skill_persona")
    op.drop_table("skills")

    op.drop_index("idx_workhistory_order")
    op.drop_index("idx_workhistory_persona")
    op.drop_table("work_histories")

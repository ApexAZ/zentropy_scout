"""Rename all indexes to explicit idx_{table}_{column} convention.

Revision ID: 011_rename_indexes
Revises: 010_auth_tables
Create Date: 2026-02-20

REQ-014 §8.1: Standardize index naming for AI-searchable codebase.

Renames 49 indexes from abbreviated convention (e.g. idx_persona_user)
to explicit convention (e.g. idx_personas_user_id) where the table name
and column name(s) are fully spelled out. This makes indexes discoverable
via grep/search by table name or column name.

The 4 indexes from migration 010 (auth tables) already follow the
explicit convention and are not touched.

All renames use ALTER INDEX RENAME which is metadata-only — no table
locks, no data movement, no reindexing.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "011_rename_indexes"
down_revision: str | None = "010_auth_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (old_name, new_name) — grouped by origin migration for traceability.
_RENAMES: list[tuple[str, str]] = [
    # Migration 001: users, job_sources
    ("idx_user_email", "idx_users_email"),
    ("idx_jobsource_name", "idx_job_sources_source_name"),
    # Migration 002: personas
    ("idx_persona_user", "idx_personas_user_id"),
    ("idx_persona_email", "idx_personas_email"),
    # Migration 003: work_histories
    ("idx_workhistory_persona", "idx_work_histories_persona_id"),
    ("idx_workhistory_order", "idx_work_histories_persona_id_display_order"),
    # Migration 003: skills
    ("idx_skill_persona", "idx_skills_persona_id"),
    ("idx_skill_name", "idx_skills_persona_id_skill_name"),
    # Migration 003: educations
    ("idx_education_persona", "idx_educations_persona_id"),
    # Migration 003: certifications
    ("idx_certification_persona", "idx_certifications_persona_id"),
    # Migration 003: achievement_stories
    ("idx_achievementstory_persona", "idx_achievement_stories_persona_id"),
    # Migration 003: voice_profiles
    ("idx_voiceprofile_persona", "idx_voice_profiles_persona_id"),
    # Migration 003: custom_non_negotiables
    ("idx_customnonneg_persona", "idx_custom_non_negotiables_persona_id"),
    # Migration 003: persona_embeddings
    ("idx_personaembedding_persona", "idx_persona_embeddings_persona_id"),
    ("idx_personaembedding_type", "idx_persona_embeddings_persona_id_embedding_type"),
    ("idx_personaembedding_vector", "idx_persona_embeddings_vector"),
    # Migration 003: resume_files
    ("idx_resumefile_persona", "idx_resume_files_persona_id"),
    ("idx_resumefile_active", "idx_resume_files_persona_id_is_active"),
    # Migration 003: base_resumes
    ("idx_baseresume_persona", "idx_base_resumes_persona_id"),
    ("idx_baseresume_primary", "idx_base_resumes_persona_id_is_primary"),
    # Migration 003: persona_change_flags
    ("idx_personachangeflag_persona", "idx_persona_change_flags_persona_id"),
    ("idx_personachangeflag_status", "idx_persona_change_flags_persona_id_status"),
    # Migration 003: user_source_preferences
    ("idx_usersourcepref_persona", "idx_user_source_preferences_persona_id"),
    # Migration 003: polling_configurations
    ("idx_pollingconfig_persona", "idx_polling_configurations_persona_id"),
    ("idx_pollingconfig_nextpoll", "idx_polling_configurations_next_poll_at"),
    # Migration 003: job_postings
    ("idx_jobposting_persona", "idx_job_postings_persona_id"),
    ("idx_jobposting_status", "idx_job_postings_persona_id_status"),
    ("idx_jobposting_source", "idx_job_postings_source_id"),
    ("idx_jobposting_external", "idx_job_postings_source_id_external_id"),
    ("idx_jobposting_hash", "idx_job_postings_description_hash"),
    ("idx_jobposting_company", "idx_job_postings_company_name"),
    ("idx_jobposting_fitscore", "idx_job_postings_persona_id_fit_score"),
    # Migration 004: bullets
    ("idx_bullet_workhistory", "idx_bullets_work_history_id"),
    ("idx_bullet_order", "idx_bullets_work_history_id_display_order"),
    # Migration 004: job_variants
    ("idx_jobvariant_baseresume", "idx_job_variants_base_resume_id"),
    ("idx_jobvariant_jobposting", "idx_job_variants_job_posting_id"),
    ("idx_jobvariant_status", "idx_job_variants_status"),
    # Migration 004: cover_letters
    ("idx_coverletter_persona", "idx_cover_letters_persona_id"),
    ("idx_coverletter_application", "idx_cover_letters_application_id"),
    ("idx_coverletter_jobposting", "idx_cover_letters_job_posting_id"),
    # Migration 004: extracted_skills
    ("idx_extractedskill_jobposting", "idx_extracted_skills_job_posting_id"),
    # Migration 005: applications
    ("idx_application_persona", "idx_applications_persona_id"),
    ("idx_application_jobposting", "idx_applications_job_posting_id"),
    ("idx_application_status", "idx_applications_persona_id_status"),
    # Migration 005: submitted_resume_pdfs
    ("idx_submittedresumepdf_application", "idx_submitted_resume_pdfs_application_id"),
    # Migration 005: submitted_cover_letter_pdfs
    (
        "idx_submittedcoverletterpdf_application",
        "idx_submitted_cover_letter_pdfs_application_id",
    ),
    (
        "idx_submittedcoverletterpdf_coverletter",
        "idx_submitted_cover_letter_pdfs_cover_letter_id",
    ),
    # Migration 006: timeline_events
    ("idx_timelineevent_application", "idx_timeline_events_application_id"),
    ("idx_timelineevent_date", "idx_timeline_events_application_id_event_date"),
]


def upgrade() -> None:
    for old_name, new_name in _RENAMES:
        op.execute(f"ALTER INDEX {old_name} RENAME TO {new_name}")


def downgrade() -> None:
    for old_name, new_name in reversed(_RENAMES):
        op.execute(f"ALTER INDEX {new_name} RENAME TO {old_name}")

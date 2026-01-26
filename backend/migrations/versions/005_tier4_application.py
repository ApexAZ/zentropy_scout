"""Create Tier 4 tables: Application and Submitted PDFs.

Revision ID: 005_tier4_application
Revises: 004_tier3_deeper_fk
Create Date: 2026-01-26

REQ-005 §4.5 Application Domain
REQ-005 §4.2 SubmittedResumePDF
REQ-005 §4.3 SubmittedCoverLetterPDF

Note: Application and SubmittedResumePDF have bidirectional FKs.
Both FKs are nullable. Create Application first, then link PDFs.
REQ-005 §9.2 explains this circular reference resolution.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005_tier4_application"
down_revision: Union[str, None] = "004_tier3_deeper_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # APPLICATION DOMAIN (REQ-005 §4.5)
    # =========================================================================

    op.create_table(
        "applications",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("job_variant_id", sa.UUID(), nullable=False),
        sa.Column("cover_letter_id", sa.UUID(), nullable=True),
        # PDF links added after PDF tables exist (nullable for bidirectional FK)
        sa.Column("submitted_resume_pdf_id", sa.UUID(), nullable=True),
        sa.Column("submitted_cover_letter_pdf_id", sa.UUID(), nullable=True),
        # Job snapshot - frozen copy at application time
        sa.Column("job_snapshot", JSONB(), nullable=False),
        # Status tracking
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'Applied'")),
        sa.Column("current_interview_stage", sa.String(30), nullable=True),
        # Outcome details
        sa.Column("offer_details", JSONB(), nullable=True),
        sa.Column("rejection_details", JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Foreign keys
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_postings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_variant_id"], ["job_variants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cover_letter_id"], ["cover_letters.id"], ondelete="SET NULL"),
        # Check constraints
        sa.CheckConstraint(
            "status IN ('Applied', 'Interviewing', 'Offer', 'Accepted', 'Rejected', 'Withdrawn')",
            name="ck_application_status",
        ),
        sa.CheckConstraint(
            "current_interview_stage IN ('Phone Screen', 'Onsite', 'Final Round') OR current_interview_stage IS NULL",
            name="ck_application_interview_stage",
        ),
        # Unique constraint - one application per job per persona
        sa.UniqueConstraint("persona_id", "job_posting_id", name="uq_application_persona_job"),
    )
    op.create_index("idx_application_persona", "applications", ["persona_id"])
    op.create_index("idx_application_jobposting", "applications", ["job_posting_id"])
    op.create_index("idx_application_status", "applications", ["persona_id", "status"])

    # Add application_id FK to cover_letters now that Application exists
    op.create_foreign_key(
        "fk_coverletter_application",
        "cover_letters",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # =========================================================================
    # RESUME DOMAIN (REQ-005 §4.2) - SubmittedResumePDF
    # =========================================================================

    op.create_table(
        "submitted_resume_pdfs",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", sa.UUID(), nullable=True),  # NULL until user marks "Applied"
        sa.Column("resume_source_type", sa.String(20), nullable=False),
        sa.Column("resume_source_id", sa.UUID(), nullable=False),  # App-enforced FK to Base or Variant
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_binary", sa.LargeBinary(), nullable=False),  # BYTEA - actual PDF
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Foreign keys
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        # Check constraints
        sa.CheckConstraint("resume_source_type IN ('Base', 'Variant')", name="ck_submittedresumepdf_source_type"),
    )
    op.create_index("idx_submittedresumepdf_application", "submitted_resume_pdfs", ["application_id"])

    # Add FK from Application to SubmittedResumePDF (bidirectional)
    op.create_foreign_key(
        "fk_application_submitted_resume",
        "applications",
        "submitted_resume_pdfs",
        ["submitted_resume_pdf_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # =========================================================================
    # COVER LETTER DOMAIN (REQ-005 §4.3) - SubmittedCoverLetterPDF
    # =========================================================================

    op.create_table(
        "submitted_cover_letter_pdfs",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cover_letter_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),  # NULL until user marks "Applied"
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_binary", sa.LargeBinary(), nullable=False),  # BYTEA - actual PDF
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Foreign keys
        sa.ForeignKeyConstraint(["cover_letter_id"], ["cover_letters.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_submittedcoverletterpdf_application", "submitted_cover_letter_pdfs", ["application_id"])
    op.create_index("idx_submittedcoverletterpdf_coverletter", "submitted_cover_letter_pdfs", ["cover_letter_id"])

    # Add FK from Application to SubmittedCoverLetterPDF
    op.create_foreign_key(
        "fk_application_submitted_coverletter",
        "applications",
        "submitted_cover_letter_pdfs",
        ["submitted_cover_letter_pdf_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FKs from Application first
    op.drop_constraint("fk_application_submitted_coverletter", "applications", type_="foreignkey")
    op.drop_constraint("fk_application_submitted_resume", "applications", type_="foreignkey")

    # Drop SubmittedCoverLetterPDF
    op.drop_index("idx_submittedcoverletterpdf_coverletter")
    op.drop_index("idx_submittedcoverletterpdf_application")
    op.drop_table("submitted_cover_letter_pdfs")

    # Drop SubmittedResumePDF
    op.drop_index("idx_submittedresumepdf_application")
    op.drop_table("submitted_resume_pdfs")

    # Drop FK from cover_letters to applications
    op.drop_constraint("fk_coverletter_application", "cover_letters", type_="foreignkey")

    # Drop Application
    op.drop_index("idx_application_status")
    op.drop_index("idx_application_jobposting")
    op.drop_index("idx_application_persona")
    op.drop_table("applications")

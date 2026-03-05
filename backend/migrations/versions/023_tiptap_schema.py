"""Add markdown content columns and resume_templates table.

Revision ID: 023_tiptap_schema
Revises: 022_usd_direct_billing
Create Date: 2026-03-05

REQ-025 §4: Adds markdown_content and template_id to base_resumes,
markdown_content and snapshot_markdown_content to job_variants,
creates resume_templates table with seed data.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_tiptap_schema"
down_revision: str = "022_usd_direct_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")

# Clean & Minimal template content (REQ-025 §6.1)
_CLEAN_MINIMAL_TEMPLATE = """\
# {full_name}

{email} | {phone} | {location} | {linkedin_url}

---

## Professional Summary

{summary}

---

## Experience

### {job_title} — {company_name}
*{start_date} – {end_date}*

- {bullet_1}
- {bullet_2}

---

## Education

### {degree} — {institution}
*{graduation_date}*

---

## Skills

{skills_list}

---

## Certifications

- {certification_1}
- {certification_2}
"""


def upgrade() -> None:
    # 1. Create resume_templates table (must exist before FK on base_resumes)
    op.create_table(
        "resume_templates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=_UUID_DEFAULT,
            primary_key=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 2. Add markdown columns + template FK to base_resumes
    op.add_column(
        "base_resumes",
        sa.Column("markdown_content", sa.Text(), nullable=True),
    )
    op.add_column(
        "base_resumes",
        sa.Column(
            "template_id",
            sa.UUID(),
            sa.ForeignKey("resume_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. Add markdown columns to job_variants
    op.add_column(
        "job_variants",
        sa.Column("markdown_content", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_variants",
        sa.Column("snapshot_markdown_content", sa.Text(), nullable=True),
    )

    # 4. Seed default system template
    op.execute(
        sa.text(
            "INSERT INTO resume_templates "
            "(name, description, markdown_content, is_system, display_order) "
            "VALUES (:name, :description, :content, true, 1)"
        ).bindparams(
            name="Clean & Minimal",
            description="A clean, professional resume layout with clear section separators",
            content=_CLEAN_MINIMAL_TEMPLATE,
        )
    )


def downgrade() -> None:
    # 1. Remove seed data
    op.execute(
        sa.text(
            "DELETE FROM resume_templates WHERE name = :name AND is_system = true"
        ).bindparams(name="Clean & Minimal")
    )

    # 2. Drop job_variants columns
    op.drop_column("job_variants", "snapshot_markdown_content")
    op.drop_column("job_variants", "markdown_content")

    # 3. Drop base_resumes columns (FK first)
    op.drop_column("base_resumes", "template_id")
    op.drop_column("base_resumes", "markdown_content")

    # 4. Drop resume_templates table
    op.drop_table("resume_templates")

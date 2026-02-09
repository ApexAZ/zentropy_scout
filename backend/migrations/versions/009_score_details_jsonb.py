"""Add score_details JSONB column to job_postings table.

Revision ID: 009_score_details_jsonb
Revises: 008_application_pin_archive
Create Date: 2026-02-08

REQ-012 Appendix A.3: FitScoreResult, StretchScoreResult, and
ScoreExplanation are computed by the service layer but only aggregate
scores (fit_score, stretch_score integers) are persisted. This column
stores the full component breakdown for the frontend score drill-down.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009_score_details_jsonb"
down_revision: str | None = "008_application_pin_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_postings",
        sa.Column(
            "score_details",
            JSONB,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("job_postings", "score_details")

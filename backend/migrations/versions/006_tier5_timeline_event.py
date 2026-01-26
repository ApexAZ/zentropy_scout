"""Create Tier 5 table: TimelineEvent.

Revision ID: 006_tier5_timeline_event
Revises: 005_tier4_application
Create Date: 2026-01-26

REQ-005 §4.5 Application Domain - TimelineEvent table
Final tier in the dependency chain.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_tier5_timeline_event"
down_revision: Union[str, None] = "005_tier4_application"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("interview_stage", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Foreign keys
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        # Check constraints
        sa.CheckConstraint(
            "event_type IN ('applied', 'status_changed', 'note_added', 'interview_scheduled', "
            "'interview_completed', 'offer_received', 'offer_accepted', 'rejected', 'withdrawn', "
            "'follow_up_sent', 'response_received', 'custom')",
            name="ck_timelineevent_event_type",
        ),
        sa.CheckConstraint(
            "interview_stage IN ('Phone Screen', 'Onsite', 'Final Round') OR interview_stage IS NULL",
            name="ck_timelineevent_interview_stage",
        ),
    )
    op.create_index("idx_timelineevent_application", "timeline_events", ["application_id"])
    op.create_index("idx_timelineevent_date", "timeline_events", ["application_id", sa.text("event_date DESC")])


def downgrade() -> None:
    op.drop_index("idx_timelineevent_date")
    op.drop_index("idx_timelineevent_application")
    op.drop_table("timeline_events")

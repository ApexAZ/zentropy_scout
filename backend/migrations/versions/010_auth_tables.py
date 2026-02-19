"""Add auth tables: expand users, create accounts, sessions, verification_tokens.

Revision ID: 010_auth_tables
Revises: 009_score_details_jsonb
Create Date: 2026-02-19

REQ-013 §6: Authentication schema changes.
- §6.1: Expand users table with name, email_verified, image, updated_at,
         password_hash, token_invalidated_before columns.
- §6.2: Create accounts table for OAuth provider connections.
- §6.3: Create sessions table for active session tracking.
- §6.4: Create verification_tokens table for magic link tokens.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "010_auth_tables"
down_revision: str | None = "009_score_details_jsonb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # §6.1: Expand users table
    # =========================================================================
    op.add_column("users", sa.Column("name", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verified", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("image", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "token_invalidated_before", sa.DateTime(timezone=True), nullable=True
        ),
    )

    # Existing user gets email_verified = now() (trusted in local mode)
    op.execute("UPDATE users SET email_verified = now() WHERE email_verified IS NULL")

    # =========================================================================
    # §6.2: Create accounts table
    # =========================================================================
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        # OAuth tokens: encrypted at application layer (Phase 1 §3)
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("token_type", sa.String(50), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=True),
        sa.Column("session_state", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "provider_account_id", name="uq_accounts_provider_account"
        ),
    )
    op.create_index("idx_accounts_user_id", "accounts", ["user_id"])

    # =========================================================================
    # §6.3: Create sessions table
    # =========================================================================
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("session_token", sa.String(255), unique=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_expires", "sessions", ["expires"])

    # =========================================================================
    # §6.4: Create verification_tokens table (composite PK, no UUID id)
    # =========================================================================
    op.create_table(
        "verification_tokens",
        sa.Column("identifier", sa.String(255), nullable=False),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("identifier", "token", name="pk_verification_tokens"),
    )
    op.create_index(
        "idx_verification_tokens_expires", "verification_tokens", ["expires"]
    )


def downgrade() -> None:
    # Drop new tables (reverse order of creation)
    op.drop_index("idx_verification_tokens_expires", table_name="verification_tokens")
    op.drop_table("verification_tokens")

    op.drop_index("idx_sessions_expires", table_name="sessions")
    op.drop_index("idx_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("idx_accounts_user_id", table_name="accounts")
    op.drop_table("accounts")

    # Remove columns from users (reverse order of addition)
    op.drop_column("users", "token_invalidated_before")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "image")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "name")

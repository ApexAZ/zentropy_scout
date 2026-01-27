"""Enable pgvector and pgcrypto extensions.

Revision ID: 000_enable_extensions
Revises:
Create Date: 2026-01-26

REQ-005 §8: Extensions Required
- pgvector: Vector similarity search for PersonaEmbedding
- pgcrypto: UUID generation via gen_random_uuid()
"""

from collections.abc import Sequence

from alembic import op

revision: str = "000_enable_extensions"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgcrypto provides gen_random_uuid() for UUID primary keys
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # pgvector provides VECTOR type for embedding similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Note: Dropping extensions will fail if tables use them
    # In production, you'd want to drop dependent tables first
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")

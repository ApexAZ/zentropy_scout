"""Create job_embeddings table and resize vector columns to 768 for Gemini.

REQ-028 §8: Create missing job_embeddings table, truncate persona_embeddings
(derived data, regenerable), alter vector columns from Vector(1536) to
Vector(768), and rebuild IVFFlat indexes. Re-embedding via standalone script.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "024_gemini_embedding_dimensions"
down_revision: str = "023_tiptap_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    # Step 1: Create job_embeddings table (model existed but was never migrated)
    op.create_table(
        "job_embeddings",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=_UUID_DEFAULT,
        ),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        sa.Column("embedding_type", sa.String(20), nullable=False),
        sa.Column("vector", Vector(768), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "embedding_type IN ('requirements', 'culture')",
            name="ck_jobembedding_type",
        ),
    )
    op.create_index("idx_jobembedding_posting", "job_embeddings", ["job_posting_id"])
    op.create_index(
        "idx_jobembedding_type",
        "job_embeddings",
        ["job_posting_id", "embedding_type"],
    )
    op.execute(
        sa.text(
            "CREATE INDEX idx_job_embeddings_vector "
            "ON job_embeddings "
            "USING ivfflat (vector vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )

    # Step 2: Truncate persona_embeddings (derived data, fully regenerable)
    op.execute(sa.text("TRUNCATE TABLE persona_embeddings"))

    # Step 3: Drop IVFFlat index (cannot ALTER column type with index present)
    op.drop_index("idx_persona_embeddings_vector", table_name="persona_embeddings")

    # Step 4: ALTER persona_embeddings vector column from 1536 to 768
    op.execute(
        sa.text("ALTER TABLE persona_embeddings ALTER COLUMN vector TYPE vector(768)")
    )

    # Step 5: Recreate IVFFlat index
    op.execute(
        sa.text(
            "CREATE INDEX idx_persona_embeddings_vector "
            "ON persona_embeddings "
            "USING ivfflat (vector vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )


def downgrade() -> None:
    # Drop job_embeddings table (was created in this migration)
    op.drop_index("idx_job_embeddings_vector", table_name="job_embeddings")
    op.drop_index("idx_jobembedding_type", table_name="job_embeddings")
    op.drop_index("idx_jobembedding_posting", table_name="job_embeddings")
    op.drop_table("job_embeddings")

    # Reverse persona_embeddings: truncate, drop index, alter back to 1536, recreate
    op.execute(sa.text("TRUNCATE TABLE persona_embeddings"))
    op.drop_index("idx_persona_embeddings_vector", table_name="persona_embeddings")

    op.execute(
        sa.text("ALTER TABLE persona_embeddings ALTER COLUMN vector TYPE vector(1536)")
    )

    op.execute(
        sa.text(
            "CREATE INDEX idx_persona_embeddings_vector "
            "ON persona_embeddings "
            "USING ivfflat (vector vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )

"""Add admin pricing dashboard and model registry tables.

Revision ID: 021_admin_pricing
Revises: 020_token_metering
Create Date: 2026-03-01

REQ-022 §4.1–§4.8, §12.1–§12.5: Creates five admin-configurable tables
(model_registry, pricing_config, task_routing_config, credit_packs,
system_config), adds is_admin column to users, and seeds all tables with
current hardcoded pricing, routing, and model data.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "021_admin_pricing"
down_revision: str = "020_token_metering"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Shared column types
# ---------------------------------------------------------------------------
_PG_UUID = sa.dialects.postgresql.UUID(as_uuid=True)
_UUID_DEFAULT = sa.text("gen_random_uuid()")
_NUMERIC_10_6 = sa.Numeric(precision=10, scale=6)
_NUMERIC_4_2 = sa.Numeric(precision=4, scale=2)
_NOW = sa.func.now()

# ---------------------------------------------------------------------------
# Seed data constants — REQ-022 §12.1–§12.5
# ---------------------------------------------------------------------------

# Provider identifiers
_CLAUDE = "claude"
_OPENAI = "openai"
_GEMINI = "gemini"

# Model identifiers
_CLAUDE_HAIKU = "claude-3-5-haiku-20241022"
_CLAUDE_SONNET = "claude-3-5-sonnet-20241022"
_GPT4O_MINI = "gpt-4o-mini"
_GPT4O = "gpt-4o"
_GEMINI_FLASH = "gemini-2.0-flash"
_GEMINI_25_FLASH = "gemini-2.5-flash"
_EMBED_SMALL = "text-embedding-3-small"
_EMBED_LARGE = "text-embedding-3-large"
_EMBED_ADA = "text-embedding-ada-002"

# §12.1 Model Registry (9 models: 6 LLM + 3 embedding)
_SEED_MODELS = [
    (_CLAUDE, _CLAUDE_HAIKU, "Claude 3.5 Haiku", "llm", True),
    (_CLAUDE, _CLAUDE_SONNET, "Claude 3.5 Sonnet", "llm", True),
    (_OPENAI, _GPT4O_MINI, "GPT-4o Mini", "llm", True),
    (_OPENAI, _GPT4O, "GPT-4o", "llm", True),
    (_GEMINI, _GEMINI_FLASH, "Gemini 2.0 Flash", "llm", True),
    (_GEMINI, _GEMINI_25_FLASH, "Gemini 2.5 Flash", "llm", True),
    (_OPENAI, _EMBED_SMALL, "Embedding 3 Small", "embedding", True),
    (_OPENAI, _EMBED_LARGE, "Embedding 3 Large", "embedding", True),
    (_OPENAI, _EMBED_ADA, "Embedding Ada 002 (Legacy)", "embedding", False),
]

# §12.2 Pricing Config (8 entries, margin 1.30, effective_date = migration date)
_SEED_PRICING = [
    # (provider, model, input_cost_per_1k, output_cost_per_1k, margin_multiplier)
    (_CLAUDE, _CLAUDE_HAIKU, 0.000800, 0.004000, 1.30),
    (_CLAUDE, _CLAUDE_SONNET, 0.003000, 0.015000, 1.30),
    (_OPENAI, _GPT4O_MINI, 0.000150, 0.000600, 1.30),
    (_OPENAI, _GPT4O, 0.002500, 0.010000, 1.30),
    (_GEMINI, _GEMINI_FLASH, 0.000100, 0.000400, 1.30),
    (_GEMINI, _GEMINI_25_FLASH, 0.000150, 0.003500, 1.30),
    (_OPENAI, _EMBED_SMALL, 0.000020, 0.000000, 1.30),
    (_OPENAI, _EMBED_LARGE, 0.000130, 0.000000, 1.30),
]

# §12.3 Task Routing Config (33 entries: 11 per provider)
_SEED_ROUTING = [
    # Claude routing
    (_CLAUDE, "skill_extraction", _CLAUDE_HAIKU),
    (_CLAUDE, "extraction", _CLAUDE_HAIKU),
    (_CLAUDE, "ghost_detection", _CLAUDE_HAIKU),
    (_CLAUDE, "resume_parsing", _CLAUDE_HAIKU),
    (_CLAUDE, "chat_response", _CLAUDE_SONNET),
    (_CLAUDE, "onboarding", _CLAUDE_SONNET),
    (_CLAUDE, "score_rationale", _CLAUDE_SONNET),
    (_CLAUDE, "cover_letter", _CLAUDE_SONNET),
    (_CLAUDE, "resume_tailoring", _CLAUDE_SONNET),
    (_CLAUDE, "story_selection", _CLAUDE_SONNET),
    (_CLAUDE, "_default", _CLAUDE_SONNET),
    # OpenAI routing
    (_OPENAI, "skill_extraction", _GPT4O_MINI),
    (_OPENAI, "extraction", _GPT4O_MINI),
    (_OPENAI, "ghost_detection", _GPT4O_MINI),
    (_OPENAI, "resume_parsing", _GPT4O_MINI),
    (_OPENAI, "chat_response", _GPT4O),
    (_OPENAI, "onboarding", _GPT4O),
    (_OPENAI, "score_rationale", _GPT4O),
    (_OPENAI, "cover_letter", _GPT4O),
    (_OPENAI, "resume_tailoring", _GPT4O),
    (_OPENAI, "story_selection", _GPT4O),
    (_OPENAI, "_default", _GPT4O),
    # Gemini routing
    (_GEMINI, "skill_extraction", _GEMINI_FLASH),
    (_GEMINI, "extraction", _GEMINI_FLASH),
    (_GEMINI, "ghost_detection", _GEMINI_FLASH),
    (_GEMINI, "chat_response", _GEMINI_FLASH),
    (_GEMINI, "onboarding", _GEMINI_FLASH),
    (_GEMINI, "score_rationale", _GEMINI_FLASH),
    (_GEMINI, "cover_letter", _GEMINI_FLASH),
    (_GEMINI, "resume_tailoring", _GEMINI_FLASH),
    (_GEMINI, "story_selection", _GEMINI_FLASH),
    (_GEMINI, "resume_parsing", _GEMINI_25_FLASH),
    (_GEMINI, "_default", _GEMINI_FLASH),
]

# §12.4 System Config
_SEED_SYSTEM_CONFIG = [
    ("signup_grant_credits", "0", "Credits granted to new users on signup"),
]

# §12.5 Credit Packs
_SEED_CREDIT_PACKS = [
    # (name, price_cents, credit_amount, display_order, is_active, description, highlight_label)
    ("Starter", 500, 50000, 1, True, "Get started with Zentropy Scout", None),
    ("Standard", 1500, 175000, 2, True, "For regular users", "Most Popular"),
    ("Pro", 4000, 500000, 3, True, "For power users", "Best Value"),
]


def upgrade() -> None:
    """Create admin pricing tables, add is_admin to users, seed data."""
    now = datetime.now(UTC)
    today = date.today()

    # 1. Add is_admin column to users table (§4.1)
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
    )

    # 2. Create model_registry table (§4.2)
    model_registry = op.create_table(
        "model_registry",
        sa.Column("id", _PG_UUID, server_default=_UUID_DEFAULT, primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("model_type", sa.String(20), server_default="llm", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "model", name="uq_model_registry_provider_model"
        ),
        sa.CheckConstraint(
            "model_type IN ('llm', 'embedding')",
            name="ck_model_registry_model_type",
        ),
    )

    # 3. Create pricing_config table (§4.3)
    pricing_config = op.create_table(
        "pricing_config",
        sa.Column("id", _PG_UUID, server_default=_UUID_DEFAULT, primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_cost_per_1k", _NUMERIC_10_6, nullable=False),
        sa.Column("output_cost_per_1k", _NUMERIC_10_6, nullable=False),
        sa.Column("margin_multiplier", _NUMERIC_4_2, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider",
            "model",
            "effective_date",
            name="uq_pricing_config_provider_model_date",
        ),
        sa.CheckConstraint(
            "margin_multiplier > 0",
            name="ck_pricing_config_margin_positive",
        ),
        sa.CheckConstraint(
            "input_cost_per_1k >= 0",
            name="ck_pricing_config_input_cost_nonneg",
        ),
        sa.CheckConstraint(
            "output_cost_per_1k >= 0",
            name="ck_pricing_config_output_cost_nonneg",
        ),
    )

    # 4. Create task_routing_config table (§4.4)
    task_routing_config = op.create_table(
        "task_routing_config",
        sa.Column("id", _PG_UUID, server_default=_UUID_DEFAULT, primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "task_type", name="uq_task_routing_config_provider_task"
        ),
    )

    # 5. Create credit_packs table (§4.5)
    credit_packs = op.create_table(
        "credit_packs",
        sa.Column("id", _PG_UUID, server_default=_UUID_DEFAULT, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("credit_amount", sa.BigInteger, nullable=False),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("display_order", sa.Integer, server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("highlight_label", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.CheckConstraint("price_cents > 0", name="ck_credit_packs_price_positive"),
        sa.CheckConstraint("credit_amount > 0", name="ck_credit_packs_amount_positive"),
    )

    # 6. Create system_config table (§4.6) — key as VARCHAR(100) PK, NOT UUID
    system_config = op.create_table(
        "system_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_NOW,
            nullable=False,
        ),
    )

    # 7. Create indexes (§4.7)
    op.create_index(
        "ix_pricing_config_lookup",
        "pricing_config",
        ["provider", "model", sa.text("effective_date DESC")],
    )
    op.create_index(
        "ix_task_routing_config_lookup",
        "task_routing_config",
        ["provider", "task_type"],
    )
    op.create_index(
        "ix_credit_packs_active",
        "credit_packs",
        ["is_active", "display_order"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    # 8. Seed model_registry (§12.1)
    op.bulk_insert(
        model_registry,
        [
            {
                "provider": provider,
                "model": model,
                "display_name": display_name,
                "model_type": model_type,
                "is_active": is_active,
                "created_at": now,
                "updated_at": now,
            }
            for provider, model, display_name, model_type, is_active in _SEED_MODELS
        ],
    )

    # 9. Seed pricing_config (§12.2)
    op.bulk_insert(
        pricing_config,
        [
            {
                "provider": provider,
                "model": model,
                "input_cost_per_1k": input_cost,
                "output_cost_per_1k": output_cost,
                "margin_multiplier": margin,
                "effective_date": today,
                "created_at": now,
                "updated_at": now,
            }
            for provider, model, input_cost, output_cost, margin in _SEED_PRICING
        ],
    )

    # 10. Seed task_routing_config (§12.3)
    op.bulk_insert(
        task_routing_config,
        [
            {
                "provider": provider,
                "task_type": task_type,
                "model": model,
                "created_at": now,
                "updated_at": now,
            }
            for provider, task_type, model in _SEED_ROUTING
        ],
    )

    # 11. Seed system_config (§12.4)
    op.bulk_insert(
        system_config,
        [
            {
                "key": key,
                "value": value,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            for key, value, description in _SEED_SYSTEM_CONFIG
        ],
    )

    # 12. Seed credit_packs (§12.5)
    op.bulk_insert(
        credit_packs,
        [
            {
                "name": name,
                "price_cents": price_cents,
                "credit_amount": credit_amount,
                "display_order": display_order,
                "is_active": is_active,
                "description": description,
                "highlight_label": highlight_label,
                "created_at": now,
                "updated_at": now,
            }
            for (
                name,
                price_cents,
                credit_amount,
                display_order,
                is_active,
                description,
                highlight_label,
            ) in _SEED_CREDIT_PACKS
        ],
    )


def downgrade() -> None:
    """Remove admin pricing tables and is_admin column."""
    # Drop indexes first
    op.drop_index("ix_credit_packs_active", table_name="credit_packs")
    op.drop_index("ix_task_routing_config_lookup", table_name="task_routing_config")
    op.drop_index("ix_pricing_config_lookup", table_name="pricing_config")

    # Drop tables (reverse order of creation)
    op.drop_table("system_config")
    op.drop_table("credit_packs")
    op.drop_table("task_routing_config")
    op.drop_table("pricing_config")
    op.drop_table("model_registry")

    # Remove is_admin column from users
    op.drop_column("users", "is_admin")

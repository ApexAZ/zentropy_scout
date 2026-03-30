"""Integration tests for REQ-023 §7.6: signup_grant_cents config key rename.

Verifies that AdminConfigService correctly reads the renamed config key
and that the old key is absent. Seeds test data to simulate post-migration
state (test DB uses create_all, not Alembic migrations).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import SystemConfig
from app.services.admin.admin_config_service import AdminConfigService

_KEY_SIGNUP_GRANT_CENTS = "signup_grant_cents"


async def _seed_signup_grant_config(db: AsyncSession) -> None:
    """Seed the post-migration signup_grant_cents config row."""
    db.add(
        SystemConfig(
            key=_KEY_SIGNUP_GRANT_CENTS,
            value="10",
            description="USD cents granted to new users on signup (0 = disabled)",
        )
    )
    await db.flush()


@pytest.mark.asyncio
class TestConfigKeyRename:
    """Config key rename integration tests (REQ-023 §7.6)."""

    async def test_signup_grant_cents_key_returns_ten(
        self, db_session: AsyncSession
    ) -> None:
        """signup_grant_cents key is readable via AdminConfigService."""
        await _seed_signup_grant_config(db_session)

        svc = AdminConfigService(db_session)
        value = await svc.get_system_config_int(_KEY_SIGNUP_GRANT_CENTS)
        assert value == 10

    async def test_signup_grant_credits_key_absent(
        self, db_session: AsyncSession
    ) -> None:
        """Old key signup_grant_credits returns default when absent."""
        await _seed_signup_grant_config(db_session)

        svc = AdminConfigService(db_session)
        value = await svc.get_system_config("signup_grant_credits")
        assert value is None

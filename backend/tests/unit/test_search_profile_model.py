"""Tests for SearchProfile SQLAlchemy model.

REQ-034 §4.2: Verifies the SearchProfile model accepts required fields,
stores JSONB bucket data, and reflects the correct values at the
Python-object level.
"""

import uuid
from datetime import UTC, datetime

from app.models.search_profile import SearchProfile

_NOW = datetime.now(UTC)
_PERSONA_ID = uuid.uuid4()


class TestSearchProfileInstantiation:
    """Verify SearchProfile can be constructed with expected field values."""

    def test_persona_id_stored_correctly(self) -> None:
        """persona_id assigned in constructor is accessible on the instance."""
        profile = SearchProfile(persona_id=_PERSONA_ID)
        assert profile.persona_id == _PERSONA_ID

    def test_fit_searches_explicit_value_stored(self) -> None:
        """Explicit fit_searches list is accessible after construction."""
        buckets = [
            {
                "label": "SWE",
                "keywords": ["python"],
                "titles": ["Software Engineer"],
                "remoteok_tags": ["python"],
                "location": None,
            }
        ]
        profile = SearchProfile(persona_id=_PERSONA_ID, fit_searches=buckets)
        assert profile.fit_searches == buckets

    def test_stretch_searches_explicit_value_stored(self) -> None:
        """Explicit stretch_searches list is accessible after construction."""
        profile = SearchProfile(persona_id=_PERSONA_ID, stretch_searches=[])
        assert profile.stretch_searches == []

    def test_persona_fingerprint_explicit_value_stored(self) -> None:
        """Explicit persona_fingerprint string is accessible after construction."""
        fingerprint = "a" * 64
        profile = SearchProfile(persona_id=_PERSONA_ID, persona_fingerprint=fingerprint)
        assert profile.persona_fingerprint == fingerprint

    def test_is_stale_explicit_false_stored(self) -> None:
        """Explicit is_stale=False is accessible after construction."""
        profile = SearchProfile(persona_id=_PERSONA_ID, is_stale=False)
        assert profile.is_stale is False

    def test_is_stale_explicit_true_stored(self) -> None:
        """Explicit is_stale=True is accessible after construction."""
        profile = SearchProfile(persona_id=_PERSONA_ID, is_stale=True)
        assert profile.is_stale is True

    def test_generated_at_explicit_value_stored(self) -> None:
        """Explicit generated_at datetime is accessible after construction."""
        profile = SearchProfile(persona_id=_PERSONA_ID, generated_at=_NOW)
        assert profile.generated_at == _NOW

    def test_approved_at_explicit_value_stored(self) -> None:
        """Explicit approved_at datetime is accessible after construction."""
        profile = SearchProfile(persona_id=_PERSONA_ID, approved_at=_NOW)
        assert profile.approved_at == _NOW

    def test_all_fields_together(self) -> None:
        """All fields can be set simultaneously without conflict."""
        buckets = [
            {
                "label": "Role",
                "keywords": [],
                "titles": [],
                "remoteok_tags": [],
                "location": "NYC",
            }
        ]
        profile = SearchProfile(
            persona_id=_PERSONA_ID,
            fit_searches=buckets,
            stretch_searches=[],
            persona_fingerprint="b" * 64,
            is_stale=False,
            generated_at=_NOW,
            approved_at=_NOW,
        )
        assert profile.persona_id == _PERSONA_ID
        assert profile.fit_searches == buckets
        assert profile.stretch_searches == []
        assert profile.persona_fingerprint == "b" * 64
        assert profile.is_stale is False
        assert profile.generated_at == _NOW
        assert profile.approved_at == _NOW

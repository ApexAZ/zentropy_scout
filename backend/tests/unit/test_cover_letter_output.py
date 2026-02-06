"""Tests for cover letter output schema.

REQ-010 §5.5: Cover Letter Output Schema.

Verifies the GeneratedCoverLetter dataclass bundles draft text, agent
reasoning, word count, stories used, and validation result into a single
output object with a to_cover_letter_record() method for database persistence.
"""

import dataclasses
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.services.cover_letter_output import GeneratedCoverLetter
from app.services.cover_letter_validation import (
    CoverLetterValidation,
    ValidationIssue,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_validation(
    *,
    passed: bool = True,
    issues: tuple[ValidationIssue, ...] = (),
    word_count: int = 300,
) -> CoverLetterValidation:
    """Create a CoverLetterValidation for testing."""
    return CoverLetterValidation(
        passed=passed,
        issues=issues,
        word_count=word_count,
    )


def _make_output(
    *,
    draft_text: str = "A solid cover letter with enough words.",
    agent_reasoning: str = "Selected the leadership story for cultural fit.",
    word_count: int = 300,
    stories_used: tuple[UUID, ...] | None = None,
    validation: CoverLetterValidation | None = None,
) -> GeneratedCoverLetter:
    """Create a GeneratedCoverLetter for testing."""
    if stories_used is None:
        stories_used = (uuid4(), uuid4())
    if validation is None:
        validation = _make_validation(word_count=word_count)
    return GeneratedCoverLetter(
        draft_text=draft_text,
        agent_reasoning=agent_reasoning,
        word_count=word_count,
        stories_used=stories_used,
        validation=validation,
    )


# =============================================================================
# GeneratedCoverLetter Construction
# =============================================================================


class TestGeneratedCoverLetter:
    """Tests for GeneratedCoverLetter dataclass."""

    def test_construction_with_all_fields(self) -> None:
        """Can construct with all required fields."""
        story_ids = (uuid4(), uuid4())
        validation = _make_validation()
        output = GeneratedCoverLetter(
            draft_text="Hello world",
            agent_reasoning="Chose story A",
            word_count=300,
            stories_used=story_ids,
            validation=validation,
        )
        assert output.draft_text == "Hello world"
        assert output.agent_reasoning == "Chose story A"
        assert output.word_count == 300
        assert output.stories_used == story_ids
        assert output.validation is validation

    def test_is_frozen(self) -> None:
        """GeneratedCoverLetter is frozen to prevent mutation."""
        output = _make_output()
        with pytest.raises(dataclasses.FrozenInstanceError):
            output.draft_text = "changed"  # type: ignore[misc]

    def test_stores_uuid_stories(self) -> None:
        """stories_used contains UUID objects."""
        story_id = uuid4()
        output = _make_output(stories_used=(story_id,))
        assert isinstance(output.stories_used[0], UUID)

    def test_empty_stories_allowed(self) -> None:
        """Cover letter can reference zero stories."""
        output = _make_output(stories_used=())
        assert output.stories_used == ()

    def test_validation_embeds_cover_letter_validation(self) -> None:
        """validation field holds a CoverLetterValidation instance."""
        validation = _make_validation(passed=False)
        output = _make_output(validation=validation)
        assert isinstance(output.validation, CoverLetterValidation)
        assert output.validation.passed is False

    def test_word_count_is_int(self) -> None:
        """word_count is a plain integer."""
        output = _make_output(word_count=275)
        assert output.word_count == 275
        assert isinstance(output.word_count, int)


# =============================================================================
# to_cover_letter_record
# =============================================================================


class TestToCoverLetterRecord:
    """Tests for to_cover_letter_record() method."""

    def test_returns_dict(self) -> None:
        """Method returns a plain dict."""
        output = _make_output()
        record = output.to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert isinstance(record, dict)

    def test_includes_persona_id(self) -> None:
        """Record contains the given persona_id."""
        pid = uuid4()
        record = _make_output().to_cover_letter_record(
            persona_id=pid, job_posting_id=uuid4()
        )
        assert record["persona_id"] == pid

    def test_includes_job_posting_id(self) -> None:
        """Record contains the given job_posting_id."""
        jpid = uuid4()
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=jpid
        )
        assert record["job_posting_id"] == jpid

    def test_stories_serialized_as_strings(self) -> None:
        """achievement_stories_used contains string UUIDs for JSONB storage."""
        s1, s2 = uuid4(), uuid4()
        record = _make_output(stories_used=(s1, s2)).to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["achievement_stories_used"] == [str(s1), str(s2)]

    def test_includes_draft_text(self) -> None:
        """Record contains draft_text from the output."""
        record = _make_output(draft_text="My letter").to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["draft_text"] == "My letter"

    def test_final_text_is_none(self) -> None:
        """final_text is always None at generation time."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["final_text"] is None

    def test_status_is_draft(self) -> None:
        """Status is always 'Draft' at generation time."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["status"] == "Draft"

    def test_includes_agent_reasoning(self) -> None:
        """Record contains agent_reasoning."""
        record = _make_output(agent_reasoning="Because reasons").to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["agent_reasoning"] == "Because reasons"

    def test_id_is_uuid(self) -> None:
        """Record contains a generated UUID id."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert isinstance(record["id"], UUID)

    def test_each_call_generates_unique_id(self) -> None:
        """Each call to to_cover_letter_record produces a unique id."""
        output = _make_output()
        r1 = output.to_cover_letter_record(persona_id=uuid4(), job_posting_id=uuid4())
        r2 = output.to_cover_letter_record(persona_id=uuid4(), job_posting_id=uuid4())
        assert r1["id"] != r2["id"]

    def test_created_at_is_utc_aware(self) -> None:
        """created_at is a timezone-aware UTC datetime."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert isinstance(record["created_at"], datetime)
        assert record["created_at"].tzinfo is not None

    def test_updated_at_is_utc_aware(self) -> None:
        """updated_at is a timezone-aware UTC datetime."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert isinstance(record["updated_at"], datetime)
        assert record["updated_at"].tzinfo is not None

    def test_record_has_all_expected_keys(self) -> None:
        """Record dict has exactly the expected keys for CoverLetter ORM model."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        expected_keys = {
            "id",
            "persona_id",
            "job_posting_id",
            "achievement_stories_used",
            "draft_text",
            "final_text",
            "status",
            "agent_reasoning",
            "created_at",
            "updated_at",
        }
        assert set(record.keys()) == expected_keys

    def test_empty_stories_produces_empty_list(self) -> None:
        """Empty stories_used produces empty list in record."""
        record = _make_output(stories_used=()).to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["achievement_stories_used"] == []

    def test_created_at_equals_updated_at(self) -> None:
        """At creation time, both timestamps should be identical."""
        record = _make_output().to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["created_at"] == record["updated_at"]

    def test_stories_order_preserved_in_record(self) -> None:
        """Story UUIDs maintain insertion order in record."""
        s1, s2, s3 = uuid4(), uuid4(), uuid4()
        record = _make_output(stories_used=(s1, s2, s3)).to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert record["achievement_stories_used"] == [str(s1), str(s2), str(s3)]

    def test_record_produced_regardless_of_validation_status(self) -> None:
        """Record is produced even when validation fails."""
        validation = _make_validation(passed=False)
        record = _make_output(validation=validation).to_cover_letter_record(
            persona_id=uuid4(), job_posting_id=uuid4()
        )
        assert isinstance(record, dict)
        assert record["status"] == "Draft"


# =============================================================================
# Safety Bounds
# =============================================================================


class TestSafetyBounds:
    """Tests for input safety bounds on GeneratedCoverLetter."""

    def test_rejects_oversized_draft_text(self) -> None:
        """draft_text exceeding 50,000 characters raises ValueError."""
        with pytest.raises(ValueError, match="draft_text"):
            _make_output(draft_text="x" * 50_001)

    def test_rejects_oversized_agent_reasoning(self) -> None:
        """agent_reasoning exceeding 10,000 characters raises ValueError."""
        with pytest.raises(ValueError, match="agent_reasoning"):
            _make_output(agent_reasoning="x" * 10_001)

    def test_rejects_negative_word_count(self) -> None:
        """Negative word_count raises ValueError."""
        with pytest.raises(ValueError, match="word_count"):
            _make_output(word_count=-1)

    def test_rejects_too_many_stories(self) -> None:
        """More than 50 stories raises ValueError."""
        stories = tuple(uuid4() for _ in range(51))
        with pytest.raises(ValueError, match="stories_used"):
            _make_output(stories_used=stories)

    def test_at_boundary_does_not_raise(self) -> None:
        """Inputs exactly at limits are accepted."""
        _make_output(
            draft_text="x" * 50_000,
            agent_reasoning="y" * 10_000,
            word_count=0,
            stories_used=tuple(uuid4() for _ in range(50)),
        )

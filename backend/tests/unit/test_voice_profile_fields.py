"""Tests for VoiceProfile model fields.

REQ-005 §4.1: Voice profile database schema.
REQ-010 §3.1: Voice profile fields and their generation impact.

Verifies the VoiceProfile SQLAlchemy model has all columns required by the
spec, with correct types and constraints.
"""

from sqlalchemy import DateTime, Text, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.persona_settings import VoiceProfile

# =============================================================================
# Column Presence Tests
# =============================================================================


class TestVoiceProfileColumns:
    """Tests that VoiceProfile has all spec-required columns."""

    def test_has_all_generation_fields(self) -> None:
        """Model must have all six generation-impact fields from REQ-010 §3.1."""

        mapper = inspect(VoiceProfile)
        column_names = {col.key for col in mapper.columns}

        generation_fields = {
            "tone",
            "sentence_style",
            "vocabulary_level",
            "personality_markers",
            "sample_phrases",
            "things_to_avoid",
        }
        assert generation_fields.issubset(column_names)

    def test_has_writing_sample_text(self) -> None:
        """Model must have writing_sample_text for voice derivation."""

        mapper = inspect(VoiceProfile)
        column_names = {col.key for col in mapper.columns}
        assert "writing_sample_text" in column_names

    def test_has_primary_key_and_foreign_key(self) -> None:
        """Model must have id (PK) and persona_id (FK)."""

        mapper = inspect(VoiceProfile)
        column_names = {col.key for col in mapper.columns}
        assert "id" in column_names
        assert "persona_id" in column_names

    def test_has_timestamp_columns(self) -> None:
        """Model must have created_at and updated_at per REQ-005 §4.1."""

        mapper = inspect(VoiceProfile)
        column_names = {col.key for col in mapper.columns}
        assert "created_at" in column_names
        assert "updated_at" in column_names


# =============================================================================
# Column Type Tests
# =============================================================================


class TestVoiceProfileColumnTypes:
    """Tests that column types match REQ-005 §4.1."""

    def test_text_fields_are_text_type(self) -> None:
        """tone, sentence_style, vocabulary_level should be Text."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("tone", "sentence_style", "vocabulary_level"):
            assert isinstance(columns[field_name].type, Text), (
                f"{field_name} should be Text"
            )

    def test_jsonb_fields_are_jsonb_type(self) -> None:
        """sample_phrases and things_to_avoid should be JSONB."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("sample_phrases", "things_to_avoid"):
            assert isinstance(columns[field_name].type, JSONB), (
                f"{field_name} should be JSONB"
            )

    def test_id_is_uuid_type(self) -> None:
        """id should be UUID."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}
        assert isinstance(columns["id"].type, UUID)

    def test_timestamps_are_datetime_with_timezone(self) -> None:
        """created_at and updated_at should be DateTime(timezone=True)."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("created_at", "updated_at"):
            col_type = columns[field_name].type
            assert isinstance(col_type, DateTime), f"{field_name} should be DateTime"
            assert col_type.timezone is True, f"{field_name} should have timezone=True"

    def test_updated_at_has_onupdate(self) -> None:
        """updated_at must have onupdate set so it auto-updates on modification."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}
        assert columns["updated_at"].onupdate is not None


# =============================================================================
# Nullability Tests
# =============================================================================


class TestVoiceProfileNullability:
    """Tests that nullability matches REQ-005 §4.1."""

    def test_required_text_fields_not_nullable(self) -> None:
        """tone, sentence_style, vocabulary_level must be NOT NULL."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("tone", "sentence_style", "vocabulary_level"):
            assert columns[field_name].nullable is False, (
                f"{field_name} should be NOT NULL"
            )

    def test_optional_text_fields_are_nullable(self) -> None:
        """personality_markers and writing_sample_text are optional."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("personality_markers", "writing_sample_text"):
            assert columns[field_name].nullable is True, (
                f"{field_name} should be nullable"
            )

    def test_jsonb_fields_not_nullable(self) -> None:
        """sample_phrases and things_to_avoid must be NOT NULL per REQ-005."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("sample_phrases", "things_to_avoid"):
            assert columns[field_name].nullable is False, (
                f"{field_name} should be NOT NULL"
            )

    def test_timestamps_not_nullable(self) -> None:
        """created_at and updated_at must be NOT NULL."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}

        for field_name in ("created_at", "updated_at"):
            assert columns[field_name].nullable is False, (
                f"{field_name} should be NOT NULL"
            )


# =============================================================================
# Relationship Tests
# =============================================================================


class TestVoiceProfileRelationships:
    """Tests for VoiceProfile relationships."""

    def test_has_persona_relationship(self) -> None:
        """Model must have a persona back-reference."""

        mapper = inspect(VoiceProfile)
        relationship_names = {rel.key for rel in mapper.relationships}
        assert "persona" in relationship_names

    def test_persona_id_is_unique(self) -> None:
        """persona_id must have unique constraint for 1:1 relationship."""

        mapper = inspect(VoiceProfile)
        columns = {col.key: col for col in mapper.columns}
        assert columns["persona_id"].unique is True


# =============================================================================
# Table Configuration Tests
# =============================================================================


class TestVoiceProfileTableConfig:
    """Tests for table-level configuration."""

    def test_table_name(self) -> None:
        """Table name must be 'voice_profiles'."""

        assert VoiceProfile.__tablename__ == "voice_profiles"

    def test_total_column_count(self) -> None:
        """Model should have exactly 11 columns (id + persona_id + 7 fields + 2 timestamps)."""

        mapper = inspect(VoiceProfile)
        columns = {col.key for col in mapper.columns}
        assert len(columns) == 11, f"Expected 11 columns, got {len(columns)}: {columns}"


# =============================================================================
# Docstring Tests
# =============================================================================


class TestVoiceProfileDocumentation:
    """Tests that generation impact documentation is present."""

    def test_docstring_references_req_010(self) -> None:
        """Docstring must reference REQ-010 §3.1 for generation impact."""

        assert VoiceProfile.__doc__ is not None
        assert "REQ-010" in VoiceProfile.__doc__

    def test_docstring_documents_generation_fields(self) -> None:
        """Docstring must document generation impact for each field."""

        doc = VoiceProfile.__doc__
        assert doc is not None

        for field_name in (
            "tone",
            "sentence_style",
            "vocabulary_level",
            "personality_markers",
            "sample_phrases",
            "things_to_avoid",
            "writing_sample_text",
        ):
            assert field_name in doc, (
                f"Docstring should document generation impact for '{field_name}'"
            )

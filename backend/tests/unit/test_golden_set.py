"""Tests for golden set schema and loader.

REQ-008 §11.2: Validation Approach — Golden Set.

The golden set is a curated collection of Persona/Job pairs with human-labeled
scores used to validate the scoring algorithm's accuracy.
"""

import json
from pathlib import Path

import pytest

from app.services.golden_set import (
    GoldenSet,
    GoldenSetEntry,
    GoldenSetMetadata,
    GoldenSetValidationError,
    load_golden_set,
)

# =============================================================================
# GoldenSetEntry Tests
# =============================================================================


class TestGoldenSetEntry:
    """Tests for individual golden set entries."""

    def test_entry_accepts_all_valid_fields(self) -> None:
        """Entry should accept all valid fields."""
        entry = GoldenSetEntry(
            id="gs-001",
            persona_summary="Senior Python developer with 8 years experience",
            job_summary="Backend engineer role at fintech startup",
            human_fit_score=85,
            human_stretch_score=45,
            notes="Strong technical match, limited growth opportunity",
        )

        assert entry.id == "gs-001"
        assert (
            entry.persona_summary == "Senior Python developer with 8 years experience"
        )
        assert entry.job_summary == "Backend engineer role at fintech startup"
        assert entry.human_fit_score == 85
        assert entry.human_stretch_score == 45
        assert entry.notes == "Strong technical match, limited growth opportunity"

    def test_entry_without_optional_notes(self) -> None:
        """Entry should work without optional notes field."""
        entry = GoldenSetEntry(
            id="gs-002",
            persona_summary="Junior frontend developer",
            job_summary="React developer position",
            human_fit_score=70,
            human_stretch_score=60,
        )

        assert entry.id == "gs-002"
        assert entry.notes is None

    def test_entry_accepts_scores_at_boundaries(self) -> None:
        """Scores at 0 and 100 boundaries should be valid."""
        entry_min = GoldenSetEntry(
            id="gs-003",
            persona_summary="Career changer with no tech experience",
            job_summary="Senior architect position",
            human_fit_score=0,
            human_stretch_score=0,
        )
        assert entry_min.human_fit_score == 0
        assert entry_min.human_stretch_score == 0

        entry_max = GoldenSetEntry(
            id="gs-004",
            persona_summary="Perfect match candidate",
            job_summary="Exact role match",
            human_fit_score=100,
            human_stretch_score=100,
        )
        assert entry_max.human_fit_score == 100
        assert entry_max.human_stretch_score == 100

    def test_entry_rejects_score_below_zero(self) -> None:
        """Scores below 0 should be rejected."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            GoldenSetEntry(
                id="gs-005",
                persona_summary="Test",
                job_summary="Test",
                human_fit_score=-1,
                human_stretch_score=50,
            )

    def test_entry_rejects_score_above_100(self) -> None:
        """Scores above 100 should be rejected."""
        with pytest.raises(ValueError, match="less than or equal to 100"):
            GoldenSetEntry(
                id="gs-006",
                persona_summary="Test",
                job_summary="Test",
                human_fit_score=50,
                human_stretch_score=101,
            )

    def test_entry_rejects_empty_id(self) -> None:
        """Empty ID should be rejected."""
        with pytest.raises(ValueError, match="at least 1 character"):
            GoldenSetEntry(
                id="",
                persona_summary="Test",
                job_summary="Test",
                human_fit_score=50,
                human_stretch_score=50,
            )


# =============================================================================
# GoldenSetMetadata Tests
# =============================================================================


class TestGoldenSetMetadata:
    """Tests for golden set metadata."""

    def test_metadata_accepts_all_valid_fields(self) -> None:
        """Metadata should accept all valid fields."""
        metadata = GoldenSetMetadata(
            version="1.0.0",
            created_date="2026-02-04",
            last_updated="2026-02-04",
            description="Initial golden set for scoring validation",
            curated_by="Brian",
            target_correlation=0.8,
        )

        assert metadata.version == "1.0.0"
        assert metadata.target_correlation == 0.8


# =============================================================================
# GoldenSet Tests
# =============================================================================


class TestGoldenSet:
    """Tests for the complete golden set collection."""

    def test_golden_set_holds_multiple_entries(self) -> None:
        """Golden set should hold multiple entries."""
        entries = [
            GoldenSetEntry(
                id="gs-001",
                persona_summary="Senior developer",
                job_summary="Backend role",
                human_fit_score=85,
                human_stretch_score=40,
            ),
            GoldenSetEntry(
                id="gs-002",
                persona_summary="Junior developer",
                job_summary="Entry position",
                human_fit_score=60,
                human_stretch_score=75,
            ),
        ]
        metadata = GoldenSetMetadata(version="1.0.0", created_date="2026-02-04")

        golden_set = GoldenSet(metadata=metadata, entries=entries)

        assert len(golden_set.entries) == 2
        assert golden_set.metadata.version == "1.0.0"

    def test_golden_set_rejects_duplicate_ids(self) -> None:
        """Golden set should reject entries with duplicate IDs."""
        entries = [
            GoldenSetEntry(
                id="gs-001",
                persona_summary="Persona 1",
                job_summary="Job 1",
                human_fit_score=50,
                human_stretch_score=50,
            ),
            GoldenSetEntry(
                id="gs-001",  # Duplicate ID
                persona_summary="Persona 2",
                job_summary="Job 2",
                human_fit_score=60,
                human_stretch_score=60,
            ),
        ]
        metadata = GoldenSetMetadata(version="1.0.0", created_date="2026-02-04")

        with pytest.raises(ValueError, match="Duplicate entry IDs"):
            GoldenSet(metadata=metadata, entries=entries)

    def test_get_entry_returns_entry_when_id_exists(self) -> None:
        """Should be able to retrieve entry by ID."""
        entries = [
            GoldenSetEntry(
                id="gs-001",
                persona_summary="Senior developer",
                job_summary="Backend role",
                human_fit_score=85,
                human_stretch_score=40,
            ),
            GoldenSetEntry(
                id="gs-002",
                persona_summary="Junior developer",
                job_summary="Entry position",
                human_fit_score=60,
                human_stretch_score=75,
            ),
        ]
        metadata = GoldenSetMetadata(version="1.0.0", created_date="2026-02-04")
        golden_set = GoldenSet(metadata=metadata, entries=entries)

        entry = golden_set.get_entry("gs-002")

        assert entry is not None
        assert entry.persona_summary == "Junior developer"

    def test_golden_set_get_entry_returns_none_for_missing(self) -> None:
        """Get entry should return None for non-existent ID."""
        entries = [
            GoldenSetEntry(
                id="gs-001",
                persona_summary="Test",
                job_summary="Test",
                human_fit_score=50,
                human_stretch_score=50,
            ),
        ]
        metadata = GoldenSetMetadata(version="1.0.0", created_date="2026-02-04")
        golden_set = GoldenSet(metadata=metadata, entries=entries)

        entry = golden_set.get_entry("gs-999")

        assert entry is None


# =============================================================================
# load_golden_set Tests
# =============================================================================


class TestLoadGoldenSet:
    """Tests for loading golden set from JSON file."""

    def test_load_valid_golden_set(self, tmp_path: Path) -> None:
        """Should load valid golden set from JSON file."""
        golden_set_data = {
            "metadata": {
                "version": "1.0.0",
                "created_date": "2026-02-04",
                "description": "Test golden set",
            },
            "entries": [
                {
                    "id": "gs-001",
                    "persona_summary": "Senior Python developer",
                    "job_summary": "Backend engineer role",
                    "human_fit_score": 85,
                    "human_stretch_score": 45,
                },
                {
                    "id": "gs-002",
                    "persona_summary": "Junior developer",
                    "job_summary": "Entry level position",
                    "human_fit_score": 60,
                    "human_stretch_score": 70,
                },
            ],
        }

        file_path = tmp_path / "golden_set.json"
        file_path.write_text(json.dumps(golden_set_data))

        golden_set = load_golden_set(file_path)

        assert golden_set.entry_count == 2
        assert golden_set.metadata.version == "1.0.0"
        assert golden_set.get_entry("gs-001") is not None

    def test_load_missing_file_raises_error(self) -> None:
        """Should raise error for missing file."""
        with pytest.raises(GoldenSetValidationError, match="not found"):
            load_golden_set(Path("/nonexistent/path/golden_set.json"))

    def test_load_invalid_json_raises_error(self, tmp_path: Path) -> None:
        """Should raise error for invalid JSON."""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("{ invalid json }")

        with pytest.raises(GoldenSetValidationError, match="Invalid JSON"):
            load_golden_set(file_path)

    def test_load_missing_metadata_raises_error(self, tmp_path: Path) -> None:
        """Should raise error when metadata is missing."""
        data = {"entries": []}
        file_path = tmp_path / "no_metadata.json"
        file_path.write_text(json.dumps(data))

        with pytest.raises(GoldenSetValidationError, match="metadata"):
            load_golden_set(file_path)

    def test_load_missing_entries_raises_error(self, tmp_path: Path) -> None:
        """Should raise error when entries are missing."""
        data = {"metadata": {"version": "1.0.0", "created_date": "2026-02-04"}}
        file_path = tmp_path / "no_entries.json"
        file_path.write_text(json.dumps(data))

        with pytest.raises(GoldenSetValidationError, match="entries"):
            load_golden_set(file_path)

    def test_load_invalid_entry_raises_error(self, tmp_path: Path) -> None:
        """Should raise error for invalid entry data."""
        data = {
            "metadata": {"version": "1.0.0", "created_date": "2026-02-04"},
            "entries": [
                {
                    "id": "gs-001",
                    "persona_summary": "Test",
                    "job_summary": "Test",
                    "human_fit_score": 150,  # Invalid: > 100
                    "human_stretch_score": 50,
                }
            ],
        }
        file_path = tmp_path / "invalid_entry.json"
        file_path.write_text(json.dumps(data))

        with pytest.raises(GoldenSetValidationError, match="validation"):
            load_golden_set(file_path)

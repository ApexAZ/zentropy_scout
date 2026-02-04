"""Tests for the golden set fixture file.

REQ-008 §11.2: Validation Approach — Golden Set.

Verifies the golden set fixture file is valid and loadable.
"""

from pathlib import Path

from app.services.golden_set import load_golden_set


class TestGoldenSetFixture:
    """Tests for the golden set fixture file."""

    def test_fixture_loads_successfully(self) -> None:
        """Golden set fixture should load without errors."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "golden_set.json"

        golden_set = load_golden_set(fixture_path)

        assert golden_set.entry_count >= 5  # Minimum seed entries
        assert golden_set.metadata.version is not None

    def test_fixture_has_valid_metadata(self) -> None:
        """Golden set fixture should have complete metadata."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "golden_set.json"

        golden_set = load_golden_set(fixture_path)

        assert golden_set.metadata.version == "0.1.0"
        assert golden_set.metadata.target_correlation == 0.8
        assert golden_set.metadata.curated_by is not None

    def test_fixture_entries_have_valid_scores(self) -> None:
        """All fixture entries should have valid score ranges."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "golden_set.json"

        golden_set = load_golden_set(fixture_path)

        for entry in golden_set.entries:
            assert 0 <= entry.human_fit_score <= 100, (
                f"{entry.id} fit score out of range"
            )
            assert 0 <= entry.human_stretch_score <= 100, (
                f"{entry.id} stretch score out of range"
            )

    def test_fixture_entries_have_unique_ids(self) -> None:
        """All fixture entries should have unique IDs."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "golden_set.json"

        golden_set = load_golden_set(fixture_path)

        ids = [entry.id for entry in golden_set.entries]
        assert len(ids) == len(set(ids)), "Duplicate IDs found in fixture"

    def test_fixture_entries_have_summaries(self) -> None:
        """All fixture entries should have non-empty summaries."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "golden_set.json"

        golden_set = load_golden_set(fixture_path)

        for entry in golden_set.entries:
            assert len(entry.persona_summary) > 10, (
                f"{entry.id} persona summary too short"
            )
            assert len(entry.job_summary) > 10, f"{entry.id} job summary too short"

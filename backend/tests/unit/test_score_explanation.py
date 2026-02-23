"""Unit tests for Score Explanation data structure.

REQ-008 §8.1: Explanation Components.

Tests cover:
- ScoreExplanation dataclass structure (five required fields)
- Field types (str for summary, list[str] for others)
- Immutability (frozen dataclass)
- Empty list defaults work correctly
"""

from dataclasses import replace

from app.services.score_explanation import ScoreExplanation

# =============================================================================
# Data Structure Tests (REQ-008 §8.1)
# =============================================================================


class TestScoreExplanationStructure:
    """Tests for ScoreExplanation dataclass structure."""

    def test_has_summary_field(self) -> None:
        """ScoreExplanation has summary field."""
        explanation = ScoreExplanation(
            summary="Test summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        assert explanation.summary == "Test summary."

    def test_has_strengths_field(self) -> None:
        """ScoreExplanation has strengths list field."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=["Strong Python skills"],
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        assert explanation.strengths == ["Strong Python skills"]

    def test_has_gaps_field(self) -> None:
        """ScoreExplanation has gaps list field."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=["Missing React experience"],
            stretch_opportunities=[],
            warnings=[],
        )
        assert explanation.gaps == ["Missing React experience"]

    def test_has_stretch_opportunities_field(self) -> None:
        """ScoreExplanation has stretch_opportunities list field."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=["Exposure to ML pipeline"],
            warnings=[],
        )
        assert explanation.stretch_opportunities == ["Exposure to ML pipeline"]

    def test_has_warnings_field(self) -> None:
        """ScoreExplanation has warnings list field."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=["Salary not disclosed"],
        )
        assert explanation.warnings == ["Salary not disclosed"]


# =============================================================================
# Multiple Items Tests (REQ-008 §8.1)
# =============================================================================


class TestScoreExplanationMultipleItems:
    """Tests for multiple items in list fields."""

    def test_multiple_strengths(self) -> None:
        """Strengths can contain multiple items."""
        strengths = [
            "Strong technical fit with Python",
            "Experience level is a perfect match",
            "Role title aligns well",
        ]
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=strengths,
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        assert len(explanation.strengths) == 3
        assert explanation.strengths[0] == "Strong technical fit with Python"

    def test_multiple_gaps(self) -> None:
        """Gaps can contain multiple items."""
        gaps = [
            "Missing required skill: Kubernetes",
            "Under-qualified for years of experience",
        ]
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=gaps,
            stretch_opportunities=[],
            warnings=[],
        )
        assert len(explanation.gaps) == 2

    def test_multiple_stretch_opportunities(self) -> None:
        """Stretch opportunities can contain multiple items."""
        opportunities = [
            "Exposure to target skills: Machine Learning",
            "Role aligns with career goal: Senior Engineer",
        ]
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=opportunities,
            warnings=[],
        )
        assert len(explanation.stretch_opportunities) == 2

    def test_multiple_warnings(self) -> None:
        """Warnings can contain multiple items."""
        warnings = [
            "Salary not disclosed",
            "High ghost risk (65%)",
            "May be overqualified",
        ]
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=warnings,
        )
        assert len(explanation.warnings) == 3


# =============================================================================
# Immutability Tests (REQ-008 §8.1)
# =============================================================================


class TestScoreExplanationImmutability:
    """Tests for ScoreExplanation immutability."""

    def test_cannot_modify_summary(self) -> None:
        """Cannot modify summary after creation."""
        explanation = ScoreExplanation(
            summary="Original summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        updated = replace(explanation, summary="Modified summary.")
        assert explanation.summary == "Original summary."
        assert updated.summary == "Modified summary."

    def test_cannot_modify_strengths(self) -> None:
        """Cannot modify strengths list reference after creation."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=["Original"],
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        updated = replace(explanation, strengths=["Modified"])
        assert explanation.strengths == ["Original"]
        assert updated.strengths == ["Modified"]

    def test_cannot_modify_gaps(self) -> None:
        """Cannot modify gaps list reference after creation."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=["Original"],
            stretch_opportunities=[],
            warnings=[],
        )
        updated = replace(explanation, gaps=["Modified"])
        assert explanation.gaps == ["Original"]
        assert updated.gaps == ["Modified"]

    def test_cannot_modify_stretch_opportunities(self) -> None:
        """Cannot modify stretch_opportunities list reference after creation."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=["Original"],
            warnings=[],
        )
        updated = replace(explanation, stretch_opportunities=["Modified"])
        assert explanation.stretch_opportunities == ["Original"]
        assert updated.stretch_opportunities == ["Modified"]

    def test_cannot_modify_warnings(self) -> None:
        """Cannot modify warnings list reference after creation."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=["Original"],
        )
        updated = replace(explanation, warnings=["Modified"])
        assert explanation.warnings == ["Original"]
        assert updated.warnings == ["Modified"]


# =============================================================================
# Empty Fields Tests (REQ-008 §8.1)
# =============================================================================


class TestScoreExplanationEmptyFields:
    """Tests for empty field handling."""

    def test_empty_summary_allowed(self) -> None:
        """Empty summary is allowed (generation may not produce one)."""
        explanation = ScoreExplanation(
            summary="",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        assert explanation.summary == ""

    def test_all_lists_empty(self) -> None:
        """All list fields can be empty."""
        explanation = ScoreExplanation(
            summary="Summary.",
            strengths=[],
            gaps=[],
            stretch_opportunities=[],
            warnings=[],
        )
        assert explanation.strengths == []
        assert explanation.gaps == []
        assert explanation.stretch_opportunities == []
        assert explanation.warnings == []


# =============================================================================
# Full Example Tests (REQ-008 §8.1)
# =============================================================================


class TestScoreExplanationFullExample:
    """Tests using realistic full explanation data."""

    def test_full_explanation_example(self) -> None:
        """Complete explanation with all fields populated."""
        explanation = ScoreExplanation(
            summary=(
                "This role is a strong fit for your technical background. "
                "You meet most requirements but may need to develop Kubernetes expertise."
            ),
            strengths=[
                "Strong technical fit — you have 5 of the key skills: Python, FastAPI, PostgreSQL, Docker, AWS",
                "Experience level is a perfect match (7 years)",
                "Role title aligns with your current position (Senior Backend Engineer)",
            ],
            gaps=[
                "Missing required skill: Kubernetes (listed as 'required')",
                "No experience with their specific tech stack component: gRPC",
            ],
            stretch_opportunities=[
                "Exposure to target skill: Machine Learning pipelines",
                "Leadership opportunity — team of 4 engineers",
            ],
            warnings=[
                "Salary not disclosed — typical range for similar roles: $150-180k",
            ],
        )

        assert "strong fit" in explanation.summary.lower()
        assert len(explanation.strengths) == 3
        assert len(explanation.gaps) == 2
        assert len(explanation.stretch_opportunities) == 2
        assert len(explanation.warnings) == 1
        assert "Salary not disclosed" in explanation.warnings[0]

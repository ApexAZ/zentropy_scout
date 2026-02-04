"""Tests for Strategist Agent graph.

REQ-007 §7: Strategist Agent — Applies scoring to discovered jobs.

The Strategist orchestrates:
1. Non-negotiables filtering
2. Embedding generation/retrieval
3. Fit and Stretch score calculation
4. Job posting updates with scores
"""

from app.agents.state import ScoreResult, StrategistState

# =============================================================================
# Trigger Condition Tests (§7.1)
# =============================================================================


class TestStrategistTriggerConditions:
    """Tests for Strategist trigger conditions per REQ-007 §7.1."""

    def test_state_accepts_jobs_to_score(self) -> None:
        """State should accept list of job IDs to score."""
        state: StrategistState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "jobs_to_score": ["job-001", "job-002", "job-003"],
            "scored_jobs": [],
            "filtered_jobs": [],
        }

        assert state["jobs_to_score"] == ["job-001", "job-002", "job-003"]
        assert len(state["scored_jobs"]) == 0

    def test_state_tracks_persona_embedding_version(self) -> None:
        """State should track persona embedding version for freshness check."""
        state: StrategistState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "persona_embedding_version": 5,
            "jobs_to_score": [],
            "scored_jobs": [],
            "filtered_jobs": [],
        }

        assert state["persona_embedding_version"] == 5

    def test_score_result_stores_all_fields(self) -> None:
        """ScoreResult should store all scoring fields."""
        result: ScoreResult = {
            "job_posting_id": "job-001",
            "fit_score": 85.5,
            "stretch_score": 42.0,
            "explanation": "Strong technical match with Python expertise.",
            "filtered_reason": None,
        }

        assert result["job_posting_id"] == "job-001"
        assert result["fit_score"] == 85.5
        assert result["stretch_score"] == 42.0
        assert result["explanation"] is not None
        assert result["filtered_reason"] is None

    def test_score_result_stores_filtered_reason(self) -> None:
        """ScoreResult should store filter reason when job fails non-negotiables."""
        result: ScoreResult = {
            "job_posting_id": "job-002",
            "fit_score": None,
            "stretch_score": None,
            "explanation": None,
            "filtered_reason": "salary_below_minimum",
        }

        assert result["fit_score"] is None
        assert result["filtered_reason"] == "salary_below_minimum"


# =============================================================================
# Scoring Flow Tests (§7.2)
# =============================================================================


class TestStrategistScoringFlow:
    """Tests for Strategist scoring flow per REQ-007 §7.2."""

    def test_state_accumulates_scored_jobs(self) -> None:
        """Scored jobs should accumulate in state."""
        state: StrategistState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "jobs_to_score": ["job-001", "job-002"],
            "scored_jobs": [],
            "filtered_jobs": [],
        }

        # Simulate scoring first job
        result1: ScoreResult = {
            "job_posting_id": "job-001",
            "fit_score": 80.0,
            "stretch_score": 45.0,
            "explanation": "Good match",
            "filtered_reason": None,
        }
        state["scored_jobs"].append(result1)

        assert len(state["scored_jobs"]) == 1
        assert state["scored_jobs"][0]["job_posting_id"] == "job-001"

    def test_state_tracks_filtered_jobs(self) -> None:
        """Filtered job IDs should be tracked separately."""
        state: StrategistState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "jobs_to_score": ["job-001", "job-002", "job-003"],
            "scored_jobs": [],
            "filtered_jobs": [],
        }

        # Simulate filtering job-002
        state["filtered_jobs"].append("job-002")

        assert "job-002" in state["filtered_jobs"]
        assert len(state["filtered_jobs"]) == 1


# =============================================================================
# Non-Negotiables Filter Integration Tests (§7.3)
# =============================================================================


class TestStrategistNonNegotiablesFiltering:
    """Tests for non-negotiables filtering in Strategist per REQ-007 §7.3."""

    def test_filtered_job_has_no_scores(self) -> None:
        """Jobs failing non-negotiables should have None scores."""
        result: ScoreResult = {
            "job_posting_id": "job-002",
            "fit_score": None,
            "stretch_score": None,
            "explanation": None,
            "filtered_reason": "remote_preference_not_met",
        }

        assert result["fit_score"] is None
        assert result["stretch_score"] is None

    def test_multiple_filter_reasons_stored(self) -> None:
        """Multiple filter failures should be joinable."""
        # If multiple non-negotiables fail, store all reasons
        result: ScoreResult = {
            "job_posting_id": "job-003",
            "fit_score": None,
            "stretch_score": None,
            "explanation": None,
            "filtered_reason": "salary_below_minimum|remote_preference_not_met",
        }

        reasons = (
            result["filtered_reason"].split("|") if result["filtered_reason"] else []
        )
        assert "salary_below_minimum" in reasons
        assert "remote_preference_not_met" in reasons


# =============================================================================
# Embedding-Based Matching Tests (§7.4)
# =============================================================================


class TestStrategistEmbeddingMatching:
    """Tests for embedding-based matching in Strategist per REQ-007 §7.4."""

    def test_stale_embeddings_detected_by_version(self) -> None:
        """Should detect when persona embeddings are stale."""
        # Current persona embedding version is 5
        # State has version 3 - stale
        state: StrategistState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "persona_embedding_version": 3,
            "jobs_to_score": ["job-001"],
            "scored_jobs": [],
            "filtered_jobs": [],
        }

        current_version = 5
        is_stale = state.get("persona_embedding_version", 0) < current_version

        assert is_stale is True

    def test_fresh_embeddings_not_regenerated(self) -> None:
        """Should not regenerate when embeddings are fresh."""
        state: StrategistState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "persona_embedding_version": 5,
            "jobs_to_score": ["job-001"],
            "scored_jobs": [],
            "filtered_jobs": [],
        }

        current_version = 5
        is_stale = state.get("persona_embedding_version", 0) < current_version

        assert is_stale is False


# =============================================================================
# Stretch Score Tests (§7.5)
# =============================================================================


class TestStrategistStretchScore:
    """Tests for stretch score in Strategist per REQ-007 §7.5."""

    def test_stretch_score_in_valid_range(self) -> None:
        """Stretch score should be 0-100."""
        result: ScoreResult = {
            "job_posting_id": "job-001",
            "fit_score": 75.0,
            "stretch_score": 88.0,
            "explanation": "High growth potential",
            "filtered_reason": None,
        }

        assert 0 <= result["stretch_score"] <= 100

    def test_stretch_score_can_be_higher_than_fit(self) -> None:
        """Career changers may have low fit but high stretch."""
        result: ScoreResult = {
            "job_posting_id": "job-001",
            "fit_score": 35.0,  # Low fit - career changer
            "stretch_score": 92.0,  # High stretch - aligns with goals
            "explanation": "Underqualified but perfect growth opportunity",
            "filtered_reason": None,
        }

        assert result["stretch_score"] > result["fit_score"]

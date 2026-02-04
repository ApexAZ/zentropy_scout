"""Tests for Strategist Agent graph.

REQ-007 §7: Strategist Agent — Applies scoring to discovered jobs.

The Strategist orchestrates:
1. Non-negotiables filtering
2. Embedding generation/retrieval
3. Fit and Stretch score calculation
4. Job posting updates with scores
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.agents.state import ScoreResult, StrategistState
from app.services.scoring_flow import (
    build_filtered_score_result,
    filter_job_non_negotiables,
    filter_jobs_batch,
)

# =============================================================================
# Test Fixtures - Mock Data for Non-Negotiables Testing
# =============================================================================


@dataclass
class MockPersona:
    """Minimal persona for non-negotiables testing.

    Implements PersonaNonNegotiablesLike protocol for use with filter functions.
    """

    remote_preference: str = "No Preference"
    minimum_base_salary: int | None = None
    commutable_cities: list[str] | None = None
    industry_exclusions: list[str] | None = None
    visa_sponsorship_required: bool = False

    def __post_init__(self) -> None:
        """Initialize list fields to empty lists if None."""
        if self.commutable_cities is None:
            self.commutable_cities = []
        if self.industry_exclusions is None:
            self.industry_exclusions = []


@dataclass
class MockJob:
    """Minimal job for non-negotiables testing.

    Implements JobFilterDataLike protocol for use with filter functions.
    """

    id: UUID
    work_model: str | None = None
    salary_max: int | None = None
    location: str | None = None
    industry: str | None = None
    visa_sponsorship: bool | None = None


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


# =============================================================================
# Non-Negotiables Filter Node Integration Tests (§7.3)
# =============================================================================


class TestStrategistFilterAndScoreNodeIntegration:
    """Tests for filter_and_score_node integration with non-negotiables.

    REQ-007 §7.3: These tests verify that the Strategist graph node
    correctly integrates with the non_negotiables_filter service.
    """

    def test_node_filters_job_failing_remote_preference(self) -> None:
        """Node should filter job that fails remote preference check."""
        persona = MockPersona(remote_preference="Remote Only")
        job = MockJob(id=uuid4(), work_model="Onsite")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False
        assert len(filter_result.failed_reasons) > 0

        score_result = build_filtered_score_result(filter_result)

        assert score_result["fit_score"] is None
        assert score_result["stretch_score"] is None
        assert score_result["filtered_reason"] is not None
        assert "Remote" in score_result["filtered_reason"]

    def test_node_passes_job_meeting_all_non_negotiables(self) -> None:
        """Node should pass job meeting all non-negotiables checks."""
        persona = MockPersona(
            remote_preference="Hybrid OK",
            minimum_base_salary=100000,
        )
        job = MockJob(
            id=uuid4(),
            work_model="Remote",
            salary_max=150000,
            industry="Technology",
            visa_sponsorship=True,
        )

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is True
        assert len(filter_result.failed_reasons) == 0

    def test_node_filters_job_below_salary_minimum(self) -> None:
        """Node should filter job with salary below minimum."""
        persona = MockPersona(minimum_base_salary=150000)
        job = MockJob(id=uuid4(), work_model="Remote", salary_max=100000)

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "Salary" in score_result["filtered_reason"]

    def test_node_filters_job_in_excluded_industry(self) -> None:
        """Node should filter job in excluded industry."""
        persona = MockPersona(industry_exclusions=["Gambling", "Tobacco"])
        job = MockJob(id=uuid4(), work_model="Remote", industry="Gambling")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "Gambling" in score_result["filtered_reason"]

    def test_node_aggregates_multiple_filter_failures(self) -> None:
        """Node should aggregate multiple non-negotiables failures."""
        persona = MockPersona(
            remote_preference="Remote Only",
            minimum_base_salary=200000,
            industry_exclusions=["Gambling"],
            visa_sponsorship_required=True,
        )
        job = MockJob(
            id=uuid4(),
            work_model="Onsite",  # Fails remote
            salary_max=100000,  # Fails salary
            industry="Gambling",  # Fails industry
            visa_sponsorship=False,  # Fails visa
        )

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False
        assert len(filter_result.failed_reasons) >= 4

        score_result = build_filtered_score_result(filter_result)
        reasons = score_result["filtered_reason"].split("|")
        assert len(reasons) >= 4

    def test_node_passes_with_undisclosed_salary_warning(self) -> None:
        """Node should pass job with undisclosed salary but add warning."""
        persona = MockPersona(minimum_base_salary=100000)
        job = MockJob(id=uuid4(), work_model="Remote")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is True
        assert any("Salary" in w for w in filter_result.warnings)

    def test_node_filters_job_requiring_visa_sponsorship(self) -> None:
        """Node should filter job when visa required but not offered."""
        persona = MockPersona(visa_sponsorship_required=True)
        job = MockJob(id=uuid4(), work_model="Remote", visa_sponsorship=False)

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "sponsorship" in score_result["filtered_reason"].lower()

    def test_node_filters_job_in_non_commutable_city(self) -> None:
        """Node should filter onsite job in non-commutable city."""
        persona = MockPersona(
            remote_preference="Onsite OK",
            commutable_cities=["San Francisco", "Oakland"],
        )
        job = MockJob(id=uuid4(), work_model="Onsite", location="New York")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "commutable" in score_result["filtered_reason"].lower()

    def test_node_passes_remote_job_regardless_of_location(self) -> None:
        """Remote jobs should pass commutable cities check regardless of location."""
        persona = MockPersona(
            remote_preference="Hybrid OK",
            commutable_cities=["San Francisco"],
        )
        job = MockJob(id=uuid4(), work_model="Remote", location="Tokyo")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is True


# =============================================================================
# Filter and Score Node State Tests (§7.3)
# =============================================================================


class TestFilterAndScoreNodeState:
    """Tests for filter_and_score_node state transitions.

    REQ-007 §7.3: These tests verify the node correctly updates state
    with filtered jobs and their reasons.
    """

    def test_batch_filter_separates_passing_and_failing_jobs(self) -> None:
        """filter_jobs_batch should correctly separate jobs."""
        persona = MockPersona(remote_preference="Remote Only")

        job1 = MockJob(id=uuid4(), work_model="Remote")
        job2 = MockJob(id=uuid4(), work_model="Onsite")
        job3 = MockJob(id=uuid4(), work_model="Remote")

        passing, filtered = filter_jobs_batch(persona, [job1, job2, job3])

        assert len(passing) == 2
        assert len(filtered) == 1
        assert passing[0].id == job1.id
        assert passing[1].id == job3.id
        assert filtered[0].job_id == job2.id

    def test_filtered_results_contain_failure_reasons(self) -> None:
        """Filtered results should contain descriptive failure reasons."""
        persona = MockPersona(
            remote_preference="Remote Only",
            minimum_base_salary=100000,
        )
        job = MockJob(id=uuid4(), work_model="Onsite", salary_max=50000)

        _, filtered = filter_jobs_batch(persona, [job])

        assert len(filtered) == 1
        assert len(filtered[0].failed_reasons) >= 2
        reasons_text = " ".join(filtered[0].failed_reasons)
        assert "Remote" in reasons_text or "Onsite" in reasons_text
        assert "Salary" in reasons_text or "salary" in reasons_text

    def test_state_output_includes_filtered_jobs_list(self) -> None:
        """Output state should track filtered job IDs separately."""
        persona = MockPersona(remote_preference="Remote Only")
        jobs = [MockJob(id=uuid4(), work_model="Onsite") for _ in range(3)]

        _, filtered = filter_jobs_batch(persona, jobs)

        filtered_job_ids = [str(f.job_id) for f in filtered]

        assert len(filtered_job_ids) == 3
        assert len(set(filtered_job_ids)) == 3

    def test_score_results_built_correctly_for_filtered_jobs(self) -> None:
        """ScoreResults for filtered jobs should have correct structure."""
        persona = MockPersona(
            remote_preference="Remote Only",
            industry_exclusions=["Gambling"],
        )
        job = MockJob(id=uuid4(), work_model="Onsite", industry="Gambling")

        _, filtered = filter_jobs_batch(persona, [job])

        # Build ScoreResult for filtered job
        score_result = build_filtered_score_result(filtered[0])

        # Verify structure matches ScoreResult TypedDict
        assert "job_posting_id" in score_result
        assert "fit_score" in score_result
        assert "stretch_score" in score_result
        assert "explanation" in score_result
        assert "filtered_reason" in score_result

        # Verify values
        assert score_result["fit_score"] is None
        assert score_result["stretch_score"] is None
        assert score_result["filtered_reason"] is not None
        assert "|" in score_result["filtered_reason"]  # Multiple reasons

    def test_empty_jobs_list_produces_empty_output(self) -> None:
        """Empty input should produce empty output."""
        persona = MockPersona(remote_preference="Remote Only")

        passing, filtered = filter_jobs_batch(persona, [])

        assert len(passing) == 0
        assert len(filtered) == 0

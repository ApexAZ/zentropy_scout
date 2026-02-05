"""Tests for Strategist Agent graph.

REQ-007 §7: Strategist Agent — Applies scoring to discovered jobs.
REQ-007 §15.4: Graph Spec — Strategist Agent (10-node graph)

The Strategist orchestrates:
1. Non-negotiables filtering
2. Embedding generation/retrieval
3. Fit and Stretch score calculation
4. Job posting updates with scores
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.state import ScoreResult, StrategistState
from app.agents.strategist_graph import (
    calculate_fit_score_node,
    calculate_stretch_score_node,
    check_auto_draft_threshold,
    check_embedding_freshness_node,
    check_non_negotiables_pass,
    create_strategist_graph,
    filter_non_negotiables_node,
    generate_job_embeddings_node,
    generate_rationale_node,
    get_strategist_graph,
    is_embedding_stale,
    load_persona_embeddings_node,
    regenerate_embeddings_node,
    reset_strategist_graph,
    save_scores_node,
    score_jobs,
    trigger_ghostwriter_node,
)
from app.services.batch_scoring import batch_score_jobs
from app.services.fit_score import FIT_NEUTRAL_SCORE
from app.services.persona_embedding_generator import (
    PersonaEmbeddingData,
    PersonaEmbeddingsResult,
)
from app.services.role_title_match import calculate_role_title_score
from app.services.scoring_flow import (
    build_filtered_score_result,
    build_scored_result,
    filter_job_non_negotiables,
    filter_jobs_batch,
)
from app.services.soft_skills_match import (
    calculate_soft_skills_score,
    cosine_similarity,
)
from app.services.stretch_score import STRETCH_NEUTRAL_SCORE

# =============================================================================
# Test Fixtures - Mock Data for Non-Negotiables Testing
# =============================================================================


@dataclass
class MockFilterPersona:
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
class MockFilterJob:
    """Minimal job for non-negotiables testing.

    Implements JobFilterDataLike protocol for use with filter functions.
    """

    id: uuid.UUID
    work_model: str | None = None
    salary_max: int | None = None
    location: str | None = None
    industry: str | None = None
    visa_sponsorship: bool | None = None


# =============================================================================
# Test Fixtures - Mock Data for Batch Scoring (§7.4)
# =============================================================================


@dataclass
class MockSkill:
    """Mock persona skill for batch scoring tests."""

    skill_name: str
    skill_type: str
    proficiency: str = "Proficient"


@dataclass
class MockExtractedSkill:
    """Mock job extracted skill for batch scoring tests."""

    skill_name: str
    skill_type: str
    is_required: bool = True
    years_requested: int | None = None


@dataclass
class MockScoringPersona:
    """Mock persona for batch scoring tests.

    Implements PersonaLike protocol required by batch_score_jobs.
    """

    id: uuid.UUID
    skills: list[MockSkill]
    years_experience: int | None = 5
    current_role: str | None = "Software Engineer"
    target_roles: list[str] | None = None
    target_skills: list[str] | None = None
    remote_preference: str = "Hybrid OK"
    commutable_cities: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize list fields to empty lists if None."""
        if self.target_roles is None:
            self.target_roles = []
        if self.target_skills is None:
            self.target_skills = []
        if self.commutable_cities is None:
            self.commutable_cities = []


@dataclass
class MockScoringJobPosting:
    """Mock job posting for batch scoring tests.

    Implements JobPostingLike protocol required by batch_score_jobs.
    """

    id: uuid.UUID
    job_title: str
    extracted_skills: list[MockExtractedSkill]
    culture_text: str | None = None
    years_experience_min: int | None = None
    years_experience_max: int | None = None
    work_model: str | None = "Hybrid"
    location: str | None = "San Francisco, CA"


@dataclass
class MockEmbeddingResult:
    """Mock embedding result matching EmbeddingResultLike protocol."""

    vectors: list[list[float]]
    model: str
    dimensions: int
    total_tokens: int


class MockEmbeddingProvider:
    """Mock embedding provider for batch scoring tests."""

    def __init__(self, dimensions: int = 1536) -> None:
        self._mock_vector = [0.1] * dimensions
        self.call_count = 0

    async def embed(self, texts: list[str]) -> MockEmbeddingResult:
        """Return mock embeddings for each input text."""
        self.call_count += 1
        return MockEmbeddingResult(
            vectors=[self._mock_vector[:] for _ in texts],
            model="text-embedding-3-small",
            dimensions=len(self._mock_vector),
            total_tokens=len(texts) * 10,
        )


def _make_scoring_persona() -> MockScoringPersona:
    """Create a standard persona for scoring tests."""
    return MockScoringPersona(
        id=uuid.uuid4(),
        skills=[
            MockSkill("Python", "Hard", "Expert"),
            MockSkill("AWS", "Hard", "Proficient"),
            MockSkill("Leadership", "Soft", "Proficient"),
        ],
        years_experience=5,
        current_role="Software Engineer",
        target_roles=["Senior Software Engineer"],
        target_skills=["Kubernetes"],
    )


def _make_scoring_persona_embeddings(
    persona_id: uuid.UUID,
) -> PersonaEmbeddingsResult:
    """Create mock persona embeddings for scoring tests."""
    mock_vector = [0.1] * 1536
    return PersonaEmbeddingsResult(
        persona_id=persona_id,
        hard_skills=PersonaEmbeddingData(
            vector=mock_vector[:],
            source_text="Python (Expert) | AWS (Proficient)",
        ),
        soft_skills=PersonaEmbeddingData(
            vector=mock_vector[:],
            source_text="Leadership",
        ),
        logistics=PersonaEmbeddingData(
            vector=mock_vector[:],
            source_text="Remote preference: Hybrid OK",
        ),
        version=datetime.now(tz=UTC),
        model_name="text-embedding-3-small",
    )


def _make_scoring_job(
    title: str = "Senior Software Engineer",
    culture_text: str | None = "Collaborative team environment",
) -> MockScoringJobPosting:
    """Create a job posting for scoring tests."""
    return MockScoringJobPosting(
        id=uuid.uuid4(),
        job_title=title,
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("AWS", "Hard", is_required=True),
            MockExtractedSkill("Docker", "Hard", is_required=False),
        ],
        culture_text=culture_text,
        years_experience_min=4,
        years_experience_max=8,
    )


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

    def test_build_scored_result_creates_valid_score_result(self) -> None:
        """build_scored_result should create ScoreResult with scores populated."""
        job_id = uuid.uuid4()
        result = build_scored_result(
            job_id=job_id,
            fit_score=85.0,
            stretch_score=72.0,
            explanation="Strong technical match with Python expertise.",
        )

        assert result["job_posting_id"] == str(job_id)
        assert result["fit_score"] == 85.0
        assert result["stretch_score"] == 72.0
        assert result["explanation"] == "Strong technical match with Python expertise."
        assert result["filtered_reason"] is None

    def test_build_scored_result_without_explanation(self) -> None:
        """build_scored_result should work without explanation."""
        job_id = uuid.uuid4()
        result = build_scored_result(
            job_id=job_id,
            fit_score=50.0,
            stretch_score=30.0,
        )

        assert result["fit_score"] == 50.0
        assert result["stretch_score"] == 30.0
        assert result["explanation"] is None
        assert result["filtered_reason"] is None

    def test_build_scored_result_validates_fit_score_bounds(self) -> None:
        """build_scored_result should reject fit_score outside 0-100."""
        with pytest.raises(ValueError, match="fit_score must be 0-100"):
            build_scored_result(
                job_id=uuid.uuid4(), fit_score=101.0, stretch_score=50.0
            )

        with pytest.raises(ValueError, match="fit_score must be 0-100"):
            build_scored_result(job_id=uuid.uuid4(), fit_score=-1.0, stretch_score=50.0)

    def test_build_scored_result_validates_stretch_score_bounds(self) -> None:
        """build_scored_result should reject stretch_score outside 0-100."""
        with pytest.raises(ValueError, match="stretch_score must be 0-100"):
            build_scored_result(
                job_id=uuid.uuid4(), fit_score=50.0, stretch_score=150.0
            )

        with pytest.raises(ValueError, match="stretch_score must be 0-100"):
            build_scored_result(
                job_id=uuid.uuid4(), fit_score=50.0, stretch_score=-10.0
            )

    def test_cosine_similarity_affects_soft_skills_score(self) -> None:
        """Soft skills score should vary based on cosine similarity.

        REQ-008 §4.3: Soft skills use embedding cosine similarity.
        Score formula: (cosine + 1) * 50, so cosine=1.0 → 100, cosine=0.0 → 50.
        """
        # Identical vectors → cosine=1.0 → score=100
        vec_a = [0.5, 0.5, 0.5, 0.5]
        identical_sim = cosine_similarity(vec_a, vec_a)
        identical_score = calculate_soft_skills_score(vec_a, vec_a)

        assert identical_sim == 1.0
        assert identical_score == 100.0

        # Orthogonal vectors → cosine=0.0 → score=50
        vec_b = [1.0, 0.0, 0.0, 0.0]
        vec_c = [0.0, 1.0, 0.0, 0.0]
        orthogonal_sim = cosine_similarity(vec_b, vec_c)
        orthogonal_score = calculate_soft_skills_score(vec_b, vec_c)

        assert orthogonal_sim == 0.0
        assert orthogonal_score == 50.0

    def test_missing_embeddings_return_neutral_score(self) -> None:
        """Missing embeddings should return neutral score (70).

        REQ-008 §9.1: Missing data returns neutral score, not penalty.
        """
        # None persona embedding
        score_no_persona = calculate_soft_skills_score(None, [0.1, 0.2, 0.3])
        assert score_no_persona == FIT_NEUTRAL_SCORE

        # None job embedding
        score_no_job = calculate_soft_skills_score([0.1, 0.2, 0.3], None)
        assert score_no_job == FIT_NEUTRAL_SCORE

        # Both None
        score_both_none = calculate_soft_skills_score(None, None)
        assert score_both_none == FIT_NEUTRAL_SCORE

    def test_role_title_exact_match_returns_perfect_score(self) -> None:
        """Exact title match should return 100 without needing embeddings.

        REQ-008 §4.5: Step 1 checks exact match before semantic similarity.
        """
        # Exact match after normalization
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=["Junior Developer"],
            job_title="Software Engineer",
            user_titles_embedding=None,  # Not needed for exact match
            job_title_embedding=None,
        )

        assert score == 100.0

    def test_role_title_synonym_match_returns_perfect_score(self) -> None:
        """Synonym title match should return 100 after normalization.

        REQ-008 §4.5.2: Title normalization handles synonyms.
        """
        # "SDE" normalizes to "software engineer"
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=[],
            job_title="SDE",
            user_titles_embedding=None,
            job_title_embedding=None,
        )

        assert score == 100.0

    def test_role_title_uses_embeddings_for_semantic_match(self) -> None:
        """Non-matching titles should use embedding similarity.

        REQ-008 §4.5: Step 2 uses embeddings for semantic matching.
        """
        # Different titles, needs embedding similarity
        embedding = [0.5] * 100  # Mock embedding

        score = calculate_role_title_score(
            current_role="Backend Developer",
            work_history_titles=[],
            job_title="API Engineer",  # Different, needs semantic match
            user_titles_embedding=embedding,
            job_title_embedding=embedding,  # Same embedding → perfect similarity
        )

        # Identical embeddings → cosine=1.0 → score=100
        assert score == 100.0

    def test_role_title_missing_embeddings_returns_neutral(self) -> None:
        """Missing embeddings for non-exact match returns neutral score."""
        score = calculate_role_title_score(
            current_role="Backend Developer",
            work_history_titles=[],
            job_title="API Engineer",  # Different, needs semantic match
            user_titles_embedding=None,  # Missing embedding
            job_title_embedding=None,
        )

        assert score == FIT_NEUTRAL_SCORE


# =============================================================================
# Batch Scoring Integration Tests (§7.4)
# =============================================================================


class TestStrategistBatchScoringIntegration:
    """Tests for batch_score_jobs integration in Strategist per REQ-007 §7.4.

    These tests verify the Strategist graph correctly calls the scoring engine
    with persona embeddings and job data to produce Fit and Stretch scores.
    """

    @pytest.mark.asyncio
    async def test_batch_scoring_produces_fit_and_stretch_scores(self) -> None:
        """batch_score_jobs should produce both Fit and Stretch scores."""
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        assert len(results) == 1
        assert 0 <= results[0].fit_score.total <= 100
        assert 0 <= results[0].stretch_score.total <= 100

    @pytest.mark.asyncio
    async def test_batch_scoring_result_maps_to_score_result(self) -> None:
        """ScoredJob from batch_score_jobs should map to ScoreResult."""
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        scored_job = results[0]
        score_result = build_scored_result(
            job_id=scored_job.job_id,
            fit_score=float(scored_job.fit_score.total),
            stretch_score=float(scored_job.stretch_score.total),
        )

        assert score_result["job_posting_id"] == str(job.id)
        assert score_result["fit_score"] == scored_job.fit_score.total
        assert score_result["stretch_score"] == scored_job.stretch_score.total
        assert score_result["filtered_reason"] is None

    @pytest.mark.asyncio
    async def test_batch_scoring_multiple_jobs(self) -> None:
        """batch_score_jobs should score multiple jobs in order."""
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()

        job1 = _make_scoring_job(title="Senior Software Engineer")
        job2 = _make_scoring_job(title="Data Scientist")

        results = await batch_score_jobs(
            jobs=[job1, job2],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        assert len(results) == 2
        assert results[0].job_id == job1.id
        assert results[1].job_id == job2.id

    @pytest.mark.asyncio
    async def test_batch_scoring_empty_jobs_returns_empty(self) -> None:
        """batch_score_jobs with empty jobs list returns empty results."""
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=[],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_scoring_uses_embedding_provider(self) -> None:
        """batch_score_jobs should call the embedding provider for job embeddings."""
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job(culture_text="Collaborative startup culture")

        await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        # Provider should be called for job title + culture embeddings
        assert provider.call_count >= 1

    @pytest.mark.asyncio
    async def test_fit_score_contains_five_components(self) -> None:
        """Fit Score should contain all 5 weighted components (REQ-008 §4.1)."""
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        fit = results[0].fit_score
        assert "hard_skills" in fit.components
        assert "soft_skills" in fit.components
        assert "experience_level" in fit.components
        assert "role_title" in fit.components
        assert "location_logistics" in fit.components

        # Verify weights sum to 1.0
        weight_sum = sum(fit.weights.values())
        assert abs(weight_sum - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_full_scoring_flow_filter_then_score(self) -> None:
        """Complete flow: filter non-negotiables, then score passing jobs.

        REQ-007 §7.2-7.4: End-to-end Strategist scoring integration.
        """
        # Setup persona with non-negotiables
        filter_persona = MockFilterPersona(
            remote_preference="Remote Only",
            minimum_base_salary=100000,
        )

        # Setup jobs: one passes, one fails
        passing_job = MockFilterJob(
            id=uuid.uuid4(), work_model="Remote", salary_max=150000
        )
        failing_job = MockFilterJob(
            id=uuid.uuid4(), work_model="Onsite", salary_max=50000
        )

        # Step 1: Filter
        passing, filtered = filter_jobs_batch(
            filter_persona, [passing_job, failing_job]
        )

        assert len(passing) == 1
        assert len(filtered) == 1
        assert passing[0].id == passing_job.id

        # Step 2: Build filtered results
        filtered_results = [build_filtered_score_result(f) for f in filtered]
        assert filtered_results[0]["fit_score"] is None
        assert filtered_results[0]["filtered_reason"] is not None

        # Step 3: Score passing jobs via batch_score_jobs
        scoring_persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(scoring_persona.id)
        provider = MockEmbeddingProvider()

        scoring_job = _make_scoring_job()
        scoring_job.id = passing_job.id  # Same ID as passing job

        scored = await batch_score_jobs(
            jobs=[scoring_job],
            persona=scoring_persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        # Step 4: Build scored results
        scored_results = [
            build_scored_result(
                job_id=s.job_id,
                fit_score=float(s.fit_score.total),
                stretch_score=float(s.stretch_score.total),
            )
            for s in scored
        ]

        # Verify complete output
        all_results = scored_results + filtered_results
        assert len(all_results) == 2

        scored_r = next(r for r in all_results if r["fit_score"] is not None)
        filtered_r = next(r for r in all_results if r["fit_score"] is None)

        assert 0 <= scored_r["fit_score"] <= 100
        assert 0 <= scored_r["stretch_score"] <= 100
        assert filtered_r["filtered_reason"] is not None


# =============================================================================
# Stretch Score Tests (§7.5)
# =============================================================================


class TestStrategistStretchScore:
    """Tests for stretch score in Strategist per REQ-007 §7.5.

    Verifies that Stretch Score components (target role alignment, target
    skills exposure, growth trajectory) integrate correctly within the
    Strategist agent's scoring flow.
    """

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

    # -----------------------------------------------------------------
    # Batch Scoring Stretch Integration — REQ-007 §7.5
    # -----------------------------------------------------------------
    # NOTE: Unit-level tests for individual stretch score functions
    # (calculate_target_role_alignment, calculate_target_skills_exposure,
    # calculate_growth_trajectory, calculate_stretch_score, interpret_stretch_score)
    # live in their dedicated test files:
    #   - test_target_role_alignment.py
    #   - test_target_skills_exposure.py
    #   - test_growth_trajectory.py
    #   - test_stretch_score_aggregation.py
    #   - test_stretch_score_interpretation.py
    #
    # Tests below focus on integration: how the Strategist graph
    # composes these functions via batch_score_jobs.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_batch_scoring_stretch_contains_three_components(self) -> None:
        """Stretch Score from batch scoring should contain all 3 components.

        REQ-008 §5.1: target_role (50%), target_skills (40%), growth (10%).
        """
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        stretch = results[0].stretch_score
        assert "target_role" in stretch.components
        assert "target_skills" in stretch.components
        assert "growth_trajectory" in stretch.components

        # Verify weights sum to 1.0
        weight_sum = sum(stretch.weights.values())
        assert abs(weight_sum - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_batch_scoring_stretch_maps_to_score_result(self) -> None:
        """Stretch score from batch scoring should map to ScoreResult.

        REQ-007 §7.5: build_scored_result should accept stretch_score total.
        """
        persona = _make_scoring_persona()
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        scored_job = results[0]
        score_result = build_scored_result(
            job_id=scored_job.job_id,
            fit_score=float(scored_job.fit_score.total),
            stretch_score=float(scored_job.stretch_score.total),
        )

        assert score_result["stretch_score"] == scored_job.stretch_score.total
        assert 0 <= score_result["stretch_score"] <= 100

    @pytest.mark.asyncio
    async def test_batch_scoring_persona_with_growth_targets(self) -> None:
        """Persona with specific growth targets should influence stretch score.

        REQ-007 §7.5: Target roles and skills drive stretch calculation.
        """
        persona = MockScoringPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard", "Expert")],
            years_experience=5,
            current_role="Software Engineer",
            target_roles=["Senior Software Engineer"],
            target_skills=["Kubernetes", "Terraform"],
        )
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()

        # Job that matches target role exactly and has one target skill
        job = MockScoringJobPosting(
            id=uuid.uuid4(),
            job_title="Senior Software Engineer",
            extracted_skills=[
                MockExtractedSkill("Python", "Hard"),
                MockExtractedSkill("Kubernetes", "Hard"),  # Matches target skill
            ],
        )

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        stretch = results[0].stretch_score
        # Target role exact match → 100
        assert stretch.components["target_role"] == 100.0
        # 1 target skill match → 50
        assert stretch.components["target_skills"] == 50.0
        # mid → senior = step up → 100
        assert stretch.components["growth_trajectory"] == 100.0

    @pytest.mark.asyncio
    async def test_batch_scoring_no_growth_targets_returns_neutral(self) -> None:
        """Persona without growth targets should get neutral stretch scores.

        REQ-008 §5.2, §5.3: Missing targets = neutral (50).
        """
        persona = MockScoringPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard", "Expert")],
            years_experience=5,
            current_role="Software Engineer",
            target_roles=[],
            target_skills=[],
        )
        embeddings = _make_scoring_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()
        job = _make_scoring_job()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=embeddings,
            embedding_provider=provider,
        )

        stretch = results[0].stretch_score
        # No target roles → neutral
        assert stretch.components["target_role"] == STRETCH_NEUTRAL_SCORE
        # No target skills → neutral
        assert stretch.components["target_skills"] == STRETCH_NEUTRAL_SCORE


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
        persona = MockFilterPersona(remote_preference="Remote Only")
        job = MockFilterJob(id=uuid.uuid4(), work_model="Onsite")

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
        persona = MockFilterPersona(
            remote_preference="Hybrid OK",
            minimum_base_salary=100000,
        )
        job = MockFilterJob(
            id=uuid.uuid4(),
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
        persona = MockFilterPersona(minimum_base_salary=150000)
        job = MockFilterJob(id=uuid.uuid4(), work_model="Remote", salary_max=100000)

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "Salary" in score_result["filtered_reason"]

    def test_node_filters_job_in_excluded_industry(self) -> None:
        """Node should filter job in excluded industry."""
        persona = MockFilterPersona(industry_exclusions=["Gambling", "Tobacco"])
        job = MockFilterJob(id=uuid.uuid4(), work_model="Remote", industry="Gambling")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "Gambling" in score_result["filtered_reason"]

    def test_node_aggregates_multiple_filter_failures(self) -> None:
        """Node should aggregate multiple non-negotiables failures."""
        persona = MockFilterPersona(
            remote_preference="Remote Only",
            minimum_base_salary=200000,
            industry_exclusions=["Gambling"],
            visa_sponsorship_required=True,
        )
        job = MockFilterJob(
            id=uuid.uuid4(),
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
        persona = MockFilterPersona(minimum_base_salary=100000)
        job = MockFilterJob(id=uuid.uuid4(), work_model="Remote")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is True
        assert any("Salary" in w for w in filter_result.warnings)

    def test_node_filters_job_requiring_visa_sponsorship(self) -> None:
        """Node should filter job when visa required but not offered."""
        persona = MockFilterPersona(visa_sponsorship_required=True)
        job = MockFilterJob(
            id=uuid.uuid4(), work_model="Remote", visa_sponsorship=False
        )

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "sponsorship" in score_result["filtered_reason"].lower()

    def test_node_filters_job_in_non_commutable_city(self) -> None:
        """Node should filter onsite job in non-commutable city."""
        persona = MockFilterPersona(
            remote_preference="Onsite OK",
            commutable_cities=["San Francisco", "Oakland"],
        )
        job = MockFilterJob(id=uuid.uuid4(), work_model="Onsite", location="New York")

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is False

        score_result = build_filtered_score_result(filter_result)
        assert "commutable" in score_result["filtered_reason"].lower()

    def test_node_passes_remote_job_regardless_of_location(self) -> None:
        """Remote jobs should pass commutable cities check regardless of location."""
        persona = MockFilterPersona(
            remote_preference="Hybrid OK",
            commutable_cities=["San Francisco"],
        )
        job = MockFilterJob(id=uuid.uuid4(), work_model="Remote", location="Tokyo")

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
        persona = MockFilterPersona(remote_preference="Remote Only")

        job1 = MockFilterJob(id=uuid.uuid4(), work_model="Remote")
        job2 = MockFilterJob(id=uuid.uuid4(), work_model="Onsite")
        job3 = MockFilterJob(id=uuid.uuid4(), work_model="Remote")

        passing, filtered = filter_jobs_batch(persona, [job1, job2, job3])

        assert len(passing) == 2
        assert len(filtered) == 1
        assert passing[0].id == job1.id
        assert passing[1].id == job3.id
        assert filtered[0].job_id == job2.id

    def test_filtered_results_contain_failure_reasons(self) -> None:
        """Filtered results should contain descriptive failure reasons."""
        persona = MockFilterPersona(
            remote_preference="Remote Only",
            minimum_base_salary=100000,
        )
        job = MockFilterJob(id=uuid.uuid4(), work_model="Onsite", salary_max=50000)

        _, filtered = filter_jobs_batch(persona, [job])

        assert len(filtered) == 1
        assert len(filtered[0].failed_reasons) >= 2
        reasons_text = " ".join(filtered[0].failed_reasons)
        assert "Remote" in reasons_text or "Onsite" in reasons_text
        assert "Salary" in reasons_text or "salary" in reasons_text

    def test_state_output_includes_filtered_jobs_list(self) -> None:
        """Output state should track filtered job IDs separately."""
        persona = MockFilterPersona(remote_preference="Remote Only")
        jobs = [MockFilterJob(id=uuid.uuid4(), work_model="Onsite") for _ in range(3)]

        _, filtered = filter_jobs_batch(persona, jobs)

        filtered_job_ids = [str(f.job_id) for f in filtered]

        assert len(filtered_job_ids) == 3
        assert len(set(filtered_job_ids)) == 3

    def test_score_results_built_correctly_for_filtered_jobs(self) -> None:
        """ScoreResults for filtered jobs should have correct structure."""
        persona = MockFilterPersona(
            remote_preference="Remote Only",
            industry_exclusions=["Gambling"],
        )
        job = MockFilterJob(id=uuid.uuid4(), work_model="Onsite", industry="Gambling")

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
        persona = MockFilterPersona(remote_preference="Remote Only")

        passing, filtered = filter_jobs_batch(persona, [])

        assert len(passing) == 0
        assert len(filtered) == 0


# =============================================================================
# Graph Structure Tests (§15.4)
# =============================================================================


class TestStrategistGraphStructure:
    """Tests for Strategist graph structure per REQ-007 §15.4."""

    def test_graph_has_ten_nodes(self) -> None:
        """Graph should have exactly 10 nodes per §15.4 spec."""
        graph = create_strategist_graph()
        compiled = graph.compile()
        node_names = set(compiled.get_graph().nodes.keys())
        # LangGraph adds __start__ and __end__ nodes automatically
        non_internal = {n for n in node_names if not n.startswith("__")}

        expected_nodes = {
            "load_persona_embeddings",
            "check_embedding_freshness",
            "regenerate_embeddings",
            "filter_non_negotiables",
            "generate_job_embeddings",
            "calculate_fit_score",
            "calculate_stretch_score",
            "generate_rationale",
            "save_scores",
            "trigger_ghostwriter",
        }

        assert non_internal == expected_nodes

    def test_entry_point_is_load_persona_embeddings(self) -> None:
        """Entry point should be load_persona_embeddings per §15.4."""
        graph = create_strategist_graph()
        compiled = graph.compile()
        graph_repr = compiled.get_graph()
        # __start__ should connect to load_persona_embeddings
        start_edges = [e.target for e in graph_repr.edges if e.source == "__start__"]

        assert "load_persona_embeddings" in start_edges

    def test_graph_compiles_without_error(self) -> None:
        """Graph should compile successfully."""
        graph = create_strategist_graph()
        compiled = graph.compile()

        assert compiled is not None

    def test_singleton_pattern_returns_same_instance(self) -> None:
        """get_strategist_graph should return same instance on repeated calls."""
        reset_strategist_graph()
        graph1 = get_strategist_graph()
        graph2 = get_strategist_graph()

        assert graph1 is graph2

        reset_strategist_graph()

    def test_reset_clears_singleton(self) -> None:
        """reset_strategist_graph should clear the singleton."""
        reset_strategist_graph()
        graph1 = get_strategist_graph()
        reset_strategist_graph()
        graph2 = get_strategist_graph()

        assert graph1 is not graph2

        reset_strategist_graph()


# =============================================================================
# Routing Function Tests (§15.4)
# =============================================================================


class TestIsEmbeddingStale:
    """Tests for is_embedding_stale routing function."""

    def test_stale_when_embeddings_stale_true(self) -> None:
        """Should return 'stale' when embeddings_stale is True."""
        state: StrategistState = {"embeddings_stale": True}
        assert is_embedding_stale(state) == "stale"

    def test_fresh_when_embeddings_stale_false(self) -> None:
        """Should return 'fresh' when embeddings_stale is False."""
        state: StrategistState = {"embeddings_stale": False}
        assert is_embedding_stale(state) == "fresh"

    def test_fresh_when_embeddings_stale_missing(self) -> None:
        """Should return 'fresh' when embeddings_stale not in state."""
        state: StrategistState = {}
        assert is_embedding_stale(state) == "fresh"


class TestCheckNonNegotiablesPass:
    """Tests for check_non_negotiables_pass routing function."""

    def test_pass_when_non_negotiables_passed_true(self) -> None:
        """Should return 'pass' when non_negotiables_passed is True."""
        state: StrategistState = {"non_negotiables_passed": True}
        assert check_non_negotiables_pass(state) == "pass"

    def test_fail_when_non_negotiables_passed_false(self) -> None:
        """Should return 'fail' when non_negotiables_passed is False."""
        state: StrategistState = {"non_negotiables_passed": False}
        assert check_non_negotiables_pass(state) == "fail"

    def test_fail_when_non_negotiables_passed_missing(self) -> None:
        """Should return 'fail' when non_negotiables_passed not in state."""
        state: StrategistState = {}
        assert check_non_negotiables_pass(state) == "fail"


class TestCheckAutoDraftThreshold:
    """Tests for check_auto_draft_threshold routing function."""

    def test_above_threshold_when_fit_score_exceeds(self) -> None:
        """Should return 'above_threshold' when fit_score >= threshold."""
        state: StrategistState = {
            "score_result": {"fit_score": 92.0},
            "auto_draft_threshold": 90,
        }
        assert check_auto_draft_threshold(state) == "above_threshold"

    def test_below_threshold_when_fit_score_below(self) -> None:
        """Should return 'below_threshold' when fit_score < threshold."""
        state: StrategistState = {
            "score_result": {"fit_score": 75.0},
            "auto_draft_threshold": 90,
        }
        assert check_auto_draft_threshold(state) == "below_threshold"

    def test_above_threshold_when_exactly_at_threshold(self) -> None:
        """Should return 'above_threshold' when fit_score == threshold."""
        state: StrategistState = {
            "score_result": {"fit_score": 90.0},
            "auto_draft_threshold": 90,
        }
        assert check_auto_draft_threshold(state) == "above_threshold"

    def test_below_threshold_when_no_threshold_set(self) -> None:
        """Should return 'below_threshold' when auto_draft_threshold is None."""
        state: StrategistState = {
            "score_result": {"fit_score": 95.0},
            "auto_draft_threshold": None,
        }
        assert check_auto_draft_threshold(state) == "below_threshold"

    def test_below_threshold_when_no_score_result(self) -> None:
        """Should return 'below_threshold' when score_result is None."""
        state: StrategistState = {
            "score_result": None,
            "auto_draft_threshold": 90,
        }
        assert check_auto_draft_threshold(state) == "below_threshold"

    def test_below_threshold_when_fit_score_is_none(self) -> None:
        """Should return 'below_threshold' when fit_score is None (filtered job)."""
        state: StrategistState = {
            "score_result": {"fit_score": None},
            "auto_draft_threshold": 90,
        }
        assert check_auto_draft_threshold(state) == "below_threshold"


# =============================================================================
# Node Function Tests (§15.4)
# =============================================================================


class TestLoadPersonaEmbeddingsNode:
    """Tests for load_persona_embeddings_node."""

    @pytest.mark.asyncio
    async def test_sets_persona_embeddings_in_state(self) -> None:
        """Node should set persona_embeddings dict in state."""
        state: StrategistState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
        }
        result = await load_persona_embeddings_node(state)

        assert "persona_embeddings" in result
        assert isinstance(result["persona_embeddings"], dict)

    @pytest.mark.asyncio
    async def test_preserves_existing_state(self) -> None:
        """Node should preserve existing state fields."""
        state: StrategistState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "current_job_id": "job-1",
        }
        result = await load_persona_embeddings_node(state)

        assert result["user_id"] == "user-1"
        assert result["persona_id"] == "persona-1"
        assert result["current_job_id"] == "job-1"


class TestCheckEmbeddingFreshnessNode:
    """Tests for check_embedding_freshness_node."""

    @pytest.mark.asyncio
    async def test_sets_embeddings_stale_flag(self) -> None:
        """Node should set embeddings_stale flag in state."""
        state: StrategistState = {
            "persona_id": "persona-1",
            "persona_embedding_version": 0,
        }
        result = await check_embedding_freshness_node(state)

        assert "embeddings_stale" in result
        assert isinstance(result["embeddings_stale"], bool)

    @pytest.mark.asyncio
    async def test_fresh_when_versions_match(self) -> None:
        """Node should set embeddings_stale=False when versions match."""
        state: StrategistState = {
            "persona_id": "persona-1",
            "persona_embedding_version": 5,
        }
        result = await check_embedding_freshness_node(state)

        assert result["embeddings_stale"] is False


class TestRegenerateEmbeddingsNode:
    """Tests for regenerate_embeddings_node."""

    @pytest.mark.asyncio
    async def test_clears_stale_flag(self) -> None:
        """Node should set embeddings_stale to False."""
        state: StrategistState = {
            "persona_id": "persona-1",
            "persona_embedding_version": 3,
            "embeddings_stale": True,
        }
        result = await regenerate_embeddings_node(state)

        assert result["embeddings_stale"] is False

    @pytest.mark.asyncio
    async def test_increments_version(self) -> None:
        """Node should increment persona_embedding_version."""
        state: StrategistState = {
            "persona_id": "persona-1",
            "persona_embedding_version": 3,
            "embeddings_stale": True,
        }
        result = await regenerate_embeddings_node(state)

        assert result["persona_embedding_version"] == 4


class TestFilterNonNegotiablesNode:
    """Tests for filter_non_negotiables_node."""

    @pytest.mark.asyncio
    async def test_sets_non_negotiables_passed(self) -> None:
        """Node should set non_negotiables_passed flag."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "persona_id": "persona-1",
        }
        result = await filter_non_negotiables_node(state)

        assert "non_negotiables_passed" in result
        assert isinstance(result["non_negotiables_passed"], bool)

    @pytest.mark.asyncio
    async def test_placeholder_assumes_pass(self) -> None:
        """Placeholder implementation should assume job passes."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "persona_id": "persona-1",
        }
        result = await filter_non_negotiables_node(state)

        assert result["non_negotiables_passed"] is True
        assert result.get("non_negotiables_reason") is None


class TestGenerateJobEmbeddingsNode:
    """Tests for generate_job_embeddings_node."""

    @pytest.mark.asyncio
    async def test_sets_job_embeddings(self) -> None:
        """Node should set job_embeddings dict in state."""
        state: StrategistState = {
            "current_job_id": "job-1",
        }
        result = await generate_job_embeddings_node(state)

        assert "job_embeddings" in result
        assert isinstance(result["job_embeddings"], dict)


class TestCalculateFitScoreNode:
    """Tests for calculate_fit_score_node."""

    @pytest.mark.asyncio
    async def test_sets_fit_result(self) -> None:
        """Node should set fit_result in state."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "persona_embeddings": {},
            "job_embeddings": {},
        }
        result = await calculate_fit_score_node(state)

        assert "fit_result" in result


class TestCalculateStretchScoreNode:
    """Tests for calculate_stretch_score_node."""

    @pytest.mark.asyncio
    async def test_sets_stretch_result(self) -> None:
        """Node should set stretch_result in state."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "persona_embeddings": {},
            "job_embeddings": {},
        }
        result = await calculate_stretch_score_node(state)

        assert "stretch_result" in result


class TestGenerateRationaleNode:
    """Tests for generate_rationale_node."""

    @pytest.mark.asyncio
    async def test_sets_rationale(self) -> None:
        """Node should set rationale in state."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "fit_result": None,
            "stretch_result": None,
        }
        result = await generate_rationale_node(state)

        assert "rationale" in result


class TestSaveScoresNode:
    """Tests for save_scores_node."""

    @pytest.mark.asyncio
    async def test_assembles_score_result_for_passing_job(self) -> None:
        """Node should assemble ScoreResult from pipeline state fields."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "non_negotiables_passed": True,
            "non_negotiables_reason": None,
            "fit_result": {"total": 85.0},
            "stretch_result": {"total": 72.0},
            "rationale": "Strong technical match.",
        }
        result = await save_scores_node(state)

        assert result["score_result"] is not None
        assert result["score_result"]["job_posting_id"] == "job-1"
        assert result["score_result"]["fit_score"] == 85.0
        assert result["score_result"]["stretch_score"] == 72.0
        assert result["score_result"]["explanation"] == "Strong technical match."
        assert result["score_result"]["filtered_reason"] is None

    @pytest.mark.asyncio
    async def test_assembles_score_result_for_filtered_job(self) -> None:
        """Node should store filter reason when job failed non-negotiables."""
        state: StrategistState = {
            "current_job_id": "job-2",
            "non_negotiables_passed": False,
            "non_negotiables_reason": "salary_below_minimum",
            "fit_result": None,
            "stretch_result": None,
            "rationale": None,
        }
        result = await save_scores_node(state)

        assert result["score_result"] is not None
        assert result["score_result"]["job_posting_id"] == "job-2"
        assert result["score_result"]["fit_score"] is None
        assert result["score_result"]["stretch_score"] is None
        assert result["score_result"]["filtered_reason"] == "salary_below_minimum"

    @pytest.mark.asyncio
    async def test_handles_none_fit_stretch_results(self) -> None:
        """Node should handle None fit/stretch results gracefully."""
        state: StrategistState = {
            "current_job_id": "job-3",
            "non_negotiables_passed": True,
            "non_negotiables_reason": None,
            "fit_result": None,
            "stretch_result": None,
            "rationale": None,
        }
        result = await save_scores_node(state)

        assert result["score_result"]["fit_score"] is None
        assert result["score_result"]["stretch_score"] is None


class TestTriggerGhostwriterNode:
    """Tests for trigger_ghostwriter_node."""

    @pytest.mark.asyncio
    async def test_returns_state_unchanged(self) -> None:
        """Placeholder node should return state with no modifications."""
        state: StrategistState = {
            "current_job_id": "job-1",
            "score_result": {
                "job_posting_id": "job-1",
                "fit_score": 95.0,
                "stretch_score": 80.0,
                "explanation": "Excellent match.",
                "filtered_reason": None,
            },
        }
        result = await trigger_ghostwriter_node(state)

        assert result["current_job_id"] == state["current_job_id"]
        assert result["score_result"] == state["score_result"]


# =============================================================================
# Convenience Function Tests (§15.4)
# =============================================================================


class TestScoreJobsConvenience:
    """Tests for score_jobs convenience function."""

    @pytest.mark.asyncio
    async def test_invokes_graph_per_job(self) -> None:
        """score_jobs should invoke graph once per job ID."""
        mock_result: ScoreResult = {
            "job_posting_id": "job-1",
            "fit_score": 80.0,
            "stretch_score": 60.0,
            "explanation": None,
            "filtered_reason": None,
        }
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"score_result": mock_result}

        with patch(
            "app.agents.strategist_graph.get_strategist_graph",
            return_value=mock_graph,
        ):
            results = await score_jobs(
                user_id="user-1",
                persona_id="persona-1",
                job_ids=["job-1", "job-2", "job-3"],
            )

        assert mock_graph.ainvoke.call_count == 3
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_empty_job_list_returns_empty(self) -> None:
        """score_jobs with empty job_ids should return empty list."""
        results = await score_jobs(
            user_id="user-1",
            persona_id="persona-1",
            job_ids=[],
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_rejects_empty_user_id(self) -> None:
        """score_jobs should reject empty user_id."""
        with pytest.raises(ValueError, match="user_id and persona_id are required"):
            await score_jobs(user_id="", persona_id="persona-1", job_ids=["job-1"])

    @pytest.mark.asyncio
    async def test_rejects_empty_persona_id(self) -> None:
        """score_jobs should reject empty persona_id."""
        with pytest.raises(ValueError, match="user_id and persona_id are required"):
            await score_jobs(user_id="user-1", persona_id="", job_ids=["job-1"])

    @pytest.mark.asyncio
    async def test_rejects_oversized_batch(self) -> None:
        """score_jobs should reject batches exceeding _MAX_SCORE_JOBS."""
        job_ids = [f"job-{i}" for i in range(501)]
        with pytest.raises(ValueError, match="exceeds maximum"):
            await score_jobs(user_id="user-1", persona_id="persona-1", job_ids=job_ids)

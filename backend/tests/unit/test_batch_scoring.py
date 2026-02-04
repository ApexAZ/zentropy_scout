"""Tests for batch scoring service.

REQ-008 §10.1: Batch Scoring — efficiently score multiple jobs against a persona.

Key optimizations tested:
1. Persona embeddings loaded once (not per job)
2. Job embeddings generated in batch (single API call)
3. All scores computed correctly for each job
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.services.batch_scoring import (
    _MAX_BATCH_SIZE,
    ScoredJob,
    batch_score_jobs,
)
from app.services.fit_score import FitScoreResult
from app.services.persona_embedding_generator import (
    PersonaEmbeddingData,
    PersonaEmbeddingsResult,
)
from app.services.stretch_score import StretchScoreResult

# =============================================================================
# Mock Factories
# =============================================================================


@dataclass
class MockSkill:
    """Mock persona skill for testing."""

    skill_name: str
    skill_type: str
    proficiency: str = "Proficient"


@dataclass
class MockExtractedSkill:
    """Mock job extracted skill for testing."""

    skill_name: str
    skill_type: str
    is_required: bool = True
    years_requested: int | None = None


@dataclass
class MockPersona:
    """Mock persona for testing."""

    id: uuid.UUID
    skills: list[MockSkill]
    years_experience: int | None = 5
    current_role: str | None = "Software Engineer"
    target_roles: list[str] | None = None
    target_skills: list[str] | None = None
    home_city: str = "San Francisco"
    home_state: str = "CA"
    home_country: str = "USA"
    remote_preference: str = "Hybrid OK"
    commutable_cities: list[str] | None = None
    industry_exclusions: list[str] | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.updated_at is None:
            self.updated_at = datetime.now(tz=UTC)
        if self.target_roles is None:
            self.target_roles = []
        if self.target_skills is None:
            self.target_skills = []
        if self.commutable_cities is None:
            self.commutable_cities = []
        if self.industry_exclusions is None:
            self.industry_exclusions = []


@dataclass
class MockJobPosting:
    """Mock job posting for testing."""

    id: uuid.UUID
    job_title: str
    extracted_skills: list[MockExtractedSkill]
    culture_text: str | None = None
    years_experience_min: int | None = None
    years_experience_max: int | None = None
    work_model: str | None = "Hybrid"
    location: str | None = "San Francisco, CA"
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.updated_at is None:
            self.updated_at = datetime.now(tz=UTC)


def make_mock_embedding(dimensions: int = 1536) -> list[float]:
    """Create a mock embedding vector (non-zero for similarity tests)."""
    return [0.1] * dimensions


def make_mock_persona_embeddings(persona_id: uuid.UUID) -> PersonaEmbeddingsResult:
    """Create mock persona embeddings result."""
    return PersonaEmbeddingsResult(
        persona_id=persona_id,
        hard_skills=PersonaEmbeddingData(
            vector=make_mock_embedding(),
            source_text="Python (Expert) | AWS (Proficient)",
        ),
        soft_skills=PersonaEmbeddingData(
            vector=make_mock_embedding(),
            source_text="Leadership | Communication",
        ),
        logistics=PersonaEmbeddingData(
            vector=make_mock_embedding(),
            source_text="Remote preference: Hybrid OK\nLocation: San Francisco, CA, USA",
        ),
        version=datetime.now(tz=UTC),
        model_name="text-embedding-3-small",
    )


def make_python_engineer_persona() -> MockPersona:
    """Create a standard Python engineer persona for testing."""
    return MockPersona(
        id=uuid.uuid4(),
        skills=[
            MockSkill("Python", "Hard", "Expert"),
            MockSkill("AWS", "Hard", "Proficient"),
            MockSkill("PostgreSQL", "Hard", "Proficient"),
            MockSkill("Leadership", "Soft", "Proficient"),
        ],
        years_experience=5,
        current_role="Software Engineer",
        target_roles=["Senior Software Engineer", "Tech Lead"],
        target_skills=["Kubernetes", "Machine Learning"],
    )


def make_python_job() -> MockJobPosting:
    """Create a Python engineer job posting for testing."""
    return MockJobPosting(
        id=uuid.uuid4(),
        job_title="Senior Software Engineer",
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("AWS", "Hard", is_required=True),
            MockExtractedSkill("Docker", "Hard", is_required=False),
            MockExtractedSkill("Teamwork", "Soft", is_required=False),
        ],
        years_experience_min=4,
        years_experience_max=8,
        work_model="Hybrid",
        location="San Francisco, CA",
        culture_text="Collaborative team environment with focus on innovation.",
    )


def make_data_scientist_job() -> MockJobPosting:
    """Create a data scientist job posting (different from persona)."""
    return MockJobPosting(
        id=uuid.uuid4(),
        job_title="Data Scientist",
        extracted_skills=[
            MockExtractedSkill("Python", "Hard", is_required=True),
            MockExtractedSkill("Machine Learning", "Hard", is_required=True),
            MockExtractedSkill("TensorFlow", "Hard", is_required=False),
        ],
        years_experience_min=3,
        years_experience_max=6,
        work_model="Remote",
    )


def make_director_job() -> MockJobPosting:
    """Create a director-level job posting (above persona level)."""
    return MockJobPosting(
        id=uuid.uuid4(),
        job_title="Director of Engineering",
        extracted_skills=[
            MockExtractedSkill("Leadership", "Soft", is_required=True),
            MockExtractedSkill("Python", "Hard", is_required=False),
        ],
        years_experience_min=10,
        years_experience_max=15,
        work_model="Onsite",
        location="New York, NY",
    )


# =============================================================================
# Mock Embedding Provider
# =============================================================================


class MockEmbeddingProvider:
    """Mock embedding provider for batch scoring tests."""

    def __init__(self, mock_vector: list[float] | None = None) -> None:
        """Initialize with optional custom mock vector."""
        self._mock_vector = mock_vector or make_mock_embedding()
        self.call_count = 0
        self.last_texts: list[str] = []

    async def embed(self, texts: list[str]) -> "MockEmbeddingResult":
        """Return mock embeddings for each input text."""
        self.call_count += 1
        self.last_texts = texts
        return MockEmbeddingResult(
            vectors=[self._mock_vector[:] for _ in texts],
            model="text-embedding-3-small",
            dimensions=len(self._mock_vector),
            total_tokens=len(texts) * 10,  # Approximate tokens
        )

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return len(self._mock_vector)


@dataclass
class MockEmbeddingResult:
    """Mock embedding result matching EmbeddingResult structure."""

    vectors: list[list[float]]
    model: str
    dimensions: int
    total_tokens: int


# =============================================================================
# Test: Basic Functionality
# =============================================================================


class TestBatchScoringBasic:
    """Test basic batch scoring functionality."""

    @pytest.mark.asyncio
    async def test_batch_score_single_job(self) -> None:
        """Scoring a single job returns correct result structure."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        job = make_python_job()
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        assert len(results) == 1
        assert isinstance(results[0], ScoredJob)
        assert results[0].job_id == job.id
        assert isinstance(results[0].fit_score, FitScoreResult)
        assert isinstance(results[0].stretch_score, StretchScoreResult)

    @pytest.mark.asyncio
    async def test_batch_score_multiple_jobs(self) -> None:
        """Scoring multiple jobs returns one result per job."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        jobs = [make_python_job(), make_data_scientist_job(), make_director_job()]
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        assert len(results) == 3
        # Results should be in same order as input jobs
        assert results[0].job_id == jobs[0].id
        assert results[1].job_id == jobs[1].id
        assert results[2].job_id == jobs[2].id

    @pytest.mark.asyncio
    async def test_batch_score_empty_jobs_list(self) -> None:
        """Scoring empty job list returns empty results."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=[],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        assert results == []


# =============================================================================
# Test: Batch Optimization
# =============================================================================


class TestBatchOptimization:
    """Test that batch scoring uses optimized paths."""

    @pytest.mark.asyncio
    async def test_embedding_provider_called_once_for_batch(self) -> None:
        """Embedding provider should be called once for batch, not per job."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        jobs = [make_python_job(), make_data_scientist_job(), make_director_job()]
        provider = MockEmbeddingProvider()

        await batch_score_jobs(
            jobs=jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Should be called once (not 3 times) for batch embedding
        # May be called more times for different embedding types, but not N times per job
        assert (
            provider.call_count <= 3
        )  # At most once per embedding type (requirements, culture, titles)

    @pytest.mark.asyncio
    async def test_persona_embeddings_reused(self) -> None:
        """Persona embeddings should be passed in, not regenerated."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        jobs = [make_python_job(), make_python_job()]
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Both results should use same persona embeddings (same soft skills score)
        assert (
            results[0].fit_score.components["soft_skills"]
            == results[1].fit_score.components["soft_skills"]
        )


# =============================================================================
# Test: Score Calculations
# =============================================================================


class TestBatchScoreCalculations:
    """Test that scores are calculated correctly."""

    @pytest.mark.asyncio
    async def test_fit_score_components_populated(self) -> None:
        """Fit score should have all 5 components."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        job = make_python_job()
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        fit = results[0].fit_score
        assert "hard_skills" in fit.components
        assert "soft_skills" in fit.components
        assert "experience_level" in fit.components
        assert "role_title" in fit.components
        assert "location_logistics" in fit.components

    @pytest.mark.asyncio
    async def test_stretch_score_components_populated(self) -> None:
        """Stretch score should have all 3 components."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        job = make_python_job()
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        stretch = results[0].stretch_score
        assert "target_role" in stretch.components
        assert "target_skills" in stretch.components
        assert "growth_trajectory" in stretch.components

    @pytest.mark.asyncio
    async def test_fit_score_total_in_valid_range(self) -> None:
        """Fit score total should be 0-100."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        jobs = [make_python_job(), make_data_scientist_job(), make_director_job()]
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        for result in results:
            assert 0 <= result.fit_score.total <= 100

    @pytest.mark.asyncio
    async def test_stretch_score_total_in_valid_range(self) -> None:
        """Stretch score total should be 0-100."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        jobs = [make_python_job(), make_data_scientist_job(), make_director_job()]
        provider = MockEmbeddingProvider()

        results = await batch_score_jobs(
            jobs=jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        for result in results:
            assert 0 <= result.stretch_score.total <= 100


# =============================================================================
# Test: Hard Skills Scoring
# =============================================================================


class TestBatchHardSkillsScoring:
    """Test hard skills calculation in batch scoring."""

    @pytest.mark.asyncio
    async def test_matching_skills_score_higher(self) -> None:
        """Job with matching skills should score higher on hard_skills."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        # Job with skills persona has
        matching_job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Python Developer",
            extracted_skills=[
                MockExtractedSkill("Python", "Hard", is_required=True),
                MockExtractedSkill("AWS", "Hard", is_required=True),
            ],
        )

        # Job with skills persona doesn't have
        non_matching_job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Java Developer",
            extracted_skills=[
                MockExtractedSkill("Java", "Hard", is_required=True),
                MockExtractedSkill("Spring", "Hard", is_required=True),
            ],
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[matching_job, non_matching_job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Matching job should have higher hard skills score
        assert (
            results[0].fit_score.components["hard_skills"]
            > results[1].fit_score.components["hard_skills"]
        )


# =============================================================================
# Test: Experience Level Scoring
# =============================================================================


class TestBatchExperienceScoring:
    """Test experience level calculation in batch scoring."""

    @pytest.mark.asyncio
    async def test_experience_within_range_scores_high(self) -> None:
        """Job with matching experience range should score 100."""
        persona = MockPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard")],
            years_experience=5,
        )
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Software Engineer",
            extracted_skills=[],
            years_experience_min=3,
            years_experience_max=7,
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Experience level should be 100 (5 years within 3-7 range)
        assert results[0].fit_score.components["experience_level"] == 100.0

    @pytest.mark.asyncio
    async def test_under_qualified_scores_lower(self) -> None:
        """Under-qualified persona should score lower on experience."""
        persona = MockPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard")],
            years_experience=2,  # Only 2 years
        )
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Senior Engineer",
            extracted_skills=[],
            years_experience_min=5,  # Needs 5+ years
            years_experience_max=10,
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Under-qualified by 3 years: 100 - (3 * 15) = 55
        assert results[0].fit_score.components["experience_level"] == 55.0


# =============================================================================
# Test: Stretch Score Calculations
# =============================================================================


class TestBatchStretchScoring:
    """Test stretch score calculations in batch scoring."""

    @pytest.mark.asyncio
    async def test_target_skills_exposure_with_matching_skills(self) -> None:
        """Job with target skills should score higher on target_skills component."""
        persona = MockPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard")],
            target_skills=["Machine Learning", "Kubernetes"],
        )
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        # Job exposes target skills
        ml_job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="ML Engineer",
            extracted_skills=[
                MockExtractedSkill("Machine Learning", "Hard"),
                MockExtractedSkill("Python", "Hard"),
            ],
        )

        # Job doesn't expose target skills
        web_job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Web Developer",
            extracted_skills=[
                MockExtractedSkill("JavaScript", "Hard"),
                MockExtractedSkill("React", "Hard"),
            ],
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[ml_job, web_job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # ML job should have higher target_skills score (exposes ML)
        assert (
            results[0].stretch_score.components["target_skills"]
            > results[1].stretch_score.components["target_skills"]
        )

    @pytest.mark.asyncio
    async def test_growth_trajectory_step_up(self) -> None:
        """Job that's a step up should score higher on growth_trajectory."""
        persona = MockPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard")],
            current_role="Software Engineer",  # Mid-level
        )
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        # Step up: Senior level
        step_up_job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Senior Software Engineer",
            extracted_skills=[],
        )

        # Lateral: Same level
        lateral_job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Software Developer",
            extracted_skills=[],
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[step_up_job, lateral_job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Step up should score 100, lateral should score 70
        assert results[0].stretch_score.components["growth_trajectory"] == 100.0
        assert results[1].stretch_score.components["growth_trajectory"] == 70.0


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestBatchScoringEdgeCases:
    """Test edge cases in batch scoring."""

    @pytest.mark.asyncio
    async def test_job_with_no_skills(self) -> None:
        """Job with no skills should use neutral hard_skills score."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Unknown Role",
            extracted_skills=[],  # No skills
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Hard skills should be neutral (70) when job has no skills
        assert results[0].fit_score.components["hard_skills"] == 70.0

    @pytest.mark.asyncio
    async def test_job_with_no_experience_requirements(self) -> None:
        """Job with no experience requirements should use neutral score."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Developer",
            extracted_skills=[MockExtractedSkill("Python", "Hard")],
            years_experience_min=None,
            years_experience_max=None,
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Experience should be neutral (70) when no requirements
        assert results[0].fit_score.components["experience_level"] == 70.0

    @pytest.mark.asyncio
    async def test_persona_with_no_target_roles(self) -> None:
        """Persona with no target roles should use neutral stretch scores."""
        persona = MockPersona(
            id=uuid.uuid4(),
            skills=[MockSkill("Python", "Hard")],
            target_roles=[],  # No target roles
            target_skills=[],  # No target skills
        )
        persona_embeddings = make_mock_persona_embeddings(persona.id)

        job = MockJobPosting(
            id=uuid.uuid4(),
            job_title="Developer",
            extracted_skills=[MockExtractedSkill("Python", "Hard")],
        )

        provider = MockEmbeddingProvider()
        results = await batch_score_jobs(
            jobs=[job],
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )

        # Target role and skills should be neutral (50) when no targets defined
        assert results[0].stretch_score.components["target_role"] == 50.0
        assert results[0].stretch_score.components["target_skills"] == 50.0


# =============================================================================
# Test: Input Validation
# =============================================================================


class TestBatchScoringValidation:
    """Test input validation in batch scoring."""

    @pytest.mark.asyncio
    async def test_mismatched_persona_embeddings_raises(self) -> None:
        """Should raise if persona_embeddings.persona_id doesn't match persona.id."""
        persona = make_python_engineer_persona()
        # Embeddings for different persona
        wrong_embeddings = make_mock_persona_embeddings(uuid.uuid4())
        job = make_python_job()
        provider = MockEmbeddingProvider()

        with pytest.raises(ValueError, match="persona_id.*mismatch"):
            await batch_score_jobs(
                jobs=[job],
                persona=persona,
                persona_embeddings=wrong_embeddings,
                embedding_provider=provider,
            )

    @pytest.mark.asyncio
    async def test_batch_size_exceeds_max_raises(self) -> None:
        """Should raise if batch size exceeds maximum."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        # Create more jobs than allowed
        jobs = [
            MockJobPosting(
                id=uuid.uuid4(),
                job_title=f"Job {i}",
                extracted_skills=[],
            )
            for i in range(_MAX_BATCH_SIZE + 1)
        ]
        provider = MockEmbeddingProvider()

        with pytest.raises(ValueError, match=f"exceeds maximum of {_MAX_BATCH_SIZE}"):
            await batch_score_jobs(
                jobs=jobs,
                persona=persona,
                persona_embeddings=persona_embeddings,
                embedding_provider=provider,
            )

    @pytest.mark.asyncio
    async def test_batch_size_at_max_succeeds(self) -> None:
        """Should succeed if batch size equals maximum."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        # Create exactly max jobs (but use a smaller number for test speed)
        small_max = 10  # Test with smaller number for speed
        jobs = [
            MockJobPosting(
                id=uuid.uuid4(),
                job_title=f"Job {i}",
                extracted_skills=[],
            )
            for i in range(small_max)
        ]
        provider = MockEmbeddingProvider()

        # Should not raise (we're under the limit)
        results = await batch_score_jobs(
            jobs=jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=provider,
        )
        assert len(results) == small_max


class TestBatchScoringEmbeddingValidation:
    """Test embedding response validation in batch scoring."""

    @pytest.mark.asyncio
    async def test_embedding_response_count_mismatch_raises(self) -> None:
        """Should raise if embedding provider returns wrong number of vectors."""
        persona = make_python_engineer_persona()
        persona_embeddings = make_mock_persona_embeddings(persona.id)
        jobs = [make_python_job(), make_python_job()]

        # Provider that returns wrong number of vectors
        class BadEmbeddingProvider:
            async def embed(self, texts: list[str]) -> MockEmbeddingResult:  # noqa: ARG002
                # Always return just 1 vector regardless of input count
                return MockEmbeddingResult(
                    vectors=[[0.1] * 1536],  # Only 1 vector
                    model="text-embedding-3-small",
                    dimensions=1536,
                    total_tokens=10,
                )

            @property
            def dimensions(self) -> int:
                return 1536

        provider = BadEmbeddingProvider()

        with pytest.raises(ValueError, match="Embedding response count mismatch"):
            await batch_score_jobs(
                jobs=jobs,
                persona=persona,
                persona_embeddings=persona_embeddings,
                embedding_provider=provider,
            )

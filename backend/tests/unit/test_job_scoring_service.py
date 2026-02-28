"""Tests for JobScoringService.

REQ-017 §6: Orchestrates non-negotiables filter + fit/stretch scoring +
rationale generation + score persistence.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.job_scoring_service import (
    RATIONALE_SCORE_THRESHOLD,
    JobScoringService,
)

# Module path for patching
_MODULE = "app.services.job_scoring_service"

# Patch targets (DRY — avoids repeating f"{_MODULE}.<name>" strings)
_PATCH_LOAD_PERSONA = f"{_MODULE}._load_persona"
_PATCH_LOAD_JOBS = f"{_MODULE}._load_jobs"
_PATCH_LOAD_DISCOVERED = f"{_MODULE}._load_discovered_job_ids"
_PATCH_GEN_EMBEDDINGS = f"{_MODULE}.generate_persona_embeddings"
_PATCH_FILTER_BATCH = f"{_MODULE}.filter_jobs_batch"
_PATCH_BATCH_SCORE = f"{_MODULE}.batch_score_jobs"
_PATCH_SAVE_SCORE = f"{_MODULE}._save_score"


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_persona(
    *,
    persona_id: UUID | None = None,
    user_id: UUID | None = None,
    skills: list | None = None,
    years_experience: int = 5,
    current_role: str = "Software Engineer",
    target_roles: list[str] | None = None,
    target_skills: list[str] | None = None,
    remote_preference: str = "No Preference",
    commutable_cities: list[str] | None = None,
    minimum_base_salary: int | None = None,
    industry_exclusions: list[str] | None = None,
    visa_sponsorship_required: bool = False,
    auto_draft_threshold: int = 90,
) -> MagicMock:
    """Create a mock Persona ORM model."""
    persona = MagicMock()
    persona.id = persona_id or uuid4()
    persona.user_id = user_id or uuid4()
    persona.skills = skills or []
    persona.years_experience = years_experience
    persona.current_role = current_role
    persona.target_roles = target_roles or ["Senior Engineer"]
    persona.target_skills = target_skills or ["Kubernetes"]
    persona.remote_preference = remote_preference
    persona.commutable_cities = commutable_cities or ["Phoenix"]
    persona.minimum_base_salary = minimum_base_salary
    persona.industry_exclusions = industry_exclusions or []
    persona.visa_sponsorship_required = visa_sponsorship_required
    persona.auto_draft_threshold = auto_draft_threshold
    persona.updated_at = datetime.now(UTC)
    return persona


def _make_job(
    *,
    job_id: UUID | None = None,
    job_title: str = "Backend Developer",
    company_name: str = "Acme Corp",
    work_model: str | None = "Remote",
    salary_max: int | None = 120000,
    location: str | None = "Remote",
    extracted_skills: list | None = None,
    culture_text: str | None = "Fast-paced startup culture",
    years_experience_min: int | None = 3,
    years_experience_max: int | None = 7,
) -> MagicMock:
    """Create a mock JobPosting ORM model."""
    job = MagicMock()
    job.id = job_id or uuid4()
    job.job_title = job_title
    job.company_name = company_name
    job.work_model = work_model
    job.salary_max = salary_max
    job.location = location
    job.extracted_skills = extracted_skills or []
    job.culture_text = culture_text
    job.years_experience_min = years_experience_min
    job.years_experience_max = years_experience_max
    return job


def _make_scored_job(
    *,
    job_id: UUID | None = None,
    fit_total: int = 75,
    stretch_total: int = 60,
) -> MagicMock:
    """Create a mock ScoredJob result from batch_score_jobs."""
    scored = MagicMock()
    scored.job_id = job_id or uuid4()
    scored.fit_score.total = fit_total
    scored.fit_score.components = {
        "hard_skills": 80.0,
        "soft_skills": 70.0,
        "experience_level": 75.0,
        "role_title": 70.0,
        "location_logistics": 90.0,
    }
    scored.fit_score.weights = {
        "hard_skills": 0.40,
        "soft_skills": 0.15,
        "experience_level": 0.25,
        "role_title": 0.10,
        "location_logistics": 0.10,
    }
    scored.stretch_score.total = stretch_total
    scored.stretch_score.components = {
        "target_role": 65.0,
        "target_skills": 55.0,
        "growth_trajectory": 70.0,
    }
    scored.stretch_score.weights = {
        "target_role": 0.50,
        "target_skills": 0.40,
        "growth_trajectory": 0.10,
    }
    return scored


def _make_persona_embeddings(persona_id: UUID) -> MagicMock:
    """Create a mock PersonaEmbeddingsResult."""
    emb = MagicMock()
    emb.persona_id = persona_id
    emb.hard_skills.vector = [0.1] * 10
    emb.soft_skills.vector = [0.2] * 10
    emb.logistics.vector = [0.3] * 10
    emb.version = datetime.now(UTC)
    return emb


def _make_llm_response(content: str = "Good match based on skills.") -> MagicMock:
    """Create a mock LLM response."""
    response = MagicMock()
    response.content = content
    return response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async database session."""
    return AsyncMock()


@pytest.fixture
def user_id() -> UUID:
    """Random user UUID for tenant isolation."""
    return uuid4()


@pytest.fixture
def persona_id() -> UUID:
    """Random persona UUID."""
    return uuid4()


# ---------------------------------------------------------------------------
# score_job() — single job scoring
# ---------------------------------------------------------------------------


class TestScoreJob:
    """Tests for JobScoringService.score_job()."""

    @pytest.mark.asyncio
    async def test_scores_single_job_through_full_pipeline(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """A single job should go through filter → score → rationale → save."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=78)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()
        mock_emb = AsyncMock()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona) as mock_load_p,
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(
                _PATCH_FILTER_BATCH,
                return_value=([job], []),
            ),
            patch(
                _PATCH_BATCH_SCORE,
                return_value=[scored],
            ),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=mock_emb
            )
            result = await svc.score_job(persona_id, job_id, user_id)

        assert result["job_posting_id"] == str(job_id)
        assert result["fit_score"] == 78
        assert result["filtered_reason"] is None
        mock_load_p.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_filtered_result_when_non_negotiables_fail(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Jobs failing non-negotiables should have None scores."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        embeddings = _make_persona_embeddings(persona_id)

        # Simulate filter failure
        from app.services.scoring_flow import JobFilterResult

        filter_result = JobFilterResult(
            job_id=job_id,
            passed=False,
            failed_reasons=["Salary below minimum"],
            warnings=[],
        )

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(
                _PATCH_FILTER_BATCH,
                return_value=([], [filter_result]),
            ),
            patch(_PATCH_BATCH_SCORE) as mock_batch,
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(mock_db, embedding_provider=AsyncMock())
            result = await svc.score_job(persona_id, job_id, user_id)

        assert result["fit_score"] is None
        assert result["stretch_score"] is None
        assert "Salary below minimum" in (result["filtered_reason"] or "")
        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_generates_rationale_when_fit_at_threshold(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Rationale should be generated when fit_score == RATIONALE_SCORE_THRESHOLD (65)."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=RATIONALE_SCORE_THRESHOLD)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response("Solid match.")

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            result = await svc.score_job(persona_id, job_id, user_id)

        assert result["explanation"] == "Solid match."
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_rationale_when_fit_below_threshold(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Rationale should be a generic message when fit < 65."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(
            job_id=job_id, fit_total=RATIONALE_SCORE_THRESHOLD - 1
        )
        embeddings = _make_persona_embeddings(persona_id)

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(mock_db, embedding_provider=AsyncMock())
            result = await svc.score_job(persona_id, job_id, user_id)

        assert result["explanation"] is not None
        assert "low match" in result["explanation"].lower()

    @pytest.mark.asyncio
    async def test_raises_not_found_when_persona_missing(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Should raise NotFoundError when persona does not exist."""
        from app.core.errors import NotFoundError

        with patch(
            _PATCH_LOAD_PERSONA, side_effect=NotFoundError("Persona", str(persona_id))
        ):
            svc = JobScoringService(mock_db)
            with pytest.raises(NotFoundError, match="Persona"):
                await svc.score_job(persona_id, uuid4(), user_id)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_job_missing(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Should raise NotFoundError when job posting does not exist."""
        from app.core.errors import NotFoundError

        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        embeddings = _make_persona_embeddings(persona_id)

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(
                _PATCH_LOAD_JOBS,
                side_effect=NotFoundError("JobPosting", "missing-id"),
            ),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
        ):
            svc = JobScoringService(mock_db, embedding_provider=AsyncMock())
            with pytest.raises(NotFoundError, match="JobPosting"):
                await svc.score_job(persona_id, uuid4(), user_id)


# ---------------------------------------------------------------------------
# score_batch() — batch scoring
# ---------------------------------------------------------------------------


class TestScoreBatch:
    """Tests for JobScoringService.score_batch()."""

    @pytest.mark.asyncio
    async def test_scores_multiple_jobs_in_one_call(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Batch scoring should process all jobs and return results."""

        job_ids = [uuid4(), uuid4(), uuid4()]
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        jobs = [_make_job(job_id=jid) for jid in job_ids]
        scored_jobs = [_make_scored_job(job_id=jid, fit_total=70) for jid in job_ids]
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=jobs),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=(jobs, [])),
            patch(_PATCH_BATCH_SCORE, return_value=scored_jobs),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            results = await svc.score_batch(persona_id, job_ids, user_id)

        assert len(results) == 3
        returned_ids = {r["job_posting_id"] for r in results}
        assert returned_ids == {str(jid) for jid in job_ids}

    @pytest.mark.asyncio
    async def test_loads_persona_embeddings_once_for_batch(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Persona embeddings should be generated once, not per job."""

        job_ids = [uuid4(), uuid4()]
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        jobs = [_make_job(job_id=jid) for jid in job_ids]
        scored_jobs = [_make_scored_job(job_id=jid) for jid in job_ids]
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=jobs),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ) as mock_gen_emb,
            patch(_PATCH_FILTER_BATCH, return_value=(jobs, [])),
            patch(_PATCH_BATCH_SCORE, return_value=scored_jobs),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            await svc.score_batch(persona_id, job_ids, user_id)

        # Performance optimization test: embedding generation is an expensive
        # API call. Calling it N times instead of once would multiply cost and
        # latency linearly with batch size. The call-count assertion guards
        # against regressions that break this optimization.
        mock_gen_emb.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_mix_of_filtered_and_scored_jobs(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Batch with some jobs filtered and some scored."""
        from app.services.scoring_flow import JobFilterResult

        pass_id = uuid4()
        fail_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        pass_job = _make_job(job_id=pass_id)
        fail_job = _make_job(job_id=fail_id)
        scored = _make_scored_job(job_id=pass_id, fit_total=80)
        embeddings = _make_persona_embeddings(persona_id)

        filter_result = JobFilterResult(
            job_id=fail_id,
            passed=False,
            failed_reasons=["Remote only mismatch"],
            warnings=[],
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[pass_job, fail_job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(
                _PATCH_FILTER_BATCH,
                return_value=([pass_job], [filter_result]),
            ),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            results = await svc.score_batch(persona_id, [pass_id, fail_id], user_id)

        assert len(results) == 2
        scored_result = next(r for r in results if r["job_posting_id"] == str(pass_id))
        filtered_result = next(
            r for r in results if r["job_posting_id"] == str(fail_id)
        )
        assert scored_result["fit_score"] == 80
        assert filtered_result["fit_score"] is None

    @pytest.mark.asyncio
    async def test_passes_user_id_to_load_jobs_for_tenant_isolation(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """score_batch should pass user_id to _load_jobs for tenant isolation."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=70)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]) as mock_load_jobs,
            patch(_PATCH_GEN_EMBEDDINGS, return_value=embeddings),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            await svc.score_batch(persona_id, [job_id], user_id)

        # Security contract: user_id must be passed for tenant isolation
        mock_load_jobs.assert_called_once_with(mock_db, [job_id], user_id)

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_input(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Empty job list should return empty results without loading persona."""

        svc = JobScoringService(mock_db)
        results = await svc.score_batch(persona_id, [], user_id)
        assert results == []

    @pytest.mark.asyncio
    async def test_raises_value_error_for_oversized_batch(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Batch exceeding _MAX_BATCH_SIZE should raise ValueError."""

        svc = JobScoringService(mock_db)
        oversized = [uuid4() for _ in range(501)]
        with pytest.raises(ValueError, match="exceeds maximum"):
            await svc.score_batch(persona_id, oversized, user_id)

    @pytest.mark.asyncio
    async def test_handles_all_jobs_filtered(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """When all jobs fail non-negotiables, no scoring should occur."""
        from app.services.scoring_flow import JobFilterResult

        job_ids = [uuid4(), uuid4()]
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        jobs = [_make_job(job_id=jid) for jid in job_ids]
        embeddings = _make_persona_embeddings(persona_id)

        filter_results = [
            JobFilterResult(
                job_id=jid,
                passed=False,
                failed_reasons=["Industry excluded"],
                warnings=[],
            )
            for jid in job_ids
        ]

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=jobs),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(
                _PATCH_FILTER_BATCH,
                return_value=([], filter_results),
            ),
            patch(_PATCH_BATCH_SCORE) as mock_batch,
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(mock_db, embedding_provider=AsyncMock())
            results = await svc.score_batch(persona_id, job_ids, user_id)

        assert len(results) == 2
        assert all(r["fit_score"] is None for r in results)
        mock_batch.assert_not_called()


# ---------------------------------------------------------------------------
# rescore_all_discovered()
# ---------------------------------------------------------------------------


class TestRescoreAllDiscovered:
    """Tests for JobScoringService.rescore_all_discovered()."""

    @pytest.mark.asyncio
    async def test_rescores_all_discovered_jobs(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Should load discovered persona_jobs and rescore them all."""

        job_id_1 = uuid4()
        job_id_2 = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        jobs = [_make_job(job_id=job_id_1), _make_job(job_id=job_id_2)]
        scored = [
            _make_scored_job(job_id=job_id_1, fit_total=70),
            _make_scored_job(job_id=job_id_2, fit_total=85),
        ]
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(
                _PATCH_LOAD_DISCOVERED,
                return_value=[job_id_1, job_id_2],
            ),
            patch(_PATCH_LOAD_JOBS, return_value=jobs),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=(jobs, [])),
            patch(_PATCH_BATCH_SCORE, return_value=scored),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            results = await svc.rescore_all_discovered(persona_id, user_id)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_discovered_jobs(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """No discovered jobs should return empty results."""

        persona = _make_persona(persona_id=persona_id, user_id=user_id)

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_DISCOVERED, return_value=[]),
        ):
            svc = JobScoringService(mock_db)
            results = await svc.rescore_all_discovered(persona_id, user_id)

        assert results == []


# ---------------------------------------------------------------------------
# Rationale generation
# ---------------------------------------------------------------------------


class TestRationaleGeneration:
    """Tests for rationale threshold gating and LLM interaction."""

    @pytest.mark.asyncio
    async def test_rationale_uses_correct_system_prompt(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """LLM call should use SCORE_RATIONALE_SYSTEM_PROMPT."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=80)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            await svc.score_job(persona_id, job_id, user_id)

        call_kwargs = mock_llm.complete.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
        system_msg = next(m for m in messages if m.role == "system")
        assert "career match analyst" in system_msg.content.lower()

    @pytest.mark.asyncio
    async def test_rationale_falls_back_on_llm_error(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """LLM error during rationale should produce a fallback message."""
        from app.providers import ProviderError

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=75)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = ProviderError("API error")

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            result = await svc.score_job(persona_id, job_id, user_id)

        # Should still return a result, just without LLM rationale
        assert result["fit_score"] == 75
        assert result["explanation"] is not None


# ---------------------------------------------------------------------------
# Score details / persistence
# ---------------------------------------------------------------------------


class TestScoreDetailsAndPersistence:
    """Tests for score_details building and persona_jobs persistence."""

    @pytest.mark.asyncio
    async def test_builds_score_details_with_components(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """score_details should include fit and stretch component breakdowns."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=75)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            result = await svc.score_job(persona_id, job_id, user_id)

        details = result["score_details"]
        assert details is not None
        assert "fit" in details
        assert "stretch" in details
        assert "hard_skills" in details["fit"]["components"]

    @pytest.mark.asyncio
    async def test_saves_score_to_persona_jobs(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Scored results should be persisted via _save_score."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=82)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE) as mock_save,
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            await svc.score_job(persona_id, job_id, user_id)

        mock_save.assert_called_once()
        save_args = mock_save.call_args
        assert save_args.kwargs["job_posting_id"] == job_id
        assert save_args.kwargs["fit_score"] == 82

    @pytest.mark.asyncio
    async def test_saves_filtered_score_to_persona_jobs(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Filtered results should also be persisted with None scores."""
        from app.services.scoring_flow import JobFilterResult

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        embeddings = _make_persona_embeddings(persona_id)

        filter_result = JobFilterResult(
            job_id=job_id,
            passed=False,
            failed_reasons=["Salary too low"],
            warnings=[],
        )

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(
                _PATCH_FILTER_BATCH,
                return_value=([], [filter_result]),
            ),
            patch(_PATCH_SAVE_SCORE) as mock_save,
        ):
            svc = JobScoringService(mock_db, embedding_provider=AsyncMock())
            await svc.score_job(persona_id, job_id, user_id)

        mock_save.assert_called_once()
        save_args = mock_save.call_args
        assert save_args.kwargs["fit_score"] is None


# ---------------------------------------------------------------------------
# Auto-draft trigger (no-op at MVP)
# ---------------------------------------------------------------------------


class TestAutoDraft:
    """Tests for auto-draft threshold detection."""

    @pytest.mark.asyncio
    async def test_auto_draft_is_noop_at_mvp(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Auto-draft should be detected but not trigger Ghostwriter at MVP."""

        job_id = uuid4()
        persona = _make_persona(
            persona_id=persona_id,
            user_id=user_id,
            auto_draft_threshold=90,
        )
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=95)
        embeddings = _make_persona_embeddings(persona_id)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]),
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db, llm_provider=mock_llm, embedding_provider=AsyncMock()
            )
            result = await svc.score_job(persona_id, job_id, user_id)

        # Should still return normally — no Ghostwriter invocation
        assert result["fit_score"] == 95


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handles_embedding_provider_error(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """Embedding generation failure should propagate as ProviderError."""
        from app.providers import ProviderError

        persona = _make_persona(persona_id=persona_id, user_id=user_id)

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                side_effect=ProviderError("Embedding API down"),
            ),
        ):
            svc = JobScoringService(mock_db, embedding_provider=AsyncMock())
            with pytest.raises(ProviderError, match="Embedding API down"):
                await svc.score_batch(persona_id, [uuid4()], user_id)

    @pytest.mark.asyncio
    async def test_score_batch_passes_embedding_provider_to_batch_scorer(
        self, mock_db: AsyncMock, user_id: UUID, persona_id: UUID
    ) -> None:
        """batch_score_jobs should receive the embedding provider."""

        job_id = uuid4()
        persona = _make_persona(persona_id=persona_id, user_id=user_id)
        job = _make_job(job_id=job_id)
        scored = _make_scored_job(job_id=job_id, fit_total=70)
        embeddings = _make_persona_embeddings(persona_id)

        mock_emb_provider = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = _make_llm_response()

        with (
            patch(_PATCH_LOAD_PERSONA, return_value=persona),
            patch(_PATCH_LOAD_JOBS, return_value=[job]),
            patch(
                _PATCH_GEN_EMBEDDINGS,
                return_value=embeddings,
            ),
            patch(_PATCH_FILTER_BATCH, return_value=([job], [])),
            patch(_PATCH_BATCH_SCORE, return_value=[scored]) as mock_batch,
            patch(_PATCH_SAVE_SCORE),
        ):
            svc = JobScoringService(
                mock_db,
                llm_provider=mock_llm,
                embedding_provider=mock_emb_provider,
            )
            await svc.score_batch(persona_id, [job_id], user_id)

        call_kwargs = mock_batch.call_args.kwargs
        assert call_kwargs["embedding_provider"] is mock_emb_provider

"""Tests for ContentGenerationService.

REQ-018 §6–§7: 8-step content generation pipeline orchestrator that replaces
the LangGraph ghostwriter graph with plain async Python.

Tests verify:
- Input validation (user_id, persona_id, job_posting_id, trigger_type)
- Duplicate prevention (draft exists, approved exists)
- Full generation pipeline (tailoring needed / not needed)
- Cover letter generation delegation
- Job freshness check (active / expired warning)
- Reasoning explanation building
- Error propagation from downstream services
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.ghostwriter import TriggerType
from app.core.errors import ValidationError
from app.services.content_generation_service import (
    ContentGenerationService,
    GenerationResult,
)

# Module path for patching
_MODULE = "app.services.content_generation_service"

# Test constants
_USER_ID = "user-1"
_PERSONA_ID = "persona-1"
_JOB_POSTING_ID = "job-1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service() -> ContentGenerationService:
    """Create a ContentGenerationService instance."""
    return ContentGenerationService()


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Validate required parameters before pipeline starts."""

    async def test_rejects_empty_user_id(
        self, service: ContentGenerationService
    ) -> None:
        """Empty user_id should raise ValueError."""
        with pytest.raises(ValidationError, match="user_id is required"):
            await service.generate(
                user_id="",
                persona_id=_PERSONA_ID,
                job_posting_id=_JOB_POSTING_ID,
                trigger_type=TriggerType.MANUAL_REQUEST,
            )

    async def test_rejects_empty_persona_id(
        self, service: ContentGenerationService
    ) -> None:
        """Empty persona_id should raise ValueError."""
        with pytest.raises(ValidationError, match="persona_id is required"):
            await service.generate(
                user_id=_USER_ID,
                persona_id="",
                job_posting_id=_JOB_POSTING_ID,
                trigger_type=TriggerType.MANUAL_REQUEST,
            )

    async def test_rejects_empty_job_posting_id(
        self, service: ContentGenerationService
    ) -> None:
        """Empty job_posting_id should raise ValueError."""
        with pytest.raises(ValidationError, match="job_posting_id is required"):
            await service.generate(
                user_id=_USER_ID,
                persona_id=_PERSONA_ID,
                job_posting_id="",
                trigger_type=TriggerType.MANUAL_REQUEST,
            )


# ---------------------------------------------------------------------------
# Duplicate Prevention (Step 1)
# ---------------------------------------------------------------------------


class TestDuplicatePrevention:
    """Step 1: Check existing variant to prevent duplicates."""

    async def test_returns_existing_draft(
        self, service: ContentGenerationService
    ) -> None:
        """When a draft variant exists, return it with a message."""
        with patch.object(service, "_check_existing", return_value="draft"):
            result = await service.generate(
                user_id=_USER_ID,
                persona_id=_PERSONA_ID,
                job_posting_id=_JOB_POSTING_ID,
            )

        assert result.duplicate_message is not None
        assert "already working" in result.duplicate_message.lower()
        assert result.cover_letter is None

    async def test_blocks_when_approved_exists(
        self, service: ContentGenerationService
    ) -> None:
        """When an approved variant exists, block with a message."""
        with patch.object(service, "_check_existing", return_value="approved"):
            result = await service.generate(
                user_id=_USER_ID,
                persona_id=_PERSONA_ID,
                job_posting_id=_JOB_POSTING_ID,
            )

        assert result.duplicate_message is not None
        assert "approved" in result.duplicate_message.lower()
        assert result.cover_letter is None


# ---------------------------------------------------------------------------
# Full Pipeline (Steps 2-8)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Steps 2-8: Full generation pipeline with tailoring."""

    @pytest.fixture(autouse=True)
    def _patch_steps(self, service: ContentGenerationService) -> None:
        """Patch all private pipeline methods for isolation."""
        # Step 1: no existing variant (sync stub)
        self._p1 = patch.object(service, "_check_existing", return_value=None)
        # Step 2: select base resume (sync stub)
        self._p2 = patch.object(
            service,
            "_select_base_resume",
            return_value="resume-1",
        )
        # Step 3: evaluate tailoring (sync stub, no tailoring needed by default)
        self._mock_tailoring = MagicMock()
        self._mock_tailoring.action = "use_base"
        self._mock_tailoring.signals = []
        self._mock_tailoring.reasoning = "Resume aligns well."
        self._p3 = patch.object(
            service,
            "_evaluate_tailoring",
            return_value=self._mock_tailoring,
        )
        # Step 4: create variant (sync stub, only called when tailoring needed)
        self._p4 = patch.object(service, "_create_variant", return_value=None)
        # Step 5: select stories (sync stub)
        self._p5 = patch.object(service, "_select_stories", return_value=[])
        # Step 6: generate cover letter (async — has real await)
        self._mock_cover_letter = MagicMock()
        self._mock_cover_letter.content = "Dear Hiring Manager..."
        self._mock_cover_letter.reasoning = "Selected stories for relevance."
        self._mock_cover_letter.word_count = 280
        self._mock_cover_letter.stories_used = []
        self._p6 = patch.object(
            service,
            "_generate_cover_letter",
            new_callable=AsyncMock,
            return_value=self._mock_cover_letter,
        )
        # Step 7: check job active (sync stub)
        self._p7 = patch.object(service, "_check_job_active", return_value=True)
        # Step 8: build review response
        self._p8 = patch.object(
            service,
            "_build_review_response",
            return_value="Materials ready for review.",
        )

        self._p1.start()
        self._p2.start()
        self._p3.start()
        self._p4.start()
        self._p5.start()
        self._p6.start()
        self._p7.start()
        self._p8.start()

    def _stop_patches(self) -> None:
        for p in [
            self._p1,
            self._p2,
            self._p3,
            self._p4,
            self._p5,
            self._p6,
            self._p7,
            self._p8,
        ]:
            p.stop()

    @pytest.fixture(autouse=True)
    def _cleanup(self) -> Generator[None, None, None]:  # noqa: PT004
        yield
        self._stop_patches()

    async def test_returns_generation_result(
        self, service: ContentGenerationService
    ) -> None:
        """Full pipeline should return a GenerationResult."""
        result = await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
        )

        assert result.cover_letter is not None
        assert result.agent_reasoning is not None
        assert result.duplicate_message is None
        assert result.review_warning is None

    async def test_skips_variant_creation_when_no_tailoring(
        self, service: ContentGenerationService
    ) -> None:
        """When tailoring not needed, result reflects 'use_base' decision."""
        result = await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
        )

        assert result.tailoring_action == "use_base"

    async def test_calls_variant_creation_when_tailoring_needed(
        self, service: ContentGenerationService
    ) -> None:
        """When tailoring is needed, _create_variant should be called."""
        self._mock_tailoring.action = "create_variant"
        self._mock_tailoring.signals = [MagicMock(detail="Missing keywords")]
        self._mock_tailoring.reasoning = "Tailoring recommended."

        await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
        )

        # Side-effect test: _create_variant produces a DB write (JobVariant
        # row) that is not reflected in GenerationResult fields. The call-count
        # assertion verifies the conditional branch executes when tailoring is
        # needed — there is no result field that distinguishes "variant was
        # created" from "variant was skipped."
        service._create_variant.assert_called_once()  # type: ignore[attr-defined]

    async def test_adds_warning_when_job_expired(
        self, service: ContentGenerationService
    ) -> None:
        """When job is expired, result should include a review warning."""
        service._check_job_active.return_value = False  # type: ignore[attr-defined]

        result = await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
        )

        assert result.review_warning is not None
        assert "expired" in result.review_warning.lower()

    async def test_no_warning_when_job_active(
        self, service: ContentGenerationService
    ) -> None:
        """When job is active, no review warning."""
        result = await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
        )

        assert result.review_warning is None

    async def test_full_pipeline_populates_all_result_fields(
        self, service: ContentGenerationService
    ) -> None:
        """Full pipeline should populate every GenerationResult field from
        the corresponding pipeline step outputs."""
        result = await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
        )

        # Step 1: no duplicate found
        assert result.duplicate_message is None
        # Step 3: tailoring evaluation
        assert result.tailoring_action == "use_base"
        assert result.tailoring_reasoning == "Resume aligns well."
        # Step 5: story selection (mock returns [])
        assert result.selected_stories == ()
        # Step 6: cover letter generated
        assert result.cover_letter is not None
        assert result.cover_letter.content == "Dear Hiring Manager..."
        assert result.cover_letter.word_count == 280
        # Step 7: job freshness check
        assert result.job_active is True
        assert result.review_warning is None
        # Step 8: reasoning explanation
        assert result.agent_reasoning == "Materials ready for review."

    async def test_passes_trigger_type_through(
        self, service: ContentGenerationService
    ) -> None:
        """Trigger type should be available in the generation result."""
        result = await service.generate(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_POSTING_ID,
            trigger_type=TriggerType.AUTO_DRAFT,
        )

        # Result is returned successfully with auto_draft trigger
        assert result.cover_letter is not None


# ---------------------------------------------------------------------------
# Reasoning Explanation (Step 8)
# ---------------------------------------------------------------------------


class TestReasoningExplanation:
    """Step 8: Build review response with reasoning."""

    async def test_builds_reasoning_from_tailoring_and_stories(
        self, service: ContentGenerationService
    ) -> None:
        """_build_review_response should combine tailoring and story info."""
        with (
            patch.object(service, "_check_existing", return_value=None),
            patch.object(
                service,
                "_select_base_resume",
                return_value="resume-1",
            ),
            patch.object(
                service,
                "_evaluate_tailoring",
            ) as mock_tailoring,
            patch.object(
                service,
                "_create_variant",
                return_value=None,
            ),
            patch.object(
                service,
                "_select_stories",
                return_value=[],
            ),
            patch.object(
                service,
                "_generate_cover_letter",
                new_callable=AsyncMock,
            ) as mock_cl,
            patch.object(
                service,
                "_check_job_active",
                return_value=True,
            ),
            patch(
                f"{_MODULE}.format_agent_reasoning",
                return_value="Tailored resume, selected 2 stories.",
            ),
        ):
            td = MagicMock()
            td.action = "create_variant"
            td.signals = [MagicMock(detail="Missing Python keyword")]
            td.reasoning = "Tailoring recommended."
            mock_tailoring.return_value = td

            cl = MagicMock()
            cl.content = "Dear Hiring Manager..."
            cl.reasoning = "Story reasoning."
            cl.word_count = 280
            cl.stories_used = ["story-1"]
            mock_cl.return_value = cl

            result = await service.generate(
                user_id=_USER_ID,
                persona_id=_PERSONA_ID,
                job_posting_id=_JOB_POSTING_ID,
            )

            assert result.agent_reasoning is not None


# ---------------------------------------------------------------------------
# GenerationResult Dataclass
# ---------------------------------------------------------------------------


class TestGenerationResult:
    """GenerationResult behavioral tests."""

    def test_duplicate_result_has_no_content(self) -> None:
        """Duplicate prevention result should have no generated content."""
        result = GenerationResult(
            cover_letter=None,
            tailoring_action=None,
            tailoring_reasoning=None,
            selected_stories=(),
            agent_reasoning=None,
            review_warning=None,
            duplicate_message="Already working on this.",
            job_active=True,
        )

        assert result.cover_letter is None
        assert result.duplicate_message == "Already working on this."


# ---------------------------------------------------------------------------
# Chat.py Delegation
# ---------------------------------------------------------------------------


class TestChatDelegation:
    """Verify chat.py delegates to ContentGenerationService."""

    # Patch target: lazy import inside delegate_ghostwriter resolves from
    # the source module, so we patch the class at its definition site.
    _PATCH_SERVICE = f"{_MODULE}.ContentGenerationService"

    async def test_delegate_ghostwriter_calls_service(self) -> None:
        """delegate_ghostwriter should call ContentGenerationService.generate."""
        from app.agents.chat import delegate_ghostwriter
        from app.agents.state import ChatAgentState

        mock_result = GenerationResult(
            cover_letter=MagicMock(),
            tailoring_action="use_base",
            tailoring_reasoning="Aligns well.",
            selected_stories=(),
            agent_reasoning="Ready.",
            review_warning=None,
            duplicate_message=None,
            job_active=True,
        )

        state: ChatAgentState = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "target_job_id": _JOB_POSTING_ID,
        }

        with patch(self._PATCH_SERVICE) as MockService:
            MockService.return_value.generate = AsyncMock(return_value=mock_result)
            new_state = await delegate_ghostwriter(state)

        tool_results = new_state.get("tool_results", [])
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "invoke_ghostwriter"
        assert tool_results[0]["result"]["status"] == "completed"
        assert tool_results[0]["error"] is None

    async def test_delegate_ghostwriter_handles_missing_job_id(self) -> None:
        """Missing target_job_id should return an error tool result."""
        from app.agents.chat import delegate_ghostwriter
        from app.agents.state import ChatAgentState

        state: ChatAgentState = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "target_job_id": None,
        }

        new_state = await delegate_ghostwriter(state)

        tool_results = new_state.get("tool_results", [])
        assert len(tool_results) == 1
        assert tool_results[0]["error"] is not None

    async def test_delegate_ghostwriter_handles_service_error(self) -> None:
        """Service exception should return an error tool result."""
        from app.agents.chat import delegate_ghostwriter
        from app.agents.state import ChatAgentState

        state: ChatAgentState = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "target_job_id": _JOB_POSTING_ID,
        }

        with patch(self._PATCH_SERVICE) as MockService:
            MockService.return_value.generate = AsyncMock(
                side_effect=RuntimeError("LLM failed")
            )
            new_state = await delegate_ghostwriter(state)

        tool_results = new_state.get("tool_results", [])
        assert len(tool_results) == 1
        assert tool_results[0]["error"] is not None
        assert tool_results[0]["result"] is None

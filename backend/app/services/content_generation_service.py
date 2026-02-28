"""Content generation service.

REQ-018 §6: Orchestrates the 8-step content generation pipeline, replacing
the LangGraph ghostwriter graph with plain async Python.

Pipeline:
    1. Check existing variant (duplicate prevention)
    2. Select base resume (role_type matching)
    3. Evaluate tailoring need → tailoring_decision.py
    4. Create job variant (LLM) → modification_limits.py
    5. Select achievement stories → story_selection.py
    6. Generate cover letter (LLM) → cover_letter_generation.py
    7. Check job still active
    8. Build review response → reasoning_explanation.py

Relocates logic from ghostwriter_graph.py nodes into private methods
on a single service class. No new business logic — orchestrates 13
existing service files only.

Cross-references:
    - REQ-018 §7: Behavioral specification (pipeline flow, duplicate rules)
    - REQ-010 §4–§5: Tailoring and cover letter generation details
    - REQ-007 §8: Original ghostwriter agent specification
"""

import logging
from dataclasses import dataclass

from app.agents.ghostwriter import TriggerType
from app.core.errors import ValidationError
from app.core.llm_sanitization import sanitize_user_feedback
from app.providers.llm.base import LLMProvider
from app.schemas.prompt_params import JobContext, VoiceProfileData
from app.services.cover_letter_generation import CoverLetterResult
from app.services.reasoning_explanation import ReasoningStory, format_agent_reasoning
from app.services.story_selection import ScoredStory, select_achievement_stories
from app.services.tailoring_decision import TailoringDecision, evaluate_tailoring_need

logger = logging.getLogger(__name__)


# =============================================================================
# Result Dataclass
# =============================================================================


@dataclass(frozen=True)
class GenerationResult:
    """Result of the content generation pipeline.

    REQ-018 §6.2: Replaces the GhostwriterState TypedDict with a proper
    dataclass. All pipeline outputs are carried here.

    Attributes:
        cover_letter: Generated cover letter result (None if duplicate).
        tailoring_action: Tailoring decision ("use_base" or "create_variant").
        tailoring_reasoning: Human-readable explanation of tailoring decision.
        selected_stories: Scored stories selected for cover letter.
        agent_reasoning: Combined user-facing reasoning explanation.
        review_warning: Warning message (e.g., job expired).
        duplicate_message: Message when an existing variant was found.
        job_active: Whether the target job is still active.
    """

    cover_letter: CoverLetterResult | None
    tailoring_action: str | None
    tailoring_reasoning: str | None
    selected_stories: tuple[ScoredStory, ...]
    agent_reasoning: str | None
    review_warning: str | None
    duplicate_message: str | None
    job_active: bool = True


# =============================================================================
# Service Class
# =============================================================================


class ContentGenerationService:
    """Generates tailored application materials for a job posting.

    REQ-018 §6.2: Single orchestrator class replacing the LangGraph
    StateGraph. Calls existing services in an 8-step pipeline.
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    async def generate(
        self,
        user_id: str,
        persona_id: str,
        job_posting_id: str,
        trigger_type: TriggerType = TriggerType.MANUAL_REQUEST,
        feedback: str | None = None,  # noqa: ARG002
        existing_variant_id: str | None = None,
    ) -> GenerationResult:
        """Generate tailored resume variant + cover letter for a job.

        REQ-018 §6.2 / §7.1: 8-step pipeline.

        Args:
            user_id: User ID for tenant isolation.
            persona_id: Persona to generate materials for.
            job_posting_id: Target job posting ID.
            trigger_type: How generation was triggered.
            feedback: User feedback for regeneration.
            existing_variant_id: Known existing variant ID for race
                condition prevention (REQ-007 §10.4.2).

        Returns:
            GenerationResult with variant, cover_letter, explanation,
            and optional warning if job expired mid-generation.

        Raises:
            ValidationError: If user_id, persona_id, or job_posting_id are empty.
        """
        # --- Input validation ---
        if not user_id:
            raise ValidationError("user_id is required")
        if not persona_id:
            raise ValidationError("persona_id is required")
        if not job_posting_id:
            raise ValidationError("job_posting_id is required")

        # Sanitize feedback early so it's safe for any future use (REQ-010 §7.2)
        if feedback is not None:
            feedback = sanitize_user_feedback(feedback)

        logger.info(
            "Starting content generation: user=%s persona=%s job=%s trigger=%s",
            user_id,
            persona_id,
            job_posting_id,
            trigger_type.value,
        )

        # --- Step 1: Check existing variant (duplicate prevention) ---
        existing_status = self._check_existing(job_posting_id, existing_variant_id)
        if existing_status is not None:
            return self._handle_duplicate(existing_status)

        # --- Step 2: Select base resume ---
        base_resume_id = self._select_base_resume(persona_id, job_posting_id)

        # --- Step 3: Evaluate tailoring need ---
        tailoring = self._evaluate_tailoring(base_resume_id, job_posting_id)

        # --- Step 4: Create job variant (conditional) ---
        if tailoring.action == "create_variant":
            self._create_variant(base_resume_id, job_posting_id, tailoring)

        # --- Step 5: Select achievement stories ---
        scored_stories = self._select_stories(persona_id, job_posting_id)

        # --- Step 6: Generate cover letter ---
        cover_letter = await self._generate_cover_letter(
            persona_id, job_posting_id, scored_stories
        )

        # --- Step 7: Check job still active ---
        job_active = self._check_job_active(job_posting_id)

        review_warning: str | None = None
        if not job_active:
            review_warning = (
                "Note: This job posting appears to have expired. "
                "You can still review the materials, but the posting "
                "may no longer be accepting applications."
            )

        # --- Step 8: Build review response ---
        agent_reasoning = self._build_review_response(
            tailoring, scored_stories, job_posting_id
        )

        return GenerationResult(
            cover_letter=cover_letter,
            tailoring_action=tailoring.action,
            tailoring_reasoning=tailoring.reasoning,
            selected_stories=tuple(scored_stories),
            agent_reasoning=agent_reasoning,
            review_warning=review_warning,
            duplicate_message=None,
            job_active=job_active,
        )

    # =========================================================================
    # Private Pipeline Methods
    # =========================================================================
    # SECURITY CONTRACT: When wiring real data into these methods, ALL
    # user-originated strings (job text, persona data, feedback) MUST pass
    # through sanitize_llm_input() before reaching LLM prompts.
    # See: app/core/llm_sanitization.py

    def _check_existing(
        self,
        job_posting_id: str,
        existing_variant_id: str | None,
    ) -> str | None:
        """Check for existing JobVariant to prevent duplicates.

        REQ-018 §7.2: Duplicate prevention.

        Returns:
            None if no variant, "draft" or "approved" if one exists.
        """
        logger.info(
            "Checking existing variant for job %s (existing_id=%s)",
            job_posting_id,
            existing_variant_id,
        )
        # Placeholder: assume no existing variant.
        # Real implementation will query job_variants repository.
        return None

    def _handle_duplicate(self, status: str) -> GenerationResult:
        """Build a result for an existing variant scenario.

        REQ-018 §7.2: Return appropriate message based on variant status.
        """
        if status == "approved":
            message = "You already have an approved resume for this job."
        else:
            message = "I'm already working on this. Want me to start fresh?"

        return GenerationResult(
            cover_letter=None,
            tailoring_action=None,
            tailoring_reasoning=None,
            selected_stories=(),
            agent_reasoning=None,
            review_warning=None,
            duplicate_message=message,
            job_active=True,
        )

    def _select_base_resume(self, persona_id: str, job_posting_id: str) -> str | None:
        """Select the best base resume for the target job.

        REQ-018 §7.1 Step 2: Match role_type to job, fall back to is_primary.

        Returns:
            Base resume ID, or None if no resume available.
        """
        logger.info(
            "Selecting base resume for persona %s, job %s",
            persona_id,
            job_posting_id,
        )
        # Placeholder: no selection yet.
        # Real implementation will query base_resumes repository.
        return None

    def _evaluate_tailoring(
        self, base_resume_id: str | None, job_posting_id: str
    ) -> TailoringDecision:
        """Evaluate whether the base resume needs tailoring.

        REQ-018 §7.1 Step 3: Delegates to tailoring_decision.py.
        """
        logger.info(
            "Evaluating tailoring need for job %s (resume=%s)",
            job_posting_id,
            base_resume_id,
        )
        # Placeholder inputs — real data arrives when extraction is wired.
        return evaluate_tailoring_need(
            job_keywords=set(),
            summary_keywords=set(),
            bullet_skills=[],
            fit_score=0.0,
        )

    def _create_variant(
        self,
        base_resume_id: str | None,
        job_posting_id: str,
        _tailoring: TailoringDecision,
    ) -> None:
        """Create a tailored JobVariant from the base resume.

        REQ-018 §7.1 Step 4: LLM call for content generation.
        """
        logger.info(
            "Creating job variant for job %s from resume %s",
            job_posting_id,
            base_resume_id,
        )
        # Placeholder: no content generated yet.
        # Real implementation will call LLM and POST /job-variants.

    def _select_stories(
        self, persona_id: str, job_posting_id: str
    ) -> list[ScoredStory]:
        """Select achievement stories for the cover letter.

        REQ-018 §7.1 Step 5: Delegates to story_selection.py.
        """
        logger.info(
            "Selecting achievement stories for persona %s, job %s",
            persona_id,
            job_posting_id,
        )
        # Placeholder inputs — real data arrives when API client is wired.
        return select_achievement_stories(
            stories=[],
            job_skills=set(),
        )

    async def _generate_cover_letter(
        self,
        _persona_id: str,
        job_posting_id: str,
        stories: list[ScoredStory],
    ) -> CoverLetterResult:
        """Generate a cover letter with voice profile.

        REQ-018 §7.1 Step 6: Delegates to cover_letter_generation.py.
        """
        from app.services.cover_letter_generation import generate_cover_letter

        logger.info(
            "Generating cover letter for job %s (stories=%d)",
            job_posting_id,
            len(stories),
        )

        story_ids = [s.story_id for s in stories]

        # Placeholder values — real data arrives when API client is wired.
        return await generate_cover_letter(
            applicant_name="",
            current_title="",
            job=JobContext(
                job_title="",
                company_name="",
                top_skills="",
                culture_signals="",
                description_excerpt="",
            ),
            voice=VoiceProfileData(
                tone="",
                sentence_style="",
                vocabulary_level="",
                personality_markers="",
                preferred_phrases="",
                things_to_avoid="",
                writing_sample="",
            ),
            stories=[],
            stories_used=story_ids,
            provider=self._provider,
        )

    def _check_job_active(self, job_posting_id: str) -> bool:
        """Check if the target job posting is still active.

        REQ-018 §7.1 Step 7: Query job posting status.
        """
        logger.info("Checking if job %s is still active", job_posting_id)
        # Placeholder: assume job is still active.
        # Real implementation will query job_postings repository.
        return True

    def _build_review_response(
        self,
        tailoring: TailoringDecision,
        stories: list[ScoredStory],
        _job_posting_id: str,
    ) -> str:
        """Build user-facing reasoning explanation.

        REQ-018 §7.1 Step 8: Delegates to reasoning_explanation.py.
        """
        signal_details = [s.detail for s in tailoring.signals]

        reasoning_stories = [
            ReasoningStory(title=s.title, rationale=s.rationale) for s in stories
        ]

        # Placeholder job_title/company_name — real data arrives when
        # API client is wired to fetch job posting details.
        return format_agent_reasoning(
            job_title="",
            company_name="",
            tailoring_action=tailoring.action,
            tailoring_signal_details=signal_details,
            stories=reasoning_stories,
        )

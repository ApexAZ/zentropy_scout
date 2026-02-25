"""Strategist prompt templates for score rationale and non-negotiables.

REQ-017 §8: Prompt Specifications.

Contains two prompt sets:
1. Score Rationale (§8.1) — 2-3 sentence explanation of fit/stretch scores
2. Non-Negotiables Explanation (§8.2) — one sentence per failed requirement

Relocated from app.agents.strategist_prompts during LLM redesign (REQ-017 §5.2).
"""

from app.core.llm_sanitization import sanitize_llm_input
from app.schemas.prompt_params import ScoreData

# =============================================================================
# Score Rationale Prompts (§8.1)
# =============================================================================

# WHY: After calculating numeric scores, the Strategist generates a human-readable
# explanation. The system prompt establishes the analyst persona and output constraints.
# The user prompt provides structured match data for the LLM to interpret.

SCORE_RATIONALE_SYSTEM_PROMPT = """You are a career match analyst explaining job fit to a job seeker.

Your task: Given the match data, write a 2-3 sentence rationale that:
1. Highlights the strongest alignment (what makes this a good/poor fit)
2. Notes any significant gaps or stretch opportunities
3. Uses specific skill names, not vague language

Tone: Direct, helpful, specific. Avoid generic phrases like "great opportunity" or "good match."

Output format: Plain text, 2-3 sentences max."""

_SCORE_RATIONALE_USER_TEMPLATE = """Job: {job_title} at {company_name}

Fit Score: {fit_score}/100
- Hard skills match: {hard_skills_pct}% ({matched_hard_skills} of {required_hard_skills})
- Soft skills match: {soft_skills_pct}%
- Experience level: {experience_match} (job wants {job_years}, you have {persona_years})
- Logistics: {logistics_match}

Stretch Score: {stretch_score}/100
- Target role alignment: {role_alignment_pct}%
- Target skills in job: {target_skills_found}

Missing required skills: {missing_skills}
Bonus skills you have: {bonus_skills}

Write a 2-3 sentence rationale for this candidate."""


def build_score_rationale_prompt(
    *,
    job_title: str,
    company_name: str,
    scores: ScoreData,
) -> str:
    """Build the score rationale user prompt with match data.

    REQ-017 §8.1: Score Rationale Generation.

    Formats the user prompt template with scoring data for LLM interpretation.
    All string parameters are sanitized to mitigate prompt injection, since
    values like skill names and match descriptions may originate from
    web-scraped job postings.

    Args:
        job_title: Title of the job posting.
        company_name: Company offering the position.
        scores: Score breakdown data (fit, stretch, skills, experience, etc.).

    Returns:
        Formatted user prompt string for LLM completion.
    """
    return _SCORE_RATIONALE_USER_TEMPLATE.format(
        job_title=sanitize_llm_input(job_title),
        company_name=sanitize_llm_input(company_name),
        fit_score=scores.fit_score,
        hard_skills_pct=scores.hard_skills_pct,
        matched_hard_skills=scores.matched_hard_skills,
        required_hard_skills=scores.required_hard_skills,
        soft_skills_pct=scores.soft_skills_pct,
        experience_match=sanitize_llm_input(scores.experience_match),
        job_years=sanitize_llm_input(scores.job_years),
        persona_years=sanitize_llm_input(scores.persona_years),
        logistics_match=sanitize_llm_input(scores.logistics_match),
        stretch_score=scores.stretch_score,
        role_alignment_pct=scores.role_alignment_pct,
        target_skills_found=sanitize_llm_input(scores.target_skills_found),
        missing_skills=sanitize_llm_input(scores.missing_skills),
        bonus_skills=sanitize_llm_input(scores.bonus_skills),
    )


# =============================================================================
# Non-Negotiables Explanation Prompts (§8.2)
# =============================================================================

# WHY: When a job fails non-negotiables, the user needs a clear, factual explanation.
# No apologies or softening — just the facts about why the job was filtered.

NON_NEGOTIABLES_SYSTEM_PROMPT = """You explain why a job posting failed the user's non-negotiable requirements.

Be direct and factual. Don't apologize or soften the message.
One sentence per failed requirement."""

_NON_NEGOTIABLES_USER_TEMPLATE = """Job: {job_title} at {company_name}

Failed requirements:
{failed_list}

User's settings:
{user_non_negotiables}

Explain each failure in one sentence."""


def build_non_negotiables_prompt(
    *,
    job_title: str,
    company_name: str,
    failed_list: list[str],
    user_non_negotiables: dict[str, object],
) -> str:
    """Build the non-negotiables explanation user prompt.

    REQ-017 §8.2: Non-Negotiables Explanation.

    Formats the user prompt with failure details for LLM interpretation.
    All string values are sanitized to mitigate prompt injection, since
    failure reasons may contain text derived from web-scraped job postings.

    Args:
        job_title: Title of the job posting.
        company_name: Company offering the position.
        failed_list: List of failure reason strings.
        user_non_negotiables: Dictionary of user's non-negotiable settings.

    Returns:
        Formatted user prompt string for LLM completion.
    """
    failed_text = (
        "\n".join(f"- {sanitize_llm_input(reason)}" for reason in failed_list)
        if failed_list
        else "None"
    )
    settings_text = "\n".join(
        f"- {sanitize_llm_input(str(key))}: {sanitize_llm_input(str(value))}"
        for key, value in user_non_negotiables.items()
    )

    return _NON_NEGOTIABLES_USER_TEMPLATE.format(
        job_title=sanitize_llm_input(job_title),
        company_name=sanitize_llm_input(company_name),
        failed_list=failed_text,
        user_non_negotiables=settings_text,
    )

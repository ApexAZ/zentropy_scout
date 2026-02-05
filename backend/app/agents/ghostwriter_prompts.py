"""Ghostwriter Agent cover letter prompt templates.

REQ-010 §5.3: Cover Letter Generation Prompts.
REQ-007 §8.5: Cover Letter Generation.

Contains:
1. System prompt constant with writing rules and XML output format
2. User prompt template with XML-tagged sections
3. Builder function with sanitization and truncation

Pattern follows strategist_prompts.py: module-level constants + builder functions
with sanitize_llm_input().
"""

from app.core.llm_sanitization import sanitize_llm_input

# =============================================================================
# Constants
# =============================================================================

_MAX_DESCRIPTION_LENGTH = 1000
"""Maximum characters for job description excerpt in the prompt."""

_MAX_WRITING_SAMPLE_LENGTH = 2000
"""Maximum characters for voice profile writing sample."""

_MAX_FIELD_LENGTH = 500
"""Maximum characters for variable-length prompt fields (skills, culture, phrases)."""

_MAX_STORIES = 5
"""Maximum number of achievement stories to include in the prompt."""

# =============================================================================
# Cover Letter Prompts (REQ-010 §5.3)
# =============================================================================

# WHY: The system prompt establishes writing rules, output format, and safety
# constraints. The voice profile reference ensures authentic writing style.
# XML output tags enable structured parsing of the response.

COVER_LETTER_SYSTEM_PROMPT = """You are writing a cover letter for a job application.

CRITICAL RULES:
1. Write in the person's authentic voice (see <voice_profile>)
2. Reference ONLY the achievement stories provided — NO fabricated accomplishments
3. NEVER use phrases from their "things_to_avoid" list
4. Keep length between 250-350 words (3-4 short paragraphs)
5. Include a specific hook about THIS company (use culture signals)
6. End with a concrete call to action, NOT "I look forward to hearing from you"

STRUCTURE:
- Opening: Hook specific to this company/role (1-2 sentences)
- Body: 1-2 achievement stories with concrete impact (2 paragraphs)
- Close: Cultural fit + enthusiasm + call to action (1 paragraph)

OUTPUT FORMAT:
<cover_letter>
[The complete cover letter text — plain text, no formatting]
</cover_letter>

<agent_reasoning>
[2-3 sentences explaining your choices: why these stories, what you emphasized]
</agent_reasoning>"""

_COVER_LETTER_USER_TEMPLATE = """<voice_profile>
TONE: {tone}
SENTENCE STYLE: {sentence_style}
VOCABULARY: {vocabulary_level}
PERSONALITY: {personality_markers}

PREFERRED PHRASES (use these patterns):
{preferred_phrases}

NEVER USE THESE WORDS/PHRASES:
{things_to_avoid}

WRITING SAMPLE (internalize their voice):
<sample>
{writing_sample}
</sample>
</voice_profile>

<applicant>
Name: {applicant_name}
Current Title: {current_title}
</applicant>

<job_posting>
Title: {job_title}
Company: {company_name}

Key Requirements:
{top_skills}

Culture Signals:
{culture_signals}

Description Excerpt:
{description_excerpt}
</job_posting>

<selected_stories>
{stories_formatted}
</selected_stories>

Write the cover letter now."""


def _format_stories(stories: list[dict]) -> str:
    """Format achievement stories into XML-structured text.

    Args:
        stories: List of story dicts with title, rationale, context, action, outcome.

    Returns:
        Formatted stories text, or "No stories provided" if empty.
    """
    if not stories:
        return "No stories provided."

    parts: list[str] = []
    for idx, story in enumerate(stories[:_MAX_STORIES], start=1):
        title = sanitize_llm_input(story.get("title", "Untitled")[:_MAX_FIELD_LENGTH])
        rationale = sanitize_llm_input(story.get("rationale", "")[:_MAX_FIELD_LENGTH])
        context = sanitize_llm_input(story.get("context", "")[:_MAX_FIELD_LENGTH])
        action = sanitize_llm_input(story.get("action", "")[:_MAX_FIELD_LENGTH])
        outcome = sanitize_llm_input(story.get("outcome", "")[:_MAX_FIELD_LENGTH])

        parts.append(
            f"### Story {idx}: {title}\n"
            f"Selection Rationale: {rationale}\n\n"
            f"Context: {context}\n"
            f"Action: {action}\n"
            f"Outcome: {outcome}"
        )

    return "\n\n".join(parts)


def build_cover_letter_prompt(
    *,
    applicant_name: str,
    current_title: str,
    job_title: str,
    company_name: str,
    top_skills: str,
    culture_signals: str,
    description_excerpt: str,
    tone: str,
    sentence_style: str,
    vocabulary_level: str,
    personality_markers: str,
    preferred_phrases: str,
    things_to_avoid: str,
    writing_sample: str,
    stories: list[dict],
) -> str:
    """Build the cover letter user prompt with applicant, job, and voice data.

    REQ-010 §5.3: Cover Letter Generation Prompt.

    Formats the user prompt template with all required data for cover letter
    generation. All string parameters are sanitized to mitigate prompt injection,
    since values like job descriptions and skill names may originate from
    web-scraped job postings.

    The job description excerpt is truncated to _MAX_DESCRIPTION_LENGTH characters
    to keep prompt size bounded.

    Args:
        applicant_name: Full name of the applicant.
        current_title: Applicant's current job title.
        job_title: Title of the target job posting.
        company_name: Company offering the position.
        top_skills: Formatted string of top required skills.
        culture_signals: Culture information extracted from the job posting.
        description_excerpt: Raw job description text (truncated to 1000 chars).
        tone: Voice profile tone setting.
        sentence_style: Voice profile sentence style setting.
        vocabulary_level: Voice profile vocabulary level setting.
        personality_markers: Voice profile personality markers.
        preferred_phrases: Phrases the applicant likes to use.
        things_to_avoid: Words/phrases the applicant wants to avoid.
        writing_sample: Sample of the applicant's writing for voice matching.
        stories: List of story dicts with title, rationale, context, action, outcome.

    Returns:
        Formatted user prompt string for LLM completion.
    """
    # Truncate variable-length fields to respect size limits
    truncated_description = description_excerpt[:_MAX_DESCRIPTION_LENGTH]
    truncated_sample = (writing_sample or "No sample provided")[
        :_MAX_WRITING_SAMPLE_LENGTH
    ]

    stories_formatted = _format_stories(stories)

    return _COVER_LETTER_USER_TEMPLATE.format(
        applicant_name=sanitize_llm_input(applicant_name),
        current_title=sanitize_llm_input(current_title),
        job_title=sanitize_llm_input(job_title),
        company_name=sanitize_llm_input(company_name),
        top_skills=sanitize_llm_input((top_skills or "")[:_MAX_FIELD_LENGTH]),
        culture_signals=sanitize_llm_input(
            (culture_signals or "No specific culture information extracted")[
                :_MAX_FIELD_LENGTH
            ]
        ),
        description_excerpt=sanitize_llm_input(truncated_description),
        tone=sanitize_llm_input(tone or "Not specified"),
        sentence_style=sanitize_llm_input(sentence_style or "Not specified"),
        vocabulary_level=sanitize_llm_input(vocabulary_level or "Not specified"),
        personality_markers=sanitize_llm_input(
            (personality_markers or "None specified")[:_MAX_FIELD_LENGTH]
        ),
        preferred_phrases=sanitize_llm_input(
            (preferred_phrases or "None provided")[:_MAX_FIELD_LENGTH]
        ),
        things_to_avoid=sanitize_llm_input(
            (things_to_avoid or "None specified")[:_MAX_FIELD_LENGTH]
        ),
        writing_sample=sanitize_llm_input(truncated_sample),
        stories_formatted=stories_formatted,
    )

# REQ-010: Content Generation Specification

**Status:** Draft
**Version:** 0.1
**PRD Reference:** §4.4 Ghostwriter, §8 Document Management
**Last Updated:** 2026-01-25

---

## 1. Overview

This document specifies the content generation system for Zentropy Scout's Ghostwriter agent: prompt engineering, output formats, quality criteria, and validation rules for generating tailored resumes and cover letters.

**Key Principle:** Generated content must sound like the user, not a template. The Voice Profile (REQ-001 §3.7) guides all writing. The Ghostwriter enhances and tailors — it never fabricates accomplishments or skills.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| Resume summary tailoring | Full resume rewriting |
| Bullet reordering/emphasis | Adding new content not in Persona |
| Cover letter generation | Portfolio/project descriptions |
| Achievement story selection | Interview prep content |
| Voice Profile application | Social media content |
| Quality validation rules | Document formatting/PDF rendering |

### 1.2 Content Generation Principles

| Principle | Description | Enforcement |
|-----------|-------------|-------------|
| **Authenticity** | Output sounds like the user wrote it | Voice Profile applied to all generation |
| **Truthfulness** | No fabricated accomplishments or skills | Content sourced only from Persona data |
| **Tailoring over rewriting** | Adjust emphasis, not substance | Modification limits enforced (see §5.3) |
| **Transparency** | User understands what changed and why | `modifications_description` / `agent_reasoning` required |
| **Reversibility** | User can reject and get original back | BaseResume always preserved |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Data source | Achievement Stories, Voice Profile, Skills, Work History |
| REQ-002 Resume Schema v0.7 | Output target | BaseResume, JobVariant structure and constraints |
| REQ-002b Cover Letter v0.5 | Output target | CoverLetter structure |
| REQ-003 Job Posting v0.4 | Input data | Job requirements, keywords, `culture_text` |
| REQ-007 Agent Behavior v0.4 | Integration | Ghostwriter flow (§8), duplicate prevention |
| REQ-008 Scoring Algorithm v0.2 | Input data | Fit/Stretch scores inform tailoring priority |
| REQ-009 Provider Abstraction v0.2 | Infrastructure | Model routing for generation tasks |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| (Future) Implementation | Prompt templates | Exact prompts to implement |
| REQ-007 Agent Behavior | Content rules | Ghostwriter must follow these constraints |

---

## 3. Voice Profile Application

The Voice Profile (REQ-001 §3.7) is the foundation for all content generation. Every generated sentence must pass through this lens.

### 3.1 Voice Profile Fields

| Field | Type | Generation Impact |
|-------|------|-------------------|
| `tone` | String | Overall emotional register ("Direct, confident, avoids buzzwords") |
| `sentence_style` | String | Structural preferences ("Short sentences, active voice") |
| `vocabulary_level` | String | Word choice guidance ("Technical when relevant, otherwise plain English") |
| `personality_markers` | String | Distinctive characteristics ("Occasional dry humor, never self-deprecating") |
| `sample_phrases` | List | Preferred constructions ("I led...", "I built...", "The result was...") |
| `things_to_avoid` | List | Blacklisted words/phrases ("Passionate", "Synergy", "Think outside the box") |

### 3.2 Voice Application Rules

**Rule 1: Avoid blacklisted terms absolutely**
```python
def validate_no_blacklist(text: str, voice_profile: VoiceProfile) -> list[str]:
    """Return list of violations found."""
    violations = []
    for term in voice_profile.things_to_avoid:
        if term.lower() in text.lower():
            violations.append(f"Contains blacklisted term: '{term}'")
    return violations
# WHY: User explicitly said they don't want these words. No exceptions.
```

**Rule 2: Use sample phrases as templates**
```python
# Good: "I led the migration to Kubernetes, resulting in 40% cost reduction."
# (Uses "I led..." pattern from sample_phrases)

# Bad: "Was responsible for leading the migration to Kubernetes..."
# (Passive voice, doesn't match sample patterns)
```

**Rule 3: Match sentence length to style**
```python
# If sentence_style = "Short sentences, active voice"
# Good: "I built the API. It handles 10M requests daily."
# Bad: "I built the API, which was designed to handle high throughput and currently processes approximately 10 million requests on a daily basis."
```

### 3.3 Voice Profile System Prompt Block

This block is included in ALL content generation prompts:

```
<voice_profile>
You are writing as {persona.full_name}. Match their voice exactly.

TONE: {voice_profile.tone}
SENTENCE STYLE: {voice_profile.sentence_style}
VOCABULARY: {voice_profile.vocabulary_level}
PERSONALITY: {voice_profile.personality_markers}

PREFERRED PHRASES (use these patterns):
{voice_profile.sample_phrases | join('\n- ')}

NEVER USE THESE WORDS/PHRASES:
{voice_profile.things_to_avoid | join(', ')}

Read their existing writing samples to internalize their voice:
<writing_sample>
{voice_profile.writing_sample_text}
</writing_sample>
</voice_profile>
```

---

## 4. Resume Tailoring

### 4.1 Tailoring Decision Logic

The Ghostwriter evaluates whether a JobVariant is needed:

```python
def evaluate_tailoring_need(
    base_resume: BaseResume,
    job_posting: JobPosting,
    fit_score: float
) -> TailoringDecision:
    """
    Determine if/how to tailor the resume.

    Returns:
        TailoringDecision with action and reasoning
    """
    signals = []

    # Signal 1: Keyword gaps in summary
    job_keywords = extract_keywords(job_posting.description)
    summary_keywords = extract_keywords(base_resume.summary)
    missing_keywords = job_keywords - summary_keywords
    keyword_gap = len(missing_keywords) / len(job_keywords) if job_keywords else 0

    if keyword_gap > 0.3:  # More than 30% of job keywords missing
        signals.append(TailoringSignal(
            type="keyword_gap",
            priority=keyword_gap,
            detail=f"Summary missing {len(missing_keywords)} key terms: {list(missing_keywords)[:5]}"
        ))

    # Signal 2: Bullet relevance mismatch
    job_skills = {s.skill_name.lower() for s in job_posting.extracted_skills}
    for job_id, bullet_order in base_resume.job_bullet_order.items():
        for idx, bullet_id in enumerate(bullet_order[:3]):  # Check top 3 bullets
            bullet = get_bullet(bullet_id)
            bullet_skills = extract_skills_from_text(bullet.text)
            if not (bullet_skills & job_skills) and job_skills:
                signals.append(TailoringSignal(
                    type="bullet_relevance",
                    priority=0.5 - (idx * 0.1),  # Higher priority for position 1
                    detail=f"Top bullet in {job_id} doesn't highlight required skills"
                ))

    # Decision matrix
    if not signals:
        return TailoringDecision(
            action="use_base",
            reasoning="BaseResume aligns well with job requirements. No tailoring needed."
        )

    total_priority = sum(s.priority for s in signals)
    if total_priority < 0.3:
        return TailoringDecision(
            action="use_base",
            reasoning=f"Minor gaps detected but not significant enough to warrant tailoring."
        )

    return TailoringDecision(
        action="create_variant",
        signals=signals,
        reasoning=f"Tailoring recommended: {'; '.join(s.detail for s in signals[:3])}"
    )
# WHY: We don't want to create variants for every job. Only when there's
# meaningful improvement to be gained. This reduces user review burden.
```

### 4.2 Summary Tailoring Prompt

**Task Type:** `TaskType.RESUME_TAILORING` → Routes to Sonnet/GPT-4o (REQ-009 §4.1)

**System Prompt:**
```
You are tailoring a professional summary for a job application.

RULES:
1. Keep the same length (±10 words) as the original
2. Preserve the person's authentic voice (see <voice_profile>)
3. Only adjust emphasis — do NOT add claims not supported by the original
4. Naturally incorporate 2-3 keywords from the job posting
5. Do NOT use any words from the blacklist

OUTPUT FORMAT:
<tailored_summary>
[Your tailored summary here — plain text, no formatting]
</tailored_summary>

<changes_made>
[1-2 sentences explaining what you adjusted and why]
</changes_made>
```

**User Prompt:**
```
<voice_profile>
{voice_profile_block}
</voice_profile>

<original_summary>
{base_resume.summary}
</original_summary>

<job_posting>
Title: {job_posting.job_title}
Company: {job_posting.company_name}

Key Requirements:
{job_posting.extracted_skills | format_as_list}

Description Excerpt:
{job_posting.description[:1500]}
</job_posting>

<keywords_to_incorporate>
{missing_keywords | join(', ')}
</keywords_to_incorporate>

Tailor the summary to better align with this role while maintaining the person's voice.
```

**Example Input/Output:**

Original Summary:
> Experienced software engineer with 8 years building scalable web applications. Led teams of 3-8 engineers. Strong background in Python and distributed systems.

Job Posting Keywords: `Kubernetes`, `microservices`, `AWS`, `team leadership`

Tailored Output:
```xml
<tailored_summary>
Experienced software engineer with 8 years building scalable web applications and microservices. Led teams of 3-8 engineers on AWS infrastructure. Strong background in Python and distributed systems.
</tailored_summary>

<changes_made>
Added "microservices" (mentioned 4x in posting) and "AWS" (required skill). Kept same structure and voice. Did not add Kubernetes — not in original experience.
</changes_made>
```

### 4.3 Bullet Reordering Logic

Bullets are reordered to surface the most relevant accomplishments first.

```python
def calculate_bullet_relevance(
    bullet: Bullet,
    job_posting: JobPosting,
    persona: Persona
) -> float:
    """
    Score a bullet's relevance to the job posting.

    Returns:
        Float 0.0-1.0 where higher = more relevant
    """
    score = 0.0
    job_skills = {s.skill_name.lower() for s in job_posting.extracted_skills}

    # Factor 1: Skill overlap (40%)
    bullet_skills = extract_skills_from_text(bullet.text)
    if job_skills:
        skill_overlap = len(bullet_skills & job_skills) / len(job_skills)
        score += skill_overlap * 0.4

    # Factor 2: Keyword presence (30%)
    job_keywords = extract_keywords(job_posting.description)
    bullet_keywords = extract_keywords(bullet.text)
    if job_keywords:
        keyword_overlap = len(bullet_keywords & job_keywords) / len(job_keywords)
        score += keyword_overlap * 0.3

    # Factor 3: Quantified outcome bonus (20%)
    if has_metrics(bullet.text):
        score += 0.2

    # Factor 4: Recency boost (10%)
    # Bullets from current/recent jobs get a boost
    if bullet.job_id:
        job_entry = get_work_history(bullet.job_id)
        if job_entry.is_current:
            score += 0.1
        elif job_entry.end_date and is_recent(job_entry.end_date, months=24):
            score += 0.05

    return min(score, 1.0)

def reorder_bullets_for_job(
    base_resume: BaseResume,
    job_posting: JobPosting,
    persona: Persona
) -> dict[str, list[str]]:
    """
    Return new bullet ordering per job entry.

    Returns:
        Dict mapping job_id → ordered list of bullet_ids
    """
    new_order = {}

    for job_id, bullet_ids in base_resume.job_bullet_order.items():
        scored_bullets = []
        for bullet_id in bullet_ids:
            bullet = get_bullet(bullet_id)
            relevance = calculate_bullet_relevance(bullet, job_posting, persona)
            scored_bullets.append((bullet_id, relevance))

        # Sort by relevance descending, but preserve relative order for ties
        scored_bullets.sort(key=lambda x: -x[1])
        new_order[job_id] = [b[0] for b in scored_bullets]

    return new_order
# WHY: The most relevant accomplishment should be position 1 since many
# recruiters only read the first bullet. We're not changing content, just
# what they see first.
```

### 4.4 Modification Limits (Guardrails)

The Ghostwriter has strict boundaries on what it can modify:

| ✅ ALLOWED | ❌ FORBIDDEN |
|------------|-------------|
| Reorder bullets within a job entry | Add bullets not in Persona |
| Adjust summary wording (tone, emphasis) | Rewrite summary completely |
| Highlight different skills from BaseResume's skill list | Add skills not in Persona |
| Minor word choice changes matching Voice Profile | Change job titles |
| | Change company names |
| | Change dates |
| | Add accomplishments not documented |
| | Fabricate metrics |

**Validation Function:**
```python
def validate_variant_modifications(
    base_resume: BaseResume,
    job_variant: JobVariant,
    persona: Persona
) -> list[str]:
    """
    Validate that variant doesn't exceed modification limits.

    Returns:
        List of violation messages (empty = valid)
    """
    violations = []

    # Check 1: Bullet IDs must be subset of base
    base_bullets = set()
    for bullets in base_resume.job_bullet_selections.values():
        base_bullets.update(bullets)

    variant_bullets = set()
    for bullets in job_variant.job_bullet_order.values():
        variant_bullets.update(bullets)

    new_bullets = variant_bullets - base_bullets
    if new_bullets:
        violations.append(f"Variant contains bullets not in BaseResume: {new_bullets}")

    # Check 2: Summary length within ±20%
    base_words = len(base_resume.summary.split())
    variant_words = len(job_variant.summary.split())
    length_change = abs(variant_words - base_words) / base_words
    if length_change > 0.2:
        violations.append(f"Summary length changed by {length_change:.0%} (max 20%)")

    # Check 3: Summary doesn't contain skills not in Persona
    persona_skills = {s.skill_name.lower() for s in persona.skills}
    summary_skills = extract_skills_from_text(job_variant.summary)
    new_skills = summary_skills - persona_skills
    if new_skills:
        violations.append(f"Summary mentions skills not in Persona: {new_skills}")

    return violations
# WHY: These guardrails prevent the Ghostwriter from overstepping. The user
# trusts that their resume accurately reflects their experience.
```

---

## 5. Cover Letter Generation

### 5.1 Cover Letter Structure

Every generated cover letter follows this structure:

| Section | Purpose | Length |
|---------|---------|--------|
| **Hook** | Grab attention with company/role-specific opening | 1-2 sentences |
| **Value Proposition** | Why you're a great fit (skills + experience match) | 2-3 sentences |
| **Achievement Highlight** | Specific story demonstrating relevant capability | 3-4 sentences |
| **Cultural Alignment** | Show you understand their values/mission | 1-2 sentences |
| **Closing** | Call to action + enthusiasm | 1-2 sentences |

**Total Target Length:** 250-350 words (fits on one page with standard formatting)

### 5.2 Achievement Story Selection

```python

def select_achievement_stories(
    persona: Persona,
    job_posting: JobPosting,
    max_stories: int = 2
) -> list[ScoredStory]:
    """
    Select the best achievement stories for a cover letter.

    WHY: 2 stories is optimal — enough to show a pattern of success
    without overwhelming. 3 max for senior/executive roles.

    Returns:
        List of ScoredStory with story, score, and selection rationale
    """
    job_skills = {s.skill_name.lower() for s in job_posting.extracted_skills}
    recent_apps = get_recent_applications(persona.id, days=30)

    scored_stories = []
    for story in persona.achievement_stories:
        score = 0.0
        rationale_parts = []

        # Factor 1: Skills match (0-40 points)
        story_skills = {s.lower() for s in story.skills_demonstrated}
        overlap = job_skills & story_skills
        skill_score = min(len(overlap) * 10, 40)
        score += skill_score
        if overlap:
            rationale_parts.append(f"Demonstrates {', '.join(list(overlap)[:3])}")

        # Factor 2: Recency (0-20 points)
        if story.related_job_id:
            job_entry = get_work_history(persona, story.related_job_id)
            if job_entry:
                if job_entry.is_current:
                    score += 20
                    rationale_parts.append("From current role")
                elif is_recent(job_entry.end_date, months=24):
                    score += 15
                    rationale_parts.append("Recent experience (last 2 years)")
                elif is_recent(job_entry.end_date, months=48):
                    score += 10

        # Factor 3: Quantified outcome (0-15 points)
        if has_metrics(story.outcome):
            score += 15
            rationale_parts.append("Quantified impact")

        # Factor 4: Culture alignment (0-15 points)
        # WHY: culture_text is LLM-extracted (REQ-007 §6.4), not raw description
        if job_posting.culture_text:
            culture_keywords = extract_keywords(job_posting.culture_text)
            story_text = f"{story.context} {story.action} {story.outcome}"
            culture_matches = count_keyword_matches(story_text, culture_keywords)
            culture_score = min(culture_matches * 5, 15)
            score += culture_score
            if culture_matches > 0:
                rationale_parts.append("Aligns with company culture")

        # Factor 5: Freshness penalty (-10 points)
        # WHY: Avoid repetition across applications
        recent_uses = count_story_uses(story.id, recent_apps, days=30)
        if recent_uses >= 3:
            score -= 10
            rationale_parts.append(f"Used {recent_uses}x recently (penalty)")

        rationale = "; ".join(rationale_parts) if rationale_parts else "General match"
        scored_stories.append(ScoredStory(
            story=story,
            score=score,
            rationale=rationale
        ))

    # Sort by score descending
    scored_stories.sort(key=lambda x: x.score, reverse=True)

    return scored_stories[:max_stories]
```

### 5.3 Cover Letter Generation Prompt

**Task Type:** `TaskType.COVER_LETTER` → Routes to Sonnet/GPT-4o (REQ-009 §4.1)

**System Prompt:**
```
You are writing a cover letter for a job application.

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
</agent_reasoning>
```

**User Prompt Template:**
```
<voice_profile>
TONE: {voice_profile.tone}
SENTENCE STYLE: {voice_profile.sentence_style}
VOCABULARY: {voice_profile.vocabulary_level}
PERSONALITY: {voice_profile.personality_markers or "None specified"}

PREFERRED PHRASES (use these patterns):
{voice_profile.sample_phrases | format_list or "None provided"}

NEVER USE THESE WORDS/PHRASES:
{voice_profile.things_to_avoid | join(", ") or "None specified"}

WRITING SAMPLE (internalize their voice):
<sample>
{voice_profile.writing_sample_text or "No sample provided"}
</sample>
</voice_profile>

<applicant>
Name: {persona.full_name}
Current Title: {persona.current_job_title}
</applicant>

<job_posting>
Title: {job_posting.job_title}
Company: {job_posting.company_name}

Key Requirements:
{for skill in job_posting.extracted_skills[:5]}
- {skill.skill_name} ({skill.importance_level})
{endfor}

Culture Signals:
{job_posting.culture_text or "No specific culture information extracted"}

Description Excerpt:
{job_posting.description[:1000]}
</job_posting>

<selected_stories>
{for idx, scored_story in enumerate(selected_stories)}
### Story {idx + 1}: {scored_story.story.title}
Selection Rationale: {scored_story.rationale}

Context: {scored_story.story.context}
Action: {scored_story.story.action}
Outcome: {scored_story.story.outcome}
{endfor}
</selected_stories>

Write the cover letter now.
```

### 5.4 Cover Letter Validation

```python
@dataclass
class CoverLetterValidation:
    passed: bool
    issues: list[ValidationIssue]
    word_count: int

@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    rule: str
    message: str

def validate_cover_letter(
    draft_text: str,
    voice_profile: VoiceProfile,
    selected_stories: list[ScoredStory],
    job_posting: JobPosting
) -> CoverLetterValidation:
    """
    Validate generated cover letter before presenting to user.

    WHY: Catching issues automatically improves trust in the system
    and reduces regeneration cycles.
    """
    issues = []
    word_count = len(draft_text.split())

    # Rule 1: Length check (250-350 words)
    if word_count < 250:
        issues.append(ValidationIssue(
            severity="error",
            rule="length_min",
            message=f"Too short: {word_count} words (minimum 250)"
        ))
    elif word_count > 350:
        issues.append(ValidationIssue(
            severity="warning",
            rule="length_max",
            message=f"Long: {word_count} words (target 250-350)"
        ))

    # Rule 2: Voice adherence — no blacklisted phrases
    if voice_profile.things_to_avoid:
        for phrase in voice_profile.things_to_avoid:
            if phrase.lower() in draft_text.lower():
                issues.append(ValidationIssue(
                    severity="error",
                    rule="blacklist_violation",
                    message=f"Contains avoided phrase: '{phrase}'"
                ))

    # Rule 3: Company specificity — name in opening
    first_paragraph = draft_text.split('\n\n')[0] if '\n\n' in draft_text else draft_text[:500]
    if job_posting.company_name.lower() not in first_paragraph.lower():
        issues.append(ValidationIssue(
            severity="warning",
            rule="company_specificity",
            message="Company name not in opening paragraph"
        ))

    # Rule 4: Story accuracy — spot-check metrics
    for scored_story in selected_stories:
        metrics = extract_metrics(scored_story.story.outcome)
        for metric in metrics:
            # If metric appears in draft, verify it's attributed correctly
            if metric in draft_text:
                if not metric_appears_in_context(draft_text, metric, scored_story.story):
                    issues.append(ValidationIssue(
                        severity="error",
                        rule="metric_accuracy",
                        message=f"Metric '{metric}' may be misattributed"
                    ))

    # Rule 5: No fabrication — check for skills not in persona
    # (This is a heuristic; full verification requires LLM)
    draft_skills = extract_skills_from_text(draft_text)
    story_skills = set()
    for ss in selected_stories:
        story_skills.update(s.lower() for s in ss.story.skills_demonstrated)

    suspicious_skills = draft_skills - story_skills
    if len(suspicious_skills) > 3:  # Allow some flexibility
        issues.append(ValidationIssue(
            severity="warning",
            rule="potential_fabrication",
            message=f"Draft mentions skills not in selected stories: {list(suspicious_skills)[:3]}"
        ))

    passed = not any(issue.severity == "error" for issue in issues)

    return CoverLetterValidation(
        passed=passed,
        issues=issues,
        word_count=word_count
    )
# WHY: Automated validation catches common generation errors. Errors block
# presentation to user; warnings are shown but don't block.
```

### 5.5 Cover Letter Output Schema

```python
@dataclass
class GeneratedCoverLetter:
    """Output from cover letter generation."""
    draft_text: str
    agent_reasoning: str
    word_count: int
    stories_used: list[UUID]  # For traceability (REQ-002b §4.1)
    validation: CoverLetterValidation

    def to_cover_letter_record(self, persona_id: UUID, job_posting_id: UUID) -> dict:
        """Convert to database record format."""
        return {
            "id": uuid4(),
            "persona_id": persona_id,
            "job_posting_id": job_posting_id,
            "achievement_stories_used": self.stories_used,
            "draft_text": self.draft_text,
            "final_text": None,  # Set on approval
            "status": "Draft",
            "agent_reasoning": self.agent_reasoning,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
```

---

## 6. Utility Functions

These functions are referenced throughout the document. They are NOT simple regex — they require LLM calls for accuracy.

### 6.1 Implementation Strategy

| Function | Implementation | Model | Rationale |
|----------|----------------|-------|-----------|
| `extract_keywords` | LLM call | Haiku | Semantic understanding needed; regex misses synonyms |
| `extract_skills_from_text` | LLM call | Haiku | Must recognize skill variants ("K8s" = "Kubernetes") |
| `has_metrics` | Regex + LLM | Regex first, Haiku fallback | Regex catches obvious patterns; LLM catches subtle ones |
| `extract_metrics` | LLM call | Haiku | Must parse context ("reduced by 40%" vs "40% of team") |
| `count_keyword_matches` | String matching | None | Simple after keywords extracted |

### 6.2 extract_keywords

```python
async def extract_keywords(
    text: str,
    max_keywords: int = 20
) -> set[str]:
    """
    Extract meaningful keywords from text using LLM.

    WHY: Regex/NLTK miss semantic meaning. "distributed systems" should be
    one keyword, not two. "K8s" should normalize to "Kubernetes".

    Args:
        text: Source text (job description, resume summary, etc.)
        max_keywords: Maximum keywords to return

    Returns:
        Set of lowercase normalized keywords
    """
    llm = get_llm_provider()

    response = await llm.complete(
        task=TaskType.EXTRACTION,  # Routes to Haiku
        messages=[
            {
                "role": "system",
                "content": """Extract the most important keywords from the text.

RULES:
1. Include technical skills, tools, methodologies
2. Normalize variants (K8s → Kubernetes, JS → JavaScript)
3. Keep multi-word terms together ("distributed systems", not "distributed" + "systems")
4. Lowercase everything
5. Output as JSON array only, no other text

Example: ["kubernetes", "python", "distributed systems", "team leadership"]"""
            },
            {
                "role": "user",
                "content": f"Extract keywords from:\n\n{text[:2000]}"
            }
        ],
        max_tokens=500
    )

    try:
        keywords = json.loads(response.content)
        return set(k.lower() for k in keywords[:max_keywords])
    except json.JSONDecodeError:
        # Fallback: simple word extraction
        return set(text.lower().split())[:max_keywords]
```

### 6.3 extract_skills_from_text

```python
async def extract_skills_from_text(
    text: str,
    persona_skills: set[str] = None
) -> set[str]:
    """
    Extract skill mentions from free text using LLM.

    WHY: Skills appear in many forms. "Led Python development" contains
    "Python" and "Leadership". Regex can't reliably extract these.

    Args:
        text: Text to analyze
        persona_skills: Optional set of known skills to bias toward

    Returns:
        Set of lowercase skill names found
    """
    llm = get_llm_provider()

    skill_hint = ""
    if persona_skills:
        skill_hint = f"\n\nKnown skills to look for: {', '.join(list(persona_skills)[:30])}"

    response = await llm.complete(
        task=TaskType.EXTRACTION,
        messages=[
            {
                "role": "system",
                "content": f"""Identify skills mentioned in the text.

RULES:
1. Include both explicit ("Python") and implicit ("led the team" → leadership)
2. Normalize to standard names (JS → JavaScript, ML → Machine Learning)
3. Include soft skills (communication, leadership, problem-solving)
4. Lowercase everything
5. Output as JSON array only{skill_hint}"""
            },
            {
                "role": "user",
                "content": f"Extract skills from:\n\n{text[:1500]}"
            }
        ],
        max_tokens=300
    )

    try:
        skills = json.loads(response.content)
        return set(s.lower() for s in skills)
    except json.JSONDecodeError:
        return set()
```

### 6.4 has_metrics and extract_metrics

```python
import re

# Common metric patterns for fast regex check
METRIC_PATTERNS = [
    r'\d+%',                    # 40%
    r'\$[\d,]+[KMB]?',          # $1.2M, $500K
    r'\d+x',                    # 10x improvement
    r'\d+\s*(users|customers|clients|engineers|teams)',  # 500 users
    r'reduced.*by\s*\d+',       # reduced by 30
    r'increased.*by\s*\d+',     # increased by 50
    r'saved.*\$?[\d,]+',        # saved $100K
]

def has_metrics(text: str) -> bool:
    """
    Quick check if text contains quantified metrics.

    WHY: Fast regex check handles 80% of cases. Avoids LLM call
    for obvious cases.
    """
    text_lower = text.lower()
    for pattern in METRIC_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

async def extract_metrics(text: str) -> list[str]:
    """
    Extract specific metric values from text.

    WHY: Need to verify metrics in generated content match source.
    "Reduced costs by 40%" should extract "40%" for comparison.

    Returns:
        List of metric strings found (e.g., ["40%", "$1.2M", "500 users"])
    """
    # Fast path: regex extraction
    metrics = []
    for pattern in METRIC_PATTERNS:
        matches = re.findall(pattern, text.lower())
        metrics.extend(matches)

    if metrics:
        return list(set(metrics))

    # Slow path: LLM for subtle metrics
    llm = get_llm_provider()
    response = await llm.complete(
        task=TaskType.EXTRACTION,
        messages=[
            {
                "role": "system",
                "content": """Extract quantified metrics from the text.

Look for: percentages, dollar amounts, user counts, time savings,
multipliers (10x), team sizes, etc.

Output as JSON array of strings. If no metrics found, output [].
Example: ["40%", "$1.2M", "500 users", "3x faster"]"""
            },
            {
                "role": "user",
                "content": text[:1000]
            }
        ],
        max_tokens=200
    )

    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return []
```

### 6.5 Caching Strategy

Utility function results should be cached to reduce LLM calls:

```python
from functools import lru_cache
import hashlib

def text_hash(text: str) -> str:
    """Generate cache key from text."""
    return hashlib.md5(text.encode()).hexdigest()[:16]

# In-memory cache for session
_keyword_cache: dict[str, set[str]] = {}

async def extract_keywords_cached(text: str, max_keywords: int = 20) -> set[str]:
    """Cached version of extract_keywords."""
    cache_key = f"kw:{text_hash(text)}:{max_keywords}"

    if cache_key in _keyword_cache:
        return _keyword_cache[cache_key]

    result = await extract_keywords(text, max_keywords)
    _keyword_cache[cache_key] = result
    return result

# WHY: Job descriptions and persona data don't change during a generation
# session. Caching prevents redundant LLM calls.
```

---

## 7. Regeneration Handling

When users request regeneration ("try a different approach"), the system modifies the prompt based on feedback.

### 7.1 Feedback Categories

| Feedback Type | Example | Prompt Modification |
|---------------|---------|---------------------|
| **Story rejection** | "Don't use the failing project story" | Exclude story, select next best |
| **Tone adjustment** | "Make it less formal" | Add tone override to voice block |
| **Length adjustment** | "Make it shorter" | Adjust word count target |
| **Focus shift** | "Focus more on technical skills" | Add emphasis instruction |
| **Complete redo** | "Start fresh" | Clear context, regenerate |

### 7.2 Feedback Sanitization

```python
def sanitize_user_feedback(feedback: str) -> str:
    """
    Remove potential prompt injection from user feedback.

    WHY: Feedback is inserted into prompts. Must prevent injection.
    """
    # Patterns that could hijack the prompt
    dangerous_patterns = [
        r"ignore\s+(all\s+)?(previous|above|prior)",
        r"disregard\s+(all\s+)?(previous|above|prior)",
        r"new\s+instructions",
        r"system\s*:",
        r"<\|",
        r"\|\>",
        r"```system",
        r"IMPORTANT:",
        r"OVERRIDE:",
    ]

    sanitized = feedback
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "[FILTERED]", sanitized, flags=re.IGNORECASE)

    # Truncate to reasonable length
    return sanitized[:500]

# WHY: Users can't inject instructions through the feedback mechanism.
```

### 7.3 Regeneration Prompt Modifier

```python
def build_regeneration_context(
    original_prompt: str,
    feedback: str,
    excluded_story_ids: list[UUID] = None,
    tone_override: str = None,
    word_count_target: tuple[int, int] = None
) -> str:
    """
    Modify prompt for regeneration based on user feedback.
    """
    modifier_parts = ["\n\n<regeneration_context>"]
    modifier_parts.append("The user reviewed the previous draft and provided feedback.")

    # Add sanitized feedback
    safe_feedback = sanitize_user_feedback(feedback)
    modifier_parts.append(f'\nFeedback: "{safe_feedback}"')

    # Add specific overrides
    if excluded_story_ids:
        modifier_parts.append(f"\nDo NOT reference these story IDs: {excluded_story_ids}")

    if tone_override:
        modifier_parts.append(f"\nTone adjustment: {tone_override}")

    if word_count_target:
        modifier_parts.append(f"\nTarget length: {word_count_target[0]}-{word_count_target[1]} words")

    modifier_parts.append("\nIncorporate this feedback while following all other rules.")
    modifier_parts.append("</regeneration_context>")

    return original_prompt + "\n".join(modifier_parts)
```

---

## 8. Edge Cases

### 8.1 Insufficient Data

| Scenario | Detection | Handling |
|----------|-----------|----------|
| No achievement stories | `len(persona.achievement_stories) == 0` | Skip cover letter; explain to user |
| Voice profile incomplete | Required fields missing | Use sensible defaults + warning |
| No matching stories | All scores < 20 | Use top 2 anyway with disclaimer |
| Job posting minimal | `len(extracted_skills) < 2` | Generate with generic approach; flag for review |
| No culture_text | `job_posting.culture_text is None` | Skip culture alignment section |

### 8.2 Expired Job During Generation

(Cross-reference: REQ-007 §10.4.4)

```python
async def generate_with_expiry_check(
    job_posting: JobPosting,
    persona: Persona
) -> GenerationResult:
    """Handle job expiring mid-generation."""

    # Check before starting
    if job_posting.status == "Expired":
        return GenerationResult(
            success=False,
            error="Job posting has expired",
            suggestion="Search for similar active postings?"
        )

    # Generate content
    result = await generate_materials(job_posting, persona)

    # Check after generation (may have expired during)
    job_posting = await refresh_job_posting(job_posting.id)
    if job_posting.status == "Expired":
        result.warnings.append(
            "Note: This job posting may no longer be active. "
            "Materials saved in case you have an alternative application path."
        )

    return result

# WHY: Don't waste the user's generated content. They may know a recruiter
# or have the job saved elsewhere.
```

### 8.3 Persona Changed During Generation

(Cross-reference: REQ-007 §10.4.1)

```python
async def generate_with_persona_version(
    job_posting: JobPosting,
    persona: Persona
) -> GenerationResult:
    """Detect persona changes during generation."""

    original_updated_at = persona.updated_at

    # Generate content (may take 10-30 seconds)
    result = await generate_materials(job_posting, persona)

    # Check if persona changed
    current_persona = await get_persona(persona.id)
    if current_persona.updated_at != original_updated_at:
        result.persona_changed = True
        result.warnings.append(
            "Your profile was updated during generation. "
            "Want to regenerate with your latest information?"
        )

    return result
```

### 8.4 Duplicate Story Selection

| Scenario | Handling |
|----------|----------|
| Only 1 story available | Use single story; generate shorter letter (200-250 words) |
| Top 2 stories from same job | Use both if outcomes differ; otherwise substitute #3 |
| User excluded all high-scoring stories | Use best available with disclaimer |
| All stories used recently (freshness penalty) | Ignore penalty; better to repeat than skip |

---

## 9. Agent Reasoning Output

The Ghostwriter explains its choices to build user trust (REQ-007 §8.7).

### 9.1 Reasoning Template

```python
def format_agent_reasoning(
    tailoring_decision: TailoringDecision,
    selected_stories: list[ScoredStory],
    job_posting: JobPosting
) -> str:
    """
    Generate user-facing explanation of generation choices.

    WHY: Transparency helps users provide better feedback and builds
    trust that the system isn't making things up.
    """
    lines = [f"I've prepared materials for **{job_posting.job_title}** at **{job_posting.company_name}**:\n"]

    # Resume tailoring explanation
    if tailoring_decision.action == "create_variant":
        lines.append("**Resume Adjustments:**")
        for signal in tailoring_decision.signals[:3]:
            lines.append(f"- {signal.detail}")
        lines.append("")
    else:
        lines.append("**Resume:** Your base resume aligns well — no changes needed.\n")

    # Cover letter explanation
    lines.append("**Cover Letter Stories:**")
    for ss in selected_stories:
        lines.append(f"- *{ss.story.title}* — {ss.rationale}")

    lines.append("\nReady for your review!")

    return "\n".join(lines)
```

### 9.2 Example Output

```
I've prepared materials for **Agile Coach** at **Innovate Corp**:

**Resume Adjustments:**
- Summary missing key terms: added emphasis on "SAFe" and "enterprise transformation"
- Reordered bullets in TechCorp role to lead with SAFe implementation (was position 4)

**Cover Letter Stories:**
- *Turned around failing project* — Demonstrates leadership; aligns with company culture
- *Scaled Agile adoption* — Demonstrates SAFe, Agile Coaching; quantified impact

Ready for your review!
```

---

## 10. Quality Metrics

### 10.1 Generation Quality Tracking

| Metric | Measurement | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **First-draft approval rate** | Approved without regeneration | > 60% | < 40% |
| **Validation pass rate** | Pass automated checks | > 90% | < 80% |
| **Avg regenerations per letter** | Count regeneration requests | < 1.5 | > 2.5 |
| **Voice adherence score** | Manual review sample (1-5) | > 4.0 | < 3.0 |
| **Story selection satisfaction** | User kept selected stories | > 70% | < 50% |

### 10.2 Feedback Loop

```python
async def log_generation_outcome(
    generation_id: UUID,
    outcome: str,  # "approved" | "regenerated" | "abandoned"
    feedback: str = None,
    regeneration_reason: str = None
):
    """
    Log outcome for quality tracking.

    WHY: Aggregate data reveals prompt improvement opportunities.
    """
    await analytics.track("content_generation_outcome", {
        "generation_id": str(generation_id),
        "outcome": outcome,
        "feedback_category": categorize_feedback(feedback) if feedback else None,
        "regeneration_reason": regeneration_reason,
        "timestamp": datetime.utcnow().isoformat()
    })
```

---

## 11. Design Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Bullet reordering only (no rewriting) | Reorder / Rewrite / Hybrid | Reorder only | Prevents hallucination; maintains user's authentic voice |
| 2-3 stories per cover letter | 1-2 / 2-3 / Unlimited | 2-3 | Shows pattern without overwhelming; fits letter structure |
| LLM for keyword extraction | Regex / NLTK / LLM | LLM (Haiku) | Semantic understanding needed; regex misses synonyms |
| Validate all before user review | Skip / Validate all / Sample | Validate all | Builds trust; automated checks are cheap |
| Sanitize user feedback | Trust input / Sanitize | Sanitize | Feedback goes into prompts; prevents injection |
| Cache utility function results | No cache / Session cache / Persistent | Session cache | Reduces LLM calls; data doesn't change mid-session |
| Complete generation if job expires | Abort / Complete + warn | Complete + warn | User may have alternative path; don't waste work |

---

## 12. Open Questions

| Question | Impact | Proposed Resolution |
|----------|--------|---------------------|
| Should bullet rewriting be added post-MVP? | User satisfaction, complexity | Evaluate based on regeneration feedback |
| How to handle multilingual personas? | Generation quality | Detect language; use appropriate prompts |
| Should we fine-tune for voice matching? | Quality, cost | Evaluate after MVP with real user data |
| How to handle very long achievement stories? | Token limits | Truncate or summarize in preprocessing |

---

## 13. Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-01-25 | Initial draft | Claude |

---

## Appendix A: Complete Generation Example

### A.1 Input Data

```json
{
  "persona": {
    "full_name": "Alex Chen",
    "current_job_title": "Senior Scrum Master"
  },
  "voice_profile": {
    "tone": "Direct, confident, avoids buzzwords",
    "sentence_style": "Short sentences, active voice",
    "vocabulary_level": "Technical when relevant, otherwise plain English",
    "personality_markers": "Occasional dry humor",
    "sample_phrases": ["I led...", "I built...", "The result was..."],
    "things_to_avoid": ["Passionate", "Synergy", "Think outside the box", "Leverage"]
  },
  "job_posting": {
    "job_title": "Agile Coach",
    "company_name": "Innovate Corp",
    "culture_text": "Fast-paced environment, data-driven decisions, direct communication valued",
    "extracted_skills": [
      {"skill_name": "SAFe", "importance_level": "Required"},
      {"skill_name": "Agile Coaching", "importance_level": "Required"},
      {"skill_name": "Stakeholder Management", "importance_level": "Preferred"}
    ]
  },
  "selected_stories": [
    {
      "title": "Turned around failing project",
      "context": "Inherited a 6-month delayed project with 40% team turnover",
      "action": "Implemented daily standups, cleared impediments directly with stakeholders",
      "outcome": "Delivered MVP 2 months early, team retention improved to 95%",
      "rationale": "Demonstrates leadership; aligns with company culture"
    },
    {
      "title": "Scaled Agile adoption",
      "context": "Company of 200 engineers using waterfall methodology",
      "action": "Designed SAFe rollout plan, trained 15 Scrum Masters, built metrics dashboard",
      "outcome": "Release cycle reduced from 6 months to 2 weeks",
      "rationale": "Demonstrates SAFe, Agile Coaching; quantified impact"
    }
  ]
}
```

### A.2 Generated Cover Letter

```
Dear Hiring Team,

Innovate Corp's reputation for data-driven decisions caught my attention. That's exactly how I work.

When I inherited a project running 6 months late with 40% turnover, I didn't write a transformation plan. I started daily standups and cleared blockers directly with stakeholders. We shipped the MVP 2 months early. Team retention hit 95%.

At my current company, I took 200 engineers from waterfall to SAFe. I trained 15 Scrum Masters, built a metrics dashboard everyone actually used, and cut our release cycle from 6 months to 2 weeks. The numbers told the story.

I'd welcome the chance to bring this approach to Innovate Corp. Let's talk about how I can help your teams ship faster.

Alex Chen
```

**Word Count:** 127 words (Note: This example is shorter for illustration; actual generation targets 250-350)

### A.3 Agent Reasoning

```
I've prepared materials for **Agile Coach** at **Innovate Corp**:

**Resume Adjustments:**
- Added emphasis on "SAFe" and "scaled Agile" in summary — mentioned 3x in posting
- Reordered TechCorp bullets to lead with SAFe implementation

**Cover Letter Stories:**
- *Turned around failing project* — Demonstrates leadership; aligns with "direct communication" culture
- *Scaled Agile adoption* — Demonstrates SAFe, Agile Coaching; quantified impact

Ready for your review!
```

### A.4 Validation Result

```json
{
  "passed": true,
  "word_count": 127,
  "issues": [
    {
      "severity": "warning",
      "rule": "length_min",
      "message": "Short: 127 words (target 250-350)"
    }
  ]
}
```

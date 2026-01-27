# REQ-008: Scoring Algorithm Specification

**Status:** Draft
**Version:** 0.2
**PRD Reference:** §4.3 Strategist Agent
**Last Updated:** 2026-01-25

---

## 1. Overview

This document specifies the algorithms used by the Strategist agent to score job postings against a user's Persona. The goal is to surface the best-fit opportunities while also identifying stretch roles that align with growth targets.

**Key Principle:** Scoring must be explainable. Users should understand why a job scored high or low, not just see a number.

### 1.1 Score Types

| Score | Range | Purpose |
|-------|-------|---------|
| **Fit Score** | 0-100 | How well the user's current skills/experience match the job requirements |
| **Stretch Score** | 0-100 | How well the job aligns with the user's growth targets |
| **Ghost Score** | 0-100 | Likelihood the job posting is stale/fake (see REQ-003 §7) |

### 1.2 Scoring Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Transparency** | Every score has a breakdown users can inspect |
| **Configurability** | Users can adjust weights (future feature) |
| **Graceful degradation** | Missing data reduces confidence, doesn't break scoring |
| **Bias awareness** | Avoid penalizing non-traditional backgrounds |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Entity definitions | Skills, WorkHistory, NonNegotiables, GrowthTargets |
| REQ-003 Job Posting Schema v0.3 | Entity definitions | ExtractedSkills, requirements, job metadata |
| REQ-005 Database Schema v0.10 | Storage | persona_embeddings, job_embeddings tables |
| REQ-007 Agent Behavior v0.3 | Integration | Strategist agent invocation, prompts |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-007 Agent Behavior | Scoring logic | Strategist uses these algorithms |
| (Future) Frontend | Score display | UI shows breakdown components |

---

## 3. Non-Negotiables Filter (Pre-Scoring)

Before calculating scores, jobs are filtered against hard requirements. Jobs that fail are still stored (for transparency) but marked as failed.

### 3.1 Filter Rules

| Non-Negotiable | Pass Condition | Fail Behavior |
|----------------|----------------|---------------|
| `remote_preference = "Remote Only"` | `job.work_model == "Remote"` | Record in `failed_non_negotiables` |
| `remote_preference = "Hybrid OK"` | `job.work_model IN ("Remote", "Hybrid")` | Record in `failed_non_negotiables` |
| `remote_preference = "Onsite OK"` | Always passes | — |
| `minimum_base_salary` | `job.salary_max >= minimum` OR salary undisclosed | Record if disclosed and below |
| `commutable_cities` | `job.location IN cities` OR `job.work_model == "Remote"` | Record if onsite and not commutable |
| `visa_sponsorship_required` | `job.visa_sponsorship == true` OR unknown | Record if explicitly "No sponsorship" |
| `industry_exclusions` | `job.company_industry NOT IN exclusions` | Record excluded industry |
| `custom_non_negotiables` | Evaluated per custom rule | Record which custom rule failed |

### 3.2 Undisclosed Data Handling

| Field | If Undisclosed |
|-------|----------------|
| Salary | Pass filter (benefit of doubt), but flag `salary_undisclosed = true` |
| Work model | Assume Onsite (conservative) |
| Visa sponsorship | Pass filter, flag as unknown |

### 3.3 Filter Output

```python
class NonNegotiablesResult:
    passed: bool
    failed_reasons: List[str]  # e.g., ["Salary below minimum ($90k < $120k)"]
    warnings: List[str]        # e.g., ["Salary not disclosed"]
```

**Jobs that fail non-negotiables:**
- `fit_score = None` (not calculated)
- `stretch_score = None`
- `failed_non_negotiables = ["reason1", "reason2"]`
- `status = "Discovered"` (still visible if user opts in)

---

## 4. Fit Score Calculation

The Fit Score measures how well the user's current qualifications match the job requirements.

### 4.1 Component Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| Hard Skills Match | 40% | Technical skills alignment |
| Soft Skills Match | 15% | Interpersonal/leadership skills |
| Experience Level | 25% | Years of experience vs. requirements |
| Role Title Match | 10% | Job title similarity to current/past roles |
| Location/Logistics | 10% | Work model preference alignment |

**Total: 100%**

### 4.2 Hard Skills Match (40%)

#### 4.2.1 Calculation Method

```python
def calculate_hard_skills_score(persona_skills: List[Skill], job_skills: List[ExtractedSkill]) -> float:
    """
    Returns 0-100 score for hard skills match.

    IMPORTANT: This function applies proficiency weighting (§4.2.3).
    A "Learning" level skill does NOT count as a full match for a senior role.
    """
    required_skills = [s for s in job_skills if s.is_required and s.skill_type == "Hard"]
    nice_to_have_skills = [s for s in job_skills if not s.is_required and s.skill_type == "Hard"]

    if not required_skills and not nice_to_have_skills:
        return 70.0  # No skills specified = neutral score

    # Build persona skill lookup: {normalized_name: Skill}
    persona_skill_map = {
        normalize(s.skill_name): s
        for s in persona_skills
        if s.skill_type == "Hard"
    }

    # Calculate weighted matches for required skills
    required_weighted_score = 0.0
    for job_skill in required_skills:
        norm_name = normalize(job_skill.skill_name)
        if norm_name in persona_skill_map:
            persona_skill = persona_skill_map[norm_name]
            # Apply proficiency weighting (see §4.2.3)
            weight = get_proficiency_weight(
                persona_proficiency=persona_skill.proficiency_level,
                job_years_requested=job_skill.years_experience  # May be None
            )
            required_weighted_score += weight

    # Calculate weighted matches for nice-to-have skills
    nice_weighted_score = 0.0
    for job_skill in nice_to_have_skills:
        norm_name = normalize(job_skill.skill_name)
        if norm_name in persona_skill_map:
            persona_skill = persona_skill_map[norm_name]
            weight = get_proficiency_weight(
                persona_proficiency=persona_skill.proficiency_level,
                job_years_requested=job_skill.years_experience
            )
            nice_weighted_score += weight

    # Required skills are critical (80% of component)
    if required_skills:
        required_score = (required_weighted_score / len(required_skills)) * 80
    else:
        required_score = 80  # No required = full credit

    # Nice-to-have adds bonus (20% of component)
    if nice_to_have_skills:
        nice_score = (nice_weighted_score / len(nice_to_have_skills)) * 20
    else:
        nice_score = 0

    return required_score + nice_score


def get_proficiency_weight(
    persona_proficiency: str,  # "Learning", "Familiar", "Proficient", "Expert"
    job_years_requested: Optional[int]
) -> float:
    """
    Returns a weight (0.0-1.0) based on how well user's proficiency matches job requirements.

    WHY NOT JUST 0/1:
    A user with "Familiar" Python shouldn't get 0% for a "5+ years Python" role,
    but they also shouldn't get 100%. This graduated weighting reflects reality:
    they HAVE the skill, just not at the required depth.

    Proficiency levels (from REQ-001):
    - "Learning": <1 year, currently acquiring
    - "Familiar": 1-2 years, can use with guidance
    - "Proficient": 2-5 years, independent
    - "Expert": 5+ years, can teach others
    """
    # If job doesn't specify years, any proficiency counts as full match
    if job_years_requested is None:
        return 1.0

    # Map proficiency to approximate years
    PROFICIENCY_YEARS = {
        "Learning": 0.5,
        "Familiar": 1.5,
        "Proficient": 3.5,
        "Expert": 6.0,
    }

    user_years = PROFICIENCY_YEARS.get(persona_proficiency, 2.0)  # Default to mid-range

    if user_years >= job_years_requested:
        return 1.0  # Meets or exceeds requirement

    # Calculate penalty based on gap
    # Each year under = 15% penalty, minimum 0.2 (they still have the skill)
    gap = job_years_requested - user_years
    penalty = gap * 0.15
    return max(0.2, 1.0 - penalty)
```

#### 4.2.2 Skill Normalization

To handle variations in skill naming:

| Raw Skill | Normalized |
|-----------|------------|
| "JavaScript", "JS", "Javascript" | `javascript` |
| "React.js", "ReactJS", "React" | `react` |
| "Amazon Web Services", "AWS" | `aws` |
| "CI/CD", "CICD", "CI-CD" | `ci_cd` |

**Implementation:** Use a skill synonym dictionary + fuzzy matching for unknown skills.

#### 4.2.3 Proficiency Weighting

**This logic is INTEGRATED into §4.2.1 via `get_proficiency_weight()`.**

| Job Requirement | User Proficiency | Weight | Rationale |
|-----------------|------------------|--------|-----------|
| "5+ years Python" | Expert (5+ years) | 1.0 | Meets requirement |
| "5+ years Python" | Proficient (2-5 years) | 0.78 | 1.5 year gap → 22% penalty |
| "5+ years Python" | Familiar (1-2 years) | 0.48 | 3.5 year gap → 52% penalty |
| "5+ years Python" | Learning (<1 year) | 0.33 | 4.5 year gap → capped at 0.2 min + partial |
| "Python" (no years) | Any | 1.0 | No requirement specified |

**Example Scoring:**

Job requires: Python (5+ years, required), SQL (required), Kubernetes (nice-to-have)

User has: Python (Familiar), SQL (Expert), Docker (Expert)

```
Python:     present, Familiar vs 5+ years → weight 0.48
SQL:        present, Expert, no years specified → weight 1.0
Kubernetes: missing → weight 0.0

Required weighted score: 0.48 + 1.0 = 1.48 out of 2 = 74%
Required component: 74% × 80 = 59.2

Nice-to-have: 0 out of 1 = 0%
Nice component: 0% × 20 = 0

Total Hard Skills Score: 59.2
```

Compare to naive "exists/doesn't exist" approach which would give: (2/2) × 80 = 80. The proficiency-aware approach correctly penalizes the Python gap.

### 4.3 Soft Skills Match (15%)

#### 4.3.1 Calculation Method

```python
def calculate_soft_skills_score(persona_skills: List[Skill], job_skills: List[ExtractedSkill]) -> float:
    """
    Returns 0-100 score for soft skills match.
    Uses embedding similarity for semantic matching.
    """
    persona_soft = [s for s in persona_skills if s.skill_type == "Soft"]
    job_soft = [s for s in job_skills if s.skill_type == "Soft"]

    if not job_soft:
        return 70.0  # No soft skills specified = neutral

    # Semantic similarity (embeddings)
    persona_embedding = embed_skills(persona_soft)
    job_embedding = embed_skills(job_soft)

    similarity = cosine_similarity(persona_embedding, job_embedding)

    # Scale from [-1, 1] to [0, 100]
    return (similarity + 1) * 50
```

#### 4.3.2 Common Soft Skills Categories

| Category | Examples |
|----------|----------|
| Communication | Written, verbal, presentation, storytelling |
| Leadership | Team management, mentoring, decision-making |
| Collaboration | Cross-functional, stakeholder management |
| Problem-solving | Analytical thinking, critical thinking, creativity |
| Adaptability | Learning agility, flexibility, resilience |

### 4.4 Experience Level (25%)

#### 4.4.1 Calculation Method

```python
def calculate_experience_score(persona: Persona, job: JobPosting) -> float:
    """
    Returns 0-100 score for experience level match.
    """
    # GUARD: persona.years_experience is Optional in REQ-001
    # New users may not have set this yet; default to 0
    user_years = persona.years_experience or 0

    # Extract job's experience requirement
    job_min_years = job.years_experience_min  # May be None
    job_max_years = job.years_experience_max  # May be None

    if job_min_years is None and job_max_years is None:
        return 70.0  # No requirement specified = neutral

    # Handle ranges
    if job_min_years and job_max_years:
        if job_min_years <= user_years <= job_max_years:
            return 100.0  # Perfect fit
        elif user_years < job_min_years:
            gap = job_min_years - user_years
            return max(0, 100 - (gap * 15))  # -15 points per year under
        else:  # user_years > job_max_years
            gap = user_years - job_max_years
            return max(50, 100 - (gap * 5))  # -5 points per year over (less penalty for overqualified)

    # Handle minimum only
    if job_min_years:
        if user_years >= job_min_years:
            return 100.0
        gap = job_min_years - user_years
        return max(0, 100 - (gap * 15))

    # Handle maximum only (unusual)
    if job_max_years:
        if user_years <= job_max_years:
            return 100.0
        gap = user_years - job_max_years
        return max(50, 100 - (gap * 5))
```

#### 4.4.2 Experience Gap Penalties

| Scenario | Penalty | Rationale |
|----------|---------|-----------|
| Under-qualified by 1 year | -15 points | Significant gap |
| Under-qualified by 3 years | -45 points | Major gap |
| Over-qualified by 2 years | -10 points | Slight concern |
| Over-qualified by 5+ years | -25 points (max) | May be seen as "slumming" |

### 4.5 Role Title Match (10%)

#### 4.5.1 Calculation Method

```python
def calculate_role_match_score(persona: Persona, job: JobPosting) -> float:
    """
    Returns 0-100 score for role title similarity.
    """
    user_titles = [persona.current_role] + [wh.job_title for wh in persona.work_history]
    job_title = job.job_title

    # Exact match
    if any(normalize_title(t) == normalize_title(job_title) for t in user_titles):
        return 100.0

    # Semantic similarity
    user_titles_embedding = embed_titles(user_titles)
    job_title_embedding = embed_title(job_title)

    similarity = cosine_similarity(user_titles_embedding, job_title_embedding)

    # Scale to 0-100
    return max(0, (similarity + 1) * 50)
```

#### 4.5.2 Title Normalization

| Variations | Normalized |
|------------|------------|
| "Sr.", "Senior", "Lead" | `senior` |
| "Jr.", "Junior", "Associate" | `junior` |
| "Software Engineer", "Software Developer", "SDE" | `software_engineer` |
| "Product Manager", "PM" | `product_manager` |

### 4.6 Location/Logistics (10%)

#### 4.6.1 Calculation Method

```python
def calculate_logistics_score(persona: Persona, job: JobPosting) -> float:
    """
    Returns 0-100 score for location/work model alignment.
    """
    score = 100.0

    # Work model preference
    if persona.remote_preference == "Remote Only":
        if job.work_model == "Remote":
            score = 100.0
        elif job.work_model == "Hybrid":
            score = 50.0  # Partial match
        else:
            score = 0.0  # Should have been filtered, but just in case

    elif persona.remote_preference == "Hybrid OK":
        if job.work_model in ("Remote", "Hybrid"):
            score = 100.0
        else:
            score = 60.0  # Onsite not ideal but acceptable

    else:  # Onsite OK
        score = 100.0  # Any work model is fine

    # Location proximity (for non-remote)
    if job.work_model != "Remote" and persona.commutable_cities:
        if job.location in persona.commutable_cities:
            pass  # Full score
        else:
            score *= 0.7  # 30% penalty for non-commutable location

    return score
```

### 4.7 Fit Score Aggregation

```python
def calculate_fit_score(persona: Persona, job: JobPosting) -> FitScoreResult:
    """
    Aggregate all components into final Fit Score.
    """
    components = {
        "hard_skills": calculate_hard_skills_score(persona.skills, job.extracted_skills),
        "soft_skills": calculate_soft_skills_score(persona.skills, job.extracted_skills),
        "experience": calculate_experience_score(persona, job),
        "role_match": calculate_role_match_score(persona, job),
        "logistics": calculate_logistics_score(persona, job)
    }

    weights = {
        "hard_skills": 0.40,
        "soft_skills": 0.15,
        "experience": 0.25,
        "role_match": 0.10,
        "logistics": 0.10
    }

    total_score = sum(components[k] * weights[k] for k in components)

    return FitScoreResult(
        total=round(total_score),
        components=components,
        weights=weights
    )
```

---

## 5. Stretch Score Calculation

The Stretch Score measures how well the job aligns with the user's growth targets.

### 5.1 Component Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| Target Role Alignment | 50% | How closely job title matches target roles |
| Target Skills Exposure | 40% | How many target skills appear in job requirements |
| Growth Trajectory | 10% | Is this a step up from current role? |

**Total: 100%**

### 5.2 Target Role Alignment (50%)

```python
def calculate_target_role_alignment(persona: Persona, job: JobPosting) -> float:
    """
    Returns 0-100 score for target role alignment.
    """
    if not persona.growth_targets or not persona.growth_targets.target_roles:
        return 50.0  # No targets defined = neutral

    target_roles = persona.growth_targets.target_roles
    job_title = job.job_title

    # Exact match
    if any(normalize_title(t) == normalize_title(job_title) for t in target_roles):
        return 100.0

    # Semantic similarity
    targets_embedding = embed_titles(target_roles)
    job_embedding = embed_title(job_title)

    similarity = cosine_similarity(targets_embedding, job_embedding)

    # Scale to 0-100, with higher baseline (growth roles should be somewhat related)
    return max(0, 30 + (similarity + 1) * 35)
```

### 5.3 Target Skills Exposure (40%)

```python
def calculate_target_skills_exposure(persona: Persona, job: JobPosting) -> float:
    """
    Returns 0-100 score for target skills present in job.
    """
    if not persona.growth_targets or not persona.growth_targets.target_skills:
        return 50.0  # No targets defined = neutral

    target_skills = {normalize(s) for s in persona.growth_targets.target_skills}
    job_skills = {normalize(s.skill_name) for s in job.extracted_skills}

    if not target_skills:
        return 50.0

    matches = len(target_skills & job_skills)

    # Scale: 1 match = 50, 2 = 75, 3+ = 100
    if matches == 0:
        return 20.0  # No target skills = low stretch value
    elif matches == 1:
        return 50.0
    elif matches == 2:
        return 75.0
    else:
        return 100.0
```

### 5.4 Growth Trajectory (10%)

```python
def calculate_growth_trajectory(persona: Persona, job: JobPosting) -> float:
    """
    Returns 0-100 score for whether this job represents career growth.
    """
    current_level = infer_level(persona.current_role)  # junior, mid, senior, lead, director, vp, c-level
    job_level = infer_level(job.job_title)

    level_order = ["junior", "mid", "senior", "lead", "director", "vp", "c_level"]

    try:
        current_idx = level_order.index(current_level)
        job_idx = level_order.index(job_level)
    except ValueError:
        return 50.0  # Can't determine levels

    if job_idx > current_idx:
        return 100.0  # Step up
    elif job_idx == current_idx:
        return 70.0   # Lateral move
    else:
        return 30.0   # Step down
```

### 5.5 Stretch Score Aggregation

```python
def calculate_stretch_score(persona: Persona, job: JobPosting) -> StretchScoreResult:
    """
    Aggregate all components into final Stretch Score.
    """
    components = {
        "target_role": calculate_target_role_alignment(persona, job),
        "target_skills": calculate_target_skills_exposure(persona, job),
        "growth_trajectory": calculate_growth_trajectory(persona, job)
    }

    weights = {
        "target_role": 0.50,
        "target_skills": 0.40,
        "growth_trajectory": 0.10
    }

    total_score = sum(components[k] * weights[k] for k in components)

    return StretchScoreResult(
        total=round(total_score),
        components=components,
        weights=weights
    )
```

---

## 6. Embedding Strategy

### 6.1 What Gets Embedded

| Entity | Embedding Type | Content | Source |
|--------|----------------|---------|--------|
| Persona Hard Skills | `persona_hard_skills` | Concatenated skill names + proficiency | Structured `Skill` records |
| Persona Soft Skills | `persona_soft_skills` | Concatenated skill names | Structured `Skill` records |
| Persona Logistics | `persona_logistics` | Location prefs, work model, values | Structured `NonNegotiables` |
| Job Requirements | `job_requirements` | Required + preferred skills, experience | Structured `ExtractedSkill` records |
| Job Culture | `job_culture` | Company values, team description, benefits | **LLM-extracted from description** |

**CRITICAL: Job Culture Extraction**

The `job_culture` embedding does NOT come from a structured field. The Scouter extracts `ExtractedSkills` (structured) but culture information is buried in the raw `description` text.

**Why this matters:**
- If we embed the entire `description`, technical keywords pollute the culture vector
- A job with "Python, AWS, Kubernetes" in the description would match a user with "Python" as a soft skill similarity — incorrect
- We must SEPARATE culture/values text from requirements text

**Solution:** The Scouter must extract `culture_text` during skill extraction (see REQ-007 §6.4). This is an LLM task:

```
From the job description, extract ONLY the text about:
- Company culture and values
- Team description and work environment
- Benefits and perks
- "About Us" content

Do NOT include:
- Technical requirements
- Skills lists
- Experience requirements
- Responsibilities

Return the extracted culture text, or empty string if none found.
```

### 6.2 Embedding Model

| Option | Dimensions | Cost | Quality | Recommendation |
|--------|------------|------|---------|----------------|
| OpenAI text-embedding-3-small | 1536 | Low | Good | **MVP choice** |
| OpenAI text-embedding-3-large | 3072 | Medium | Better | Future upgrade |
| Cohere embed-english-v3.0 | 1024 | Low | Good | Alternative |
| Local (sentence-transformers) | 384-768 | Free | Varies | Self-hosted option |

**MVP Recommendation:** `text-embedding-3-small` — good balance of cost and quality.

### 6.3 Embedding Generation

```python
async def generate_persona_embeddings(persona: Persona) -> PersonaEmbeddings:
    """
    Generate all embeddings for a Persona.
    Called on: Persona creation, Persona update (see REQ-007 §7.1).
    """
    # Hard skills text
    hard_skills_text = " | ".join([
        f"{s.skill_name} ({s.proficiency_level})"
        for s in persona.skills if s.skill_type == "Hard"
    ])

    # Soft skills text
    soft_skills_text = " | ".join([
        s.skill_name for s in persona.skills if s.skill_type == "Soft"
    ])

    # Logistics text
    logistics_text = f"""
    Remote preference: {persona.non_negotiables.remote_preference}
    Location: {persona.location}
    Commutable cities: {', '.join(persona.non_negotiables.commutable_cities or [])}
    Industry exclusions: {', '.join(persona.non_negotiables.industry_exclusions or [])}
    """

    # Generate embeddings
    hard_embedding = await embed(hard_skills_text)
    soft_embedding = await embed(soft_skills_text)
    logistics_embedding = await embed(logistics_text)

    return PersonaEmbeddings(
        persona_id=persona.id,
        hard_skills=hard_embedding,
        soft_skills=soft_embedding,
        logistics=logistics_embedding,
        version=persona.updated_at  # For staleness detection
    )
```

### 6.4 Job Embedding Generation

```python
async def generate_job_embeddings(job: JobPosting) -> JobEmbeddings:
    """
    Generate embeddings for a JobPosting.
    Called by: Strategist during scoring (see REQ-007 §7).

    IMPORTANT: job.culture_text must be populated by the Scouter (REQ-007 §6.4).
    If culture_text is empty/None, we fall back to a neutral embedding.
    """
    # Requirements text from structured ExtractedSkills
    requirements_text = " | ".join([
        f"{s.skill_name} ({s.years_experience}+ years)" if s.years_experience else s.skill_name
        for s in job.extracted_skills
        if s.is_required
    ])

    preferred_text = " | ".join([
        s.skill_name for s in job.extracted_skills if not s.is_required
    ])

    full_requirements = f"""
    Required: {requirements_text}
    Preferred: {preferred_text}
    Experience: {job.years_experience_min or 'Not specified'}-{job.years_experience_max or 'Not specified'} years
    """

    # Culture text - MUST come from LLM extraction, not raw description
    # See §6.1 for why this separation is critical
    culture_text = job.culture_text or ""

    if not culture_text:
        # Fallback: Use empty string which produces a neutral embedding
        # This is INTENTIONAL - we don't want to pollute culture matching
        # with technical requirements from the description
        logger.warning(f"Job {job.id} has no culture_text - culture matching will be neutral")

    # Generate embeddings
    requirements_embedding = await embed(full_requirements)
    culture_embedding = await embed(culture_text) if culture_text else get_neutral_embedding()

    return JobEmbeddings(
        job_posting_id=job.id,
        requirements=requirements_embedding,
        culture=culture_embedding,
    )


def get_neutral_embedding() -> List[float]:
    """
    Returns a zero vector for jobs without culture text.

    WHY ZERO VECTOR:
    - Cosine similarity with any vector = 0 (orthogonal)
    - This gives a neutral soft skills score (50), not a penalty
    - Better than embedding random text or the full description
    """
    return [0.0] * 1536  # Match embedding dimensions
```

### 6.5 Embedding Storage

```sql
CREATE TABLE persona_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    embedding_type TEXT NOT NULL,  -- 'hard_skills', 'soft_skills', 'logistics'
    embedding vector(1536) NOT NULL,
    version TIMESTAMPTZ NOT NULL,  -- Matches persona.updated_at
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(persona_id, embedding_type)
);

CREATE INDEX idx_persona_embeddings_persona ON persona_embeddings(persona_id);
```

### 6.6 Embedding Freshness Check

```python
def is_embedding_fresh(persona: Persona, embeddings: PersonaEmbeddings) -> bool:
    """
    Check if embeddings are up-to-date with Persona.
    """
    return embeddings.version == persona.updated_at
```

If stale, regenerate before scoring (see REQ-007 §10.4.1).

---

## 7. Score Interpretation

### 7.1 Fit Score Thresholds

| Range | Label | Interpretation |
|-------|-------|----------------|
| 90-100 | **Excellent** | Strong match, high confidence |
| 75-89 | **Good** | Solid match, minor gaps |
| 60-74 | **Fair** | Partial match, notable gaps |
| 40-59 | **Stretch** | Significant gaps, but possible |
| 0-39 | **Poor** | Not a good fit |

### 7.2 Stretch Score Thresholds

| Range | Label | Interpretation |
|-------|-------|----------------|
| 80-100 | **High Growth** | Strong alignment with career goals |
| 60-79 | **Moderate Growth** | Some goal alignment |
| 40-59 | **Lateral** | Similar to current role |
| 0-39 | **Low Growth** | Not aligned with stated goals |

### 7.3 Combined Interpretation

| Fit Score | Stretch Score | Recommendation |
|-----------|---------------|----------------|
| High (75+) | High (80+) | 🎯 **Top Priority** — Apply immediately |
| High (75+) | Low (<60) | ✅ **Safe Bet** — Good fit, but not growth |
| Low (<60) | High (80+) | 🌱 **Stretch Opportunity** — Worth the reach |
| Low (<60) | Low (<60) | ⚠️ **Likely Skip** — Neither fit nor growth |

### 7.4 Auto-Draft Threshold

Default: `auto_draft_threshold = 90`

Jobs with `fit_score >= auto_draft_threshold` trigger automatic Ghostwriter drafting (see REQ-007 §8.1).

---

## 8. Score Explanation Generation

The Strategist generates human-readable explanations (see REQ-007 §7.6).

### 8.1 Explanation Components

```python
class ScoreExplanation:
    summary: str              # 2-3 sentence overview
    strengths: List[str]      # What matches well
    gaps: List[str]           # What's missing
    stretch_opportunities: List[str]  # Growth potential
    warnings: List[str]       # Concerns (salary undisclosed, ghost score, etc.)
```

### 8.2 Explanation Generation Logic

```python
def generate_explanation(
    fit_result: FitScoreResult,
    stretch_result: StretchScoreResult,
    persona: Persona,
    job: JobPosting
) -> ScoreExplanation:

    strengths = []
    gaps = []
    stretch_opportunities = []
    warnings = []

    # Hard skills analysis
    if fit_result.components["hard_skills"] >= 80:
        matched = get_matched_skills(persona, job, "Hard")
        strengths.append(f"Strong technical fit — you have {len(matched)} of the key skills: {', '.join(matched[:3])}")
    elif fit_result.components["hard_skills"] < 50:
        missing = get_missing_skills(persona, job, "Hard", required_only=True)
        gaps.append(f"Missing required skills: {', '.join(missing[:3])}")

    # Experience analysis
    if fit_result.components["experience"] >= 90:
        strengths.append(f"Experience level is a perfect match ({persona.years_experience} years)")
    elif fit_result.components["experience"] < 60:
        if persona.years_experience < job.years_experience_min:
            gaps.append(f"Under-qualified: job wants {job.years_experience_min}+ years, you have {persona.years_experience}")
        else:
            warnings.append(f"May be seen as overqualified ({persona.years_experience} years vs. {job.years_experience_max} max)")

    # Stretch analysis
    if stretch_result.components["target_skills"] >= 75:
        target_matches = get_target_skill_matches(persona, job)
        stretch_opportunities.append(f"Exposure to target skills: {', '.join(target_matches)}")

    if stretch_result.components["target_role"] >= 80:
        stretch_opportunities.append(f"Aligns with your target role of {persona.growth_targets.target_roles[0]}")

    # Warnings
    if job.salary_max is None:
        warnings.append("Salary not disclosed")
    if job.ghost_score and job.ghost_score >= 60:
        warnings.append(f"Ghost risk: {job.ghost_score}% — this posting may be stale")

    # Generate summary
    summary = generate_summary_sentence(fit_result.total, stretch_result.total, strengths, gaps)

    return ScoreExplanation(
        summary=summary,
        strengths=strengths,
        gaps=gaps,
        stretch_opportunities=stretch_opportunities,
        warnings=warnings
    )
```

---

## 9. Edge Cases & Special Handling

### 9.1 Missing Data

| Scenario | Handling |
|----------|----------|
| Job has no skills extracted | Return `fit_score = 50` (neutral), flag for manual review |
| Persona has no skills | Block scoring, prompt user to complete onboarding |
| Job experience not specified | Use neutral score (70) for experience component |
| No salary range | Pass non-negotiables, add warning |

### 9.2 Career Changers

Users transitioning between fields may have low hard skills match but high transferable skills.

**Enhancement (Future):** Add `career_change_mode` that:
- Weights soft skills higher (25% instead of 15%)
- Considers adjacent skill mapping (e.g., "Data Analysis" → "Product Analytics")
- Boosts stretch score for roles in target industry

### 9.3 Entry-Level Users

Users with <2 years experience may score poorly on experience-heavy roles.

**Handling:**
- If `persona.years_experience < 2` and job is entry-level, boost experience score
- Flag roles explicitly marked "Entry Level" or "New Grad"

### 9.4 Executive Roles

VP+ roles often have vague skill requirements and emphasize leadership.

**Handling:**
- Detect executive titles (VP, Director, C-suite)
- Shift weights: Soft skills 30%, Hard skills 25%, Experience 25%

---

## 10. Performance Considerations

### 10.1 Batch Scoring

When Scouter discovers many jobs at once, score in batches:

```python
async def batch_score_jobs(jobs: List[JobPosting], persona: Persona) -> List[ScoredJob]:
    """
    Score multiple jobs efficiently.
    """
    # Load persona embeddings once
    persona_embeddings = await get_persona_embeddings(persona.id)

    # Generate job embeddings in batch
    job_texts = [job_to_embedding_text(j) for j in jobs]
    job_embeddings = await batch_embed(job_texts)

    # Score each job
    results = []
    for job, job_emb in zip(jobs, job_embeddings):
        fit = calculate_fit_score(persona, job, persona_embeddings, job_emb)
        stretch = calculate_stretch_score(persona, job)
        results.append(ScoredJob(job=job, fit=fit, stretch=stretch))

    return results
```

### 10.2 Caching

| What to Cache | TTL | Invalidation |
|---------------|-----|--------------|
| Persona embeddings | Until persona update | On any persona change |
| Skill synonym dictionary | 24 hours | Manual refresh |
| Title normalization | 24 hours | Manual refresh |

### 10.3 Embedding Costs

| Volume | Estimated Monthly Cost (OpenAI) |
|--------|--------------------------------|
| 100 jobs/day | ~$3 |
| 500 jobs/day | ~$15 |
| 2000 jobs/day | ~$60 |

(Based on text-embedding-3-small at $0.00002/1K tokens)

---

## 11. Testing & Validation

### 11.1 Test Cases

| Scenario | Expected Fit | Expected Stretch |
|----------|--------------|------------------|
| Perfect match (all skills, right experience) | 95+ | Varies |
| Missing 1 required skill | 70-80 | Varies |
| Missing 3+ required skills | <50 | Varies |
| 2 years under experience requirement | 60-70 | Varies |
| Job matches target role exactly | Varies | 90+ |
| Job has 2 target skills | Varies | 70-80 |

### 11.2 Validation Approach

1. **Golden set:** Curate 50 Persona/Job pairs with human-labeled scores
2. **Correlation check:** Verify algorithm scores correlate with human labels (r > 0.8)
3. **A/B testing:** Track user behavior (apply rate, dismiss rate) vs. scores

---

## 12. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Should users be able to customize weights? | Deferred | Add in v2 if requested |
| 2 | How to handle skills not in synonym dictionary? | TBD | Fuzzy match + LLM fallback? |
| 3 | Career changer mode implementation? | Deferred | Separate feature |

---

## 13. Design Decisions & Rationale

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Scoring approach | Pure ML / Rule-based / Hybrid | Hybrid (rules + embeddings) | Interpretable, tunable, cost-effective |
| Hard skills weight | 30% / 40% / 50% | 40% | Technical skills are primary filter for most roles |
| Experience penalty | Linear / Exponential / Step | Linear | Simple, predictable, easy to explain |
| Embedding model | OpenAI / Cohere / Local | OpenAI text-embedding-3-small | Best balance of cost, quality, API simplicity |

---

## 14. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-25 | 0.1 | Initial draft. Non-negotiables filter, Fit Score calculation (5 components), Stretch Score calculation (3 components), embedding strategy, score interpretation. |
| 2026-01-25 | 0.2 | **Bug fixes from review:** (1) Integrated proficiency weighting into §4.2.1 — "Learning" level skills no longer count as full matches for senior roles. (2) Clarified job culture embedding requires LLM extraction from description (§6.1, §6.4) — prevents polluting soft skills matching with technical keywords. (3) Added null guard for `persona.years_experience` in §4.4.1 — prevents crash for new users. |

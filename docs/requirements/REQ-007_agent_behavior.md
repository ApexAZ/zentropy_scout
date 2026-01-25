# REQ-007: Agent Behavior Specification

**Status:** Draft  
**PRD Reference:** §4 Core Agentic Capabilities  
**Last Updated:** 2026-01-25

---

## 1. Overview

This document specifies the behavior of Zentropy Scout's AI agents: how they're triggered, what tools they use, how they interact with the API, and how they coordinate with users via Human-in-the-Loop (HITL) patterns.

**Key Principle:** Agents are internal API clients. They interpret user intent, select appropriate tools, and call the same REST endpoints as the frontend. All writes go through the API — agents don't bypass validation or tenant isolation.

### 1.1 Agent Roster

| Agent | Role | Trigger | PRD Reference |
|-------|------|---------|---------------|
| **Chat Agent** | User interaction hub | User message | §7.2 |
| **Onboarding Agent** | Persona building | New user / incomplete onboarding | §4.1 |
| **Scouter** | Job discovery | Scheduled polling / manual refresh | §4.2 |
| **Strategist** | Match analysis | Job discovered | §4.3 |
| **Ghostwriter** | Content generation | High-match job (auto) or user request | §4.4 |

### 1.2 Architecture Context

```
┌─────────────────────────────────────────────────────────────┐
│                      Chat Agent (LangGraph)                  │
│  • Receives user messages via /chat/messages                 │
│  • Interprets intent, selects tools                          │
│  • Streams responses via SSE /chat/stream                    │
│  • Can invoke other agents as sub-graphs                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Onboarding  │ │    Scouter    │ │  Ghostwriter  │
│     Agent     │ │               │ │               │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        │                 ▼                 │
        │         ┌───────────────┐         │
        │         │   Strategist  │         │
        │         │  (scoring)    │         │
        │         └───────┬───────┘         │
        │                 │                 │
        └────────────┬────┴────┬────────────┘
                     ▼         ▼
              ┌─────────────────────┐
              │        API          │
              │  (REQ-006 endpoints)│
              └─────────────────────┘
```

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Entity definitions | Persona fields, onboarding steps, voice profile |
| REQ-002 Resume Schema v0.7 | Entity definitions | BaseResume, JobVariant, PersonaChangeFlag |
| REQ-002b Cover Letter Schema v0.5 | Entity definitions | CoverLetter, achievement story selection |
| REQ-003 Job Posting Schema v0.3 | Entity definitions | Ghost detection, matching, non-negotiables |
| REQ-004 Application Schema v0.5 | Entity definitions | Status lifecycle, timeline events |
| REQ-006 API Contract v0.6 | Endpoint contracts | All tools map to API endpoints |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| (Future) Implementation | Agent specifications | LangGraph graph definitions, prompts |

---

## 3. LangGraph Framework

### 3.1 Why LangGraph

| Requirement | How LangGraph Addresses It |
|-------------|---------------------------|
| HITL checkpointing | Built-in state persistence; can pause and resume |
| Tool calling | Native tool/function binding |
| Streaming | Supports token-by-token streaming for chat |
| Sub-graphs | Agents can invoke other agents as nodes |
| State management | Typed state schemas, automatic serialization |

### 3.2 State Schema

All agents share a common state schema with agent-specific extensions.

```python
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph

class BaseAgentState(TypedDict):
    # User context
    user_id: str
    persona_id: str
    
    # Conversation
    messages: List[dict]  # Chat history
    current_message: Optional[str]
    
    # Tool execution
    tool_calls: List[dict]
    tool_results: List[dict]
    
    # Control flow
    next_action: Optional[str]
    requires_human_input: bool
    checkpoint_reason: Optional[str]
```

### 3.3 Checkpointing & HITL

**Checkpoint Triggers:**

| Trigger | Behavior |
|---------|----------|
| Approval needed | Pause, notify user, wait for response |
| Clarification needed | Pause, ask question, wait for answer |
| Long-running task | Checkpoint periodically, allow resume |
| Error/uncertainty | Pause, explain situation, ask for guidance |

**Checkpoint Storage:**
- MVP: Redis (same instance as task queue)
- State serialized as JSON
- TTL: 24 hours for incomplete flows, 7 days for conversation history

---

## 4. Chat Agent

The Chat Agent is the primary user interface. It interprets natural language, selects tools, and coordinates with specialized agents.

### 4.1 Responsibilities

| Responsibility | Description |
|----------------|-------------|
| Intent recognition | Understand what user wants to do |
| Tool selection | Pick appropriate tool(s) for the task |
| Context management | Maintain conversation history |
| Response streaming | Stream LLM output via SSE |
| Agent delegation | Invoke Onboarding/Ghostwriter when needed |
| Clarification | Ask follow-up questions when intent is ambiguous |

### 4.2 Tool Categories

Tools are thin wrappers around API endpoints (REQ-006).

#### 4.2.1 Job Management Tools

| Tool | API Endpoint | Description |
|------|--------------|-------------|
| `list_jobs` | `GET /job-postings` | List discovered jobs with filters |
| `get_job` | `GET /job-postings/{id}` | Get job details |
| `favorite_job` | `PATCH /job-postings/{id}` | Toggle favorite flag |
| `dismiss_job` | `PATCH /job-postings/{id}` | Set status to Dismissed |
| `bulk_dismiss_jobs` | `POST /job-postings/bulk-dismiss` | Dismiss multiple jobs |
| `bulk_favorite_jobs` | `POST /job-postings/bulk-favorite` | Favorite/unfavorite multiple |
| `refresh_jobs` | `POST /refresh` | Trigger Scouter to poll sources |

#### 4.2.2 Application Tools

| Tool | API Endpoint | Description |
|------|--------------|-------------|
| `list_applications` | `GET /applications` | List applications with filters |
| `get_application` | `GET /applications/{id}` | Get application details |
| `mark_applied` | `POST /applications` | Create application record |
| `update_status` | `PATCH /applications/{id}` | Update application status |
| `add_timeline_event` | `POST /applications/{id}/timeline` | Add event to timeline |
| `add_note` | `PATCH /applications/{id}` | Update notes field |

#### 4.2.3 Resume/Cover Letter Tools

| Tool | API Endpoint | Description |
|------|--------------|-------------|
| `list_base_resumes` | `GET /base-resumes` | List user's base resumes |
| `get_job_variant` | `GET /job-variants/{id}` | Get variant details |
| `approve_variant` | `PATCH /job-variants/{id}` | Approve draft variant |
| `get_cover_letter` | `GET /cover-letters/{id}` | Get cover letter |
| `approve_cover_letter` | `PATCH /cover-letters/{id}` | Approve draft |
| `regenerate_cover_letter` | `POST /cover-letters/{id}/regenerate` | Request new draft |

#### 4.2.4 Persona Tools

| Tool | API Endpoint | Description |
|------|--------------|-------------|
| `get_persona` | `GET /personas/{id}` | Get persona details |
| `update_persona` | `PATCH /personas/{id}` | Update persona fields |
| `add_skill` | `POST /personas/{id}/skills` | Add new skill |
| `add_work_history` | `POST /personas/{id}/work-history` | Add job entry |
| `get_change_flags` | `GET /persona-change-flags` | Get pending sync flags |
| `resolve_change_flag` | `PATCH /persona-change-flags/{id}` | Resolve a flag |

#### 4.2.5 Search/Query Tools

| Tool | API Endpoint | Description |
|------|--------------|-------------|
| `find_jobs_by_company` | `GET /job-postings?company_name=X` | Filter jobs by company |
| `find_high_match_jobs` | `GET /job-postings?fit_score_min=X&sort=-fit_score` | Find best matches |
| `find_pending_applications` | `GET /applications?status=Applied,Interviewing` | Active applications |
| `find_pending_reviews` | `GET /job-variants?status=Approved` + filter | Materials ready for submission |

#### 4.2.6 Agent Invocation Tools

| Tool | Description |
|------|-------------|
| `invoke_onboarding` | Start/resume onboarding flow |
| `invoke_ghostwriter` | Generate materials for a job |
| `invoke_scouter` | Trigger immediate job search |

### 4.3 Intent Recognition Patterns

| User Says | Recognized Intent | Tools Selected |
|-----------|-------------------|----------------|
| "Show me new jobs" | list_discovered_jobs | `list_jobs(status=Discovered, sort=-fit_score)` |
| "Favorite the Acme one" | favorite_job | `favorite_job(id=<resolved>)` |
| "What's my fit for job 123?" | get_job_analysis | `get_job(id=123)` → explain scores |
| "Draft materials for this job" | generate_materials | `invoke_ghostwriter(job_id=...)` |
| "I applied to Acme" | mark_applied | `mark_applied(...)` or clarify which job |
| "Update my skills" | update_persona | `invoke_onboarding` or direct edit |
| "How's my job search going?" | summarize_status | `list_applications` + `list_jobs` → summarize |

### 4.4 Ambiguity Resolution

When intent is unclear, agent asks clarifying questions:

**Ambiguous reference:**
```
User: "Dismiss that one"
Agent: "Which job would you like to dismiss? I see 3 you were recently looking at:
        1. Scrum Master at Acme Corp
        2. Product Owner at TechCo
        3. Agile Coach at StartupX"
```

**Missing information:**
```
User: "I got an interview"
Agent: "Great! Which application is this for? And when is the interview scheduled?"
```

**Confirmation for destructive actions:**
```
User: "Dismiss all jobs below 70%"
Agent: "This will dismiss 15 jobs. Want me to proceed, or would you like to review them first?"
```

### 4.5 Response Formatting

| Context | Format |
|---------|--------|
| Single job details | Structured card with key fields |
| Job list | Compact list with score, company, title |
| Status update confirmation | Brief confirmation + next steps |
| Error | Explanation + suggested action |
| Complex analysis | Prose with key points highlighted |

---

## 5. Onboarding Agent

Guides new users through persona creation via structured interview.

### 5.1 Trigger Conditions

| Condition | Trigger |
|-----------|---------|
| New user (no persona) | Auto-start on first login |
| `onboarding_complete = false` | Resume from `onboarding_step` |
| User request | "Update my profile" → partial re-interview |

### 5.2 Interview Flow (State Machine)

```
┌─────────────────┐
│  resume_upload  │ ← Optional, can skip
└────────┬────────┘
         ▼
┌─────────────────┐
│   basic_info    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  work_history   │ ← Confirm/expand extracted jobs
└────────┬────────┘
         ▼
┌─────────────────┐
│   education     │ ← Optional section
└────────┬────────┘
         ▼
┌─────────────────┐
│     skills      │ ← Rate proficiency, add missing
└────────┬────────┘
         ▼
┌─────────────────┐
│ certifications  │ ← Optional section
└────────┬────────┘
         ▼
┌─────────────────┐
│achievement_stories│ ← Guided conversation, 3-5 stories
└────────┬────────┘
         ▼
┌─────────────────┐
│ non_negotiables │ ← Location, salary, filters
└────────┬────────┘
         ▼
┌─────────────────┐
│ growth_targets  │ ← Target roles, skills, stretch
└────────┬────────┘
         ▼
┌─────────────────┐
│ voice_profile   │ ← Derive from conversation + samples
└────────┬────────┘
         ▼
┌─────────────────┐
│     review      │ ← User reviews, makes edits
└────────┬────────┘
         ▼
┌─────────────────┐
│ base_resume_setup│ ← Create first BaseResume(s)
└────────┬────────┘
         ▼
    [Complete]
```

### 5.3 Step Behaviors

#### 5.3.1 resume_upload

| Behavior | Description |
|----------|-------------|
| Prompt | "Do you have an existing resume to upload? (PDF or DOCX)" |
| If uploaded | Extract data, populate persona fields |
| If skipped | Proceed to basic_info, gather all data via interview |
| API calls | `POST /resume-files`, then extraction service |

#### 5.3.2 basic_info

| Field | Gathering Approach |
|-------|-------------------|
| full_name | "What's your full name as you'd like it on applications?" |
| email | "What's the best email for job applications?" |
| phone | "And your phone number?" |
| location | "Where are you located? (City, State/Country)" |
| linkedin_url | "Do you have a LinkedIn profile I should link?" |
| portfolio_url | "Any portfolio or personal website?" |

**Validation:** Email format, phone format (flexible).

#### 5.3.3 work_history

| Behavior | Description |
|----------|-------------|
| If resume extracted | Present extracted jobs, ask to confirm/edit |
| For each job | Confirm title, dates, company; expand bullets |
| Bullet expansion | "Tell me more about your accomplishments here" |
| Minimum | At least 1 job with 1 bullet |

**Probing questions:**
- "What was your biggest accomplishment in this role?"
- "Can you quantify any of these results?"
- "What skills did you develop or demonstrate?"

#### 5.3.4 skills

| Behavior | Description |
|----------|-------------|
| If resume extracted | Present extracted skills, ask proficiency |
| Proficiency scale | Learning / Familiar / Proficient / Expert |
| For each skill | "How would you rate your [skill] proficiency?" |
| Missing skills | "Any other technical or soft skills to add?" |
| Categorization | Agent suggests category, user confirms |

#### 5.3.5 achievement_stories

| Behavior | Description |
|----------|-------------|
| Goal | Capture 3-5 structured stories |
| Prompt | "Tell me about a time you [achieved something significant]" |
| Structure | Extract Context → Action → Outcome |
| Follow-ups | "What was the result?" "Can you quantify that?" |
| Skill linking | "Which skills did this demonstrate?" |

**Story prompts:**
- "Tell me about a challenging project you turned around"
- "Describe a time you led a team through a difficult situation"
- "What's an accomplishment you're most proud of?"

#### 5.3.6 non_negotiables

| Field | Gathering Approach |
|-------|-------------------|
| remote_preference | "Are you looking for remote, hybrid, or onsite roles?" |
| commutable_cities | If not remote-only: "Which cities can you commute to?" |
| minimum_base_salary | "What's your minimum acceptable base salary?" |
| visa_sponsorship | "Do you require visa sponsorship?" |
| industry_exclusions | "Any industries you want to avoid?" |
| custom filters | "Any other dealbreakers I should know about?" |

#### 5.3.7 voice_profile

| Behavior | Description |
|----------|-------------|
| Derivation | Analyze conversation for tone, style, vocabulary |
| Optional sample | "Can you share a writing sample? (email, doc, etc.)" |
| Presentation | "Based on our conversation, here's how I'd describe your voice..." |
| Confirmation | User reviews and edits |

**Derived traits:**
- Tone: Direct? Warm? Formal?
- Sentence style: Short and punchy? Elaborate?
- Vocabulary: Technical? Plain English?
- Things to avoid: Buzzwords they never use

#### 5.3.8 base_resume_setup

| Behavior | Description |
|----------|-------------|
| Prompt | "What type of role are you primarily targeting?" |
| First resume | Create BaseResume for primary role type |
| Additional | "Any other role types you're considering?" |
| Selection | Agent suggests which jobs/bullets/skills to include |
| Rendering | Generate and store anchor PDF |
| Primary | Mark first as `is_primary = true` |

### 5.4 Checkpoint Handling

| Scenario | Behavior |
|----------|----------|
| User exits mid-flow | Save `onboarding_step`, checkpoint state |
| User returns | "Welcome back! We were working on [step]. Ready to continue?" |
| User wants to skip | Allow skipping optional sections (education, certifications) |
| User wants to restart | "Start fresh or continue where we left off?" |

### 5.5 Post-Onboarding Updates

User can update persona anytime via chat:
- "I got a new certification" → Add certification
- "Update my skills" → Re-run skills section
- "I changed my salary requirement" → Update non-negotiables

Agent uses same interview patterns but for single sections.

---

## 6. Scouter Agent

Discovers job postings from configured sources.

### 6.1 Trigger Conditions

| Trigger | Source |
|---------|--------|
| Scheduled poll | Based on `Persona.polling_frequency` |
| Manual refresh | User clicks refresh or says "Find new jobs" |
| Source added | User enables new source |

### 6.2 Polling Flow

```
[Trigger]
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Get user's enabled sources       │
│    GET /user-source-preferences     │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┴─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌────────┐    ┌────────┐
│ Adzuna │  │  Muse  │    │RemoteOK│  ... (parallel)
└───┬────┘  └───┬────┘    └───┬────┘
    │           │             │
    └───────────┴──────┬──────┘
                       ▼
┌─────────────────────────────────────┐
│ 2. Normalize to common schema       │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 3. Deduplication check              │
│    • Same source + external_id?     │
│    • Cross-source similarity?       │
│    • Repost detection?              │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 4. For each new/updated job:        │
│    • Extract skills (LLM)           │
│    • Calculate ghost score          │
│    • POST /job-postings             │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 5. Invoke Strategist for scoring    │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ 6. Update polling state             │
│    PATCH /polling-configuration     │
└─────────────────────────────────────┘
```

### 6.3 Source Adapters

Each external source has an adapter that normalizes to common schema.

| Source | API | Rate Limits | Notes |
|--------|-----|-------------|-------|
| Adzuna | REST | 250/day (free) | Good US/UK coverage |
| The Muse | REST | 3600/hour | Curated companies |
| RemoteOK | REST | Generous | Remote-focused |
| USAJobs | REST | 200/day | US federal jobs |

**Adapter interface:**
```python
class JobSourceAdapter:
    def fetch_jobs(self, params: SearchParams) -> List[RawJob]
    def normalize(self, raw: RawJob) -> JobPostingCreate
```

### 6.4 Skill Extraction

LLM extracts skills from job description.

**Prompt template:**
```
Extract skills from this job posting. For each skill:
- skill_name: The skill (normalize common variations)
- skill_type: "Hard" or "Soft"
- is_required: true if explicitly required, false if nice-to-have
- years_requested: number if specified, null otherwise

Job posting:
{description}

Return JSON array of skills.
```

**Model:** Haiku/GPT-4o-mini (fast, cheap, sufficient for extraction)

### 6.5 Ghost Detection

Calculate ghost score based on signals (REQ-003 §7).

| Signal | Weight | Calculation |
|--------|--------|-------------|
| Days open | 30% | 0-30 days = 0, 31-60 = 50, 60+ = 100 |
| Repost count | 30% | 0 = 0, 1 = 30, 2 = 60, 3+ = 100 |
| Description vagueness | 20% | LLM assessment |
| Missing critical fields | 10% | Salary, deadline, location |
| Requirement mismatch | 10% | Seniority vs. years mismatch |

### 6.6 Deduplication Logic

```python
def is_duplicate(new_job, existing_jobs):
    # Same source, same external ID
    if any(e.source_id == new_job.source_id 
           and e.external_id == new_job.external_id 
           for e in existing_jobs):
        return "update_existing"
    
    # Cross-source: same description hash
    if any(e.description_hash == new_job.description_hash 
           for e in existing_jobs):
        return "add_to_also_found_on"
    
    # Likely repost: same company + similar title + >85% description similarity
    for e in existing_jobs:
        if (e.company_name == new_job.company_name 
            and is_similar_title(e.job_title, new_job.job_title)
            and description_similarity(e.description, new_job.description) > 0.85):
            return "create_linked_repost"
    
    return "create_new"
```

### 6.7 Error Handling

| Error | Handling |
|-------|----------|
| Source API down | Log, skip source, continue with others |
| Rate limit hit | Back off, retry next poll cycle |
| Extraction fails | Store job without extracted skills, flag for retry |
| Scoring fails | Store job with null scores, flag for retry |

---

## 7. Strategist Agent

Scores jobs against user's persona.

### 7.1 Trigger Conditions

| Trigger | Source |
|---------|--------|
| New job discovered | Invoked by Scouter |
| Persona updated | Re-score affected jobs |
| Manual request | "Re-analyze job 123" |

### 7.2 Scoring Flow

```
[Job Posting] + [Persona]
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Non-Negotiables Filter (Pass/Fail)│
│    • Remote preference              │
│    • Minimum salary                 │
│    • Location/commute               │
│    • Industry exclusions            │
│    • Custom filters                 │
└─────────────────┬───────────────────┘
         │
         ├── FAIL → Store in failed_non_negotiables, don't surface
         │
         ▼ PASS
┌─────────────────────────────────────┐
│ 2. Generate/Fetch Embeddings        │
│    • Persona: hard_skills,          │
│      soft_skills, logistics         │
│    • Job: requirements, culture     │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. Calculate Fit Score (0-100)      │
│    • Hard skills: 40%               │
│    • Soft skills: 20%               │
│    • Experience level: 20%          │
│    • Location/logistics: 20%        │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. Calculate Stretch Score (0-100)  │
│    • Target role alignment: 50%     │
│    • Target skills exposure: 50%    │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 5. Update Job Posting               │
│    PATCH /job-postings/{id}         │
│    { fit_score, stretch_score,      │
│      failed_non_negotiables }       │
└─────────────────────────────────────┘
```

### 7.3 Non-Negotiables Filtering

| Filter | Check |
|--------|-------|
| `minimum_base_salary` | `job.salary_max >= persona.minimum_base_salary` (if salary disclosed) |
| `remote_preference = Remote Only` | `job.work_model == Remote` |
| `remote_preference = Hybrid OK` | `job.work_model != Onsite` |
| `commutable_cities` | `job.location in persona.commutable_cities` OR remote |
| `industry_exclusions` | `job.company_industry not in persona.industry_exclusions` |
| `custom_non_negotiables` | Apply each custom filter |

**Jobs that fail store reason in `failed_non_negotiables` but are still created (for transparency).**

### 7.4 Embedding-Based Matching

**Persona embeddings** (from REQ-001 §4):
- `hard_skills`: Technical skills, tools, languages
- `soft_skills`: Communication, leadership, collaboration
- `logistics`: Values, preferences, work style

**Job embeddings:**
- `requirements`: Technical requirements extracted
- `culture`: Culture signals, work environment indicators

**Similarity calculation:**
```python
def calculate_fit_score(persona_embeddings, job_embeddings):
    hard_skills_sim = cosine_similarity(
        persona_embeddings['hard_skills'],
        job_embeddings['requirements']
    )
    soft_skills_sim = cosine_similarity(
        persona_embeddings['soft_skills'],
        job_embeddings['culture']
    )
    # ... combine with weights
    return weighted_average([
        (hard_skills_sim, 0.40),
        (soft_skills_sim, 0.20),
        (experience_match, 0.20),
        (logistics_match, 0.20)
    ])
```

### 7.5 Stretch Score

Measures growth opportunity alignment.

| Factor | Calculation |
|--------|-------------|
| Target role alignment | Similarity between `job.job_title` and `persona.target_roles` |
| Target skills exposure | Count of `persona.target_skills` present in `job.requirements` |

---

## 8. Ghostwriter Agent

Generates tailored application materials.

### 8.1 Trigger Conditions

| Trigger | Condition |
|---------|-----------|
| Auto-draft | Job `fit_score >= persona.auto_draft_threshold` |
| Manual request | User says "Draft materials for this job" |
| Regeneration | User says "Try a different approach" |

### 8.2 Generation Flow

```
[Job Posting] + [Persona] + [BaseResume]
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Select Base Resume               │
│    • Match role_type to job         │
│    • Fall back to is_primary        │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Evaluate tailoring need          │
│    • Keyword gaps?                  │
│    • Bullet relevance?              │
│    • Summary alignment?             │
└─────────────────┬───────────────────┘
         │
         ├── No tailoring needed → Use BaseResume directly
         │
         ▼ Tailoring needed
┌─────────────────────────────────────┐
│ 3. Create Job Variant (Draft)       │
│    • Reorder bullets                │
│    • Adjust summary                 │
│    • Store modifications_description│
│    POST /job-variants               │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. Select Achievement Stories       │
│    • Match to job requirements      │
│    • Prefer recent, quantified      │
│    • Avoid repetition               │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 5. Generate Cover Letter (Draft)    │
│    • Apply Voice Profile            │
│    • Reference selected stories     │
│    • Align with job keywords        │
│    POST /cover-letters              │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 6. Present to user for review       │
│    • Show variant diff              │
│    • Show cover letter draft        │
│    • Explain reasoning              │
└─────────────────────────────────────┘
```

### 8.3 Base Resume Selection

```python
def select_base_resume(job, base_resumes):
    # Try to match role_type
    for br in base_resumes:
        if role_type_matches(br.role_type, job.job_title):
            return br
    
    # Fall back to primary
    return next(br for br in base_resumes if br.is_primary)
```

### 8.4 Tailoring Decision

Agent evaluates need for JobVariant:

| Signal | Action |
|--------|--------|
| Job uses keywords not in summary | Adjust summary |
| Some bullets more relevant than current order | Reorder bullets |
| No changes needed | Use BaseResume directly |

**Modification limits** (from REQ-002 §11.3):
- ✅ Reorder bullets within jobs
- ✅ Adjust summary wording (tone, emphasis)
- ✅ Highlight different skills from BaseResume's list
- ❌ Add content not in Persona
- ❌ Rewrite summary completely
- ❌ Change job history

### 8.5 Cover Letter Generation

**Prompt structure:**
```
You are writing a cover letter for {persona.full_name}.

Voice Profile:
- Tone: {voice_profile.tone}
- Style: {voice_profile.sentence_style}
- Vocabulary: {voice_profile.vocabulary_level}
- Avoid: {voice_profile.things_to_avoid}

Job Details:
{job.description}

Achievement Stories to Reference:
{selected_stories}

Write a cover letter that:
1. Opens with a hook specific to this company/role
2. Highlights relevant achievement(s) from the stories
3. Aligns language with job posting keywords
4. Closes with enthusiasm and call to action
5. Sounds like the person, not a template
```

**Model:** Sonnet/GPT-4o (writing quality critical)

### 8.6 Story Selection Logic

```python
def select_stories(persona, job, max_stories=2):
    scored_stories = []
    for story in persona.achievement_stories:
        score = 0
        # Skills match
        job_skills = {s.skill_name for s in job.extracted_skills}
        story_skills = set(story.skills_demonstrated)
        score += len(job_skills & story_skills) * 10
        
        # Recency (if linked to recent job)
        if story.related_job_id:
            job_entry = get_work_history(story.related_job_id)
            if job_entry.is_current or recent(job_entry.end_date):
                score += 5
        
        # Has quantified outcome
        if has_metrics(story.outcome):
            score += 3
        
        scored_stories.append((story, score))
    
    # Return top N, avoiding repetition from recent applications
    return dedupe_recent(sorted(scored_stories, key=lambda x: -x[1])[:max_stories])
```

### 8.7 Reasoning Explanation

Agent explains its choices:

```
"I've tailored your Scrum Master resume for this role:

**Summary Changes:**
Added emphasis on 'scaled Agile' and 'SAFe' — mentioned 3 times in the job posting.

**Bullet Reordering:**
Moved your SAFe implementation accomplishment to position 1 (was position 4).

**Cover Letter:**
Referenced your 'Turned around failing project' story — it demonstrates the leadership under ambiguity they're looking for.

Ready for you to review!"
```

---

## 9. Agent Communication Patterns

### 9.1 Agent-to-User (via Chat Agent)

| Pattern | Example |
|---------|---------|
| Progress update | "Searching Adzuna... Found 12 new jobs. Scoring..." |
| Result summary | "Found 8 matches above your threshold. Top 3: ..." |
| Action confirmation | "Done! I've favorited the Scrum Master role at Acme." |
| Clarification request | "Which job would you like me to draft materials for?" |
| HITL pause | "I've drafted your cover letter. Ready for review?" |
| Error explanation | "Couldn't reach Adzuna (API timeout). Checked other sources." |

### 9.2 Agent-to-Agent (Internal)

| Pattern | Implementation |
|---------|----------------|
| Scouter → Strategist | Direct function call (same process) or queue message |
| Strategist → Ghostwriter | Triggered when score exceeds auto_draft_threshold |
| Chat → Any agent | LangGraph sub-graph invocation |

### 9.3 SSE Event Types (from REQ-006 §2.5)

| Event | Payload | When |
|-------|---------|------|
| `chat_token` | `{ "text": "..." }` | LLM streaming output |
| `chat_done` | `{ "message_id": "..." }` | Message complete |
| `tool_start` | `{ "tool": "...", "args": {...} }` | Tool execution begins |
| `tool_result` | `{ "tool": "...", "success": bool }` | Tool execution complete |
| `data_changed` | `{ "resource": "...", "id": "...", "action": "..." }` | Data mutation |

---

## 10. Error Handling & Recovery

### 10.1 Transient Errors

| Error Type | Handling |
|------------|----------|
| API timeout | Retry with exponential backoff (3 attempts) |
| Rate limit | Back off, inform user of delay |
| Network error | Retry, then surface to user |

### 10.2 Permanent Errors

| Error Type | Handling |
|------------|----------|
| Invalid input | Surface validation errors to user |
| Resource not found | Clear error message, suggest alternatives |
| Authorization failure | Should never happen (same user context) |

### 10.3 Graceful Degradation

| Scenario | Fallback |
|----------|----------|
| Embedding service down | Skip scoring, show jobs without scores |
| LLM service down | Queue requests, notify user of delay |
| External job API down | Use cached results, note staleness |

---

## 11. Configuration

### 11.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_USER_ID` | (required) | User ID for local mode |
| `LLM_PROVIDER` | `claude` | claude, openai, or gemini |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model for embeddings |
| `SCOUTER_MODEL` | `claude-3-haiku` | Model for extraction |
| `GHOSTWRITER_MODEL` | `claude-3-sonnet` | Model for writing |
| `REDIS_URL` | `redis://localhost:6379` | Checkpoint storage |

### 11.2 Model Routing

| Agent/Task | Claude | OpenAI | Gemini | Rationale |
|------------|--------|--------|--------|-----------|
| Skill extraction | Haiku | GPT-4o-mini | Flash | High volume, simple |
| Ghost detection | Haiku | GPT-4o-mini | Flash | Simple classification |
| Scoring analysis | Sonnet | GPT-4o | Pro | Reasoning needed |
| Cover letter | Sonnet | GPT-4o | Pro | Writing quality |
| Chat responses | Sonnet | GPT-4o | Pro | Conversational nuance |
| Onboarding | Sonnet | GPT-4o | Pro | Interview quality |

---

## 12. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | LangGraph vs. custom state machine? | TBD | Leaning LangGraph for HITL checkpointing |
| 2 | Embedding model choice? | TBD | OpenAI text-embedding-3-small vs. Cohere |
| 3 | How to handle multi-turn clarification? | TBD | LangGraph interrupt + resume |
| 4 | Batch vs. streaming for Scouter? | TBD | Batch likely sufficient |
| 5 | Agent memory across sessions? | TBD | Chat history persistence strategy |

---

## 13. Design Decisions & Rationale

### 13.1 Architecture Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Agent framework | Custom / LangChain / LangGraph / CrewAI | LangGraph | Best HITL support, clean state management, streaming support |
| Agent communication | Direct calls / Message queue / API | Hybrid: direct for sync, API for data | Scouter→Strategist is sync; all writes go through API for consistency |
| Tool implementation | Custom logic / API wrappers | API wrappers | Same validation path as frontend; auditable; consistent |

### 13.2 UX Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Ghostwriter trigger | Always auto / Always manual / Threshold | Threshold (default 90%) | Auto for clear wins, manual for maybes; user configurable |
| Clarification style | Multiple choice / Open-ended / Hybrid | Hybrid | Multiple choice for selection, open-ended for details |
| Progress visibility | Silent / Verbose / Configurable | Verbose by default | Users want to see agents working; builds trust |

### 13.3 Model Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Model per task | Single model for all / Task-specific | Task-specific | Cost optimization; Haiku for volume, Sonnet for quality |
| Provider lock-in | Single provider / Multi-provider | Multi-provider ready | BYOK model for future hosted; local uses Claude SDK |

---

## 14. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-25 | 0.1 | Initial draft. Agent roster, architecture overview, LangGraph framework. Chat Agent tools mapped to REQ-006 endpoints. |

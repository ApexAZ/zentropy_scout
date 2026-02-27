# REQ-007: Agent Behavior Specification

**Status:** Implemented
**Version:** 0.4
**PRD Reference:** §4 Core Agentic Capabilities
**Last Updated:** 2026-02-27

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
| `add_skill` | `POST /personas/{id}/skills` | Add new skill → triggers embedding regen |
| `add_work_history` | `POST /personas/{id}/work-history` | Add job entry → triggers embedding regen |
| `get_change_flags` | `GET /persona-change-flags` | Get pending sync flags |
| `resolve_change_flag` | `PATCH /persona-change-flags/{id}` | Resolve a flag |
| `regenerate_embeddings` | `POST /personas/{id}/embeddings/regenerate` | Force embedding regeneration |
| `rescore_all_jobs` | `POST /job-postings/rescore` | Re-run Strategist on all Discovered jobs |

**Note:** `add_skill` and `add_work_history` automatically trigger embedding regeneration and job rescoring (see §5.5, §7.1). The explicit tools are available for manual/debug scenarios.

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

**CRITICAL: Embedding Regeneration**

When Persona is updated post-onboarding, the system must:
1. Update the Persona data (via API)
2. Regenerate affected Persona Embeddings (see §7.1)
3. Trigger Strategist to re-score all Discovered jobs

**Example flow:**
```
User: "I learned Kubernetes"
         │
         ▼
Chat Agent: add_skill(name="Kubernetes", type="Hard", proficiency="Familiar")
         │
         ▼
API: POST /personas/{id}/skills → 201 Created
         │
         ▼
System: Regenerate hard_skills embedding
         │
         ▼
System: Invoke Strategist.rescore_all_jobs()
         │
         ▼
Chat Agent: "Added Kubernetes to your skills. I'm re-analyzing your job
            matches — you might see new opportunities that need this skill!"
```

Without this flow, new skills won't be reflected in job matching until the next full embedding regeneration.

### 5.6 Onboarding Prompt Templates

The Onboarding Agent maintains a consistent interviewer persona throughout the conversation. These prompts prevent drift into generic chatbot behavior.

#### 5.6.1 System Prompt (Interviewer Persona)

```
You are Scout, a friendly career coach conducting an onboarding interview for a job search assistant.

Your personality:
- Warm but efficient — you respect the user's time
- Curious and encouraging — you draw out details with follow-up questions
- Professional but not stiff — conversational, not corporate
- You celebrate wins and accomplishments without being sycophantic

Your job:
- Guide the user through building their professional profile
- Ask probing questions to surface quantifiable achievements
- Help them articulate skills they might undersell
- Capture their authentic voice for future cover letters

Interview style:
- One question at a time (never overwhelm with multiple questions)
- Acknowledge their answer before moving on
- Use their name occasionally
- If they give a vague answer, probe for specifics ("Can you quantify that?")
- If they seem stuck, offer examples or reframe the question

You are NOT:
- A therapist (stay focused on career)
- A resume writer (you're gathering data, not writing yet)
- Pushy (if they want to skip something, let them)

Current step: {current_step}
Gathered so far: {gathered_data_summary}
```

#### 5.6.2 Step-Specific Prompts

**Work History Expansion:**
```
The user just told you about a role: {role_title} at {company}.

Your task: Help them surface 2-3 strong bullet points for this role.

Ask about:
- Their biggest accomplishment in this role
- A challenge they overcame
- Impact they had (numbers, percentages, scale)

If they give a vague answer like "I led projects", probe:
- "How many projects? What was the scale?"
- "What was the outcome? Did it save time/money/improve something?"

Output: After gathering details, summarize what you'll record and ask for confirmation.
```

**Achievement Story Gathering:**
```
You're gathering achievement stories (STAR format: Situation, Task, Action, Result).

Goal: Capture 3-5 stories that demonstrate different skills.

For each story, you need:
- Context: What was the situation/challenge?
- Action: What specifically did THEY do (not their team)?
- Outcome: What was the measurable result?
- Skills demonstrated: Which skills does this showcase?

Probing questions:
- "What made this challenging?"
- "What would have happened if you hadn't stepped in?"
- "Can you put a number on the impact?"

Stories already captured: {existing_stories}
Skills already covered: {covered_skills}

Ask for a story that demonstrates a DIFFERENT skill than what you already have.
```

**Voice Profile Derivation:**
```
Based on the conversation so far, analyze the user's communication style.

Conversation transcript:
{transcript}

Assess:
1. Tone: Formal/casual? Direct/diplomatic? Confident/humble?
2. Sentence style: Short and punchy? Detailed and thorough?
3. Vocabulary: Technical jargon? Plain English? Industry-specific terms?
4. Patterns to avoid: Buzzwords they never use? Phrases they dislike?

Output a Voice Profile summary (3-4 bullet points) and present it to the user:
"Based on our conversation, here's how I'd describe your professional voice..."

Ask them to confirm or adjust.
```

#### 5.6.3 Transition Prompts

Between sections, use natural transitions:

```
Great, I've got a solid picture of your work history.

Next, let's talk about your skills — both the technical ones and the softer
interpersonal skills that are often just as important.

What would you say are your strongest technical skills?
```

```
Those are excellent stories — I can already see how they'll strengthen your
applications.

Now let's define your non-negotiables — the things that would make you
immediately pass on a job, no matter how interesting it sounds.

First: Are you looking for remote work, hybrid, or are you open to onsite?
```

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

### 6.4 Skill & Culture Extraction

LLM extracts structured data from job description in a single pass.

**Input Truncation:** Job posting `raw_text` can be massive (50k+ chars with embedded HTML/scripts). Before sending to the LLM:
1. Store full `raw_text` in database (for audit/debugging)
2. Truncate to **15,000 characters** for LLM extraction
3. Truncate at word boundary to avoid mid-word cuts

```python
def truncate_for_extraction(raw_text: str, max_chars: int = 15000) -> str:
    """Truncate raw text for LLM extraction while preserving word boundaries."""
    if len(raw_text) <= max_chars:
        return raw_text
    # Find last space before limit
    truncated = raw_text[:max_chars].rsplit(' ', 1)[0]
    return truncated + "..."
```

**CRITICAL:** We extract BOTH skills AND culture text. The culture text is required for soft skills matching (see REQ-008 §6.1). Without it, the Strategist cannot properly score culture fit.

**Prompt template:**
```
Analyze this job posting and extract:

1. SKILLS: For each skill mentioned:
   - skill_name: The skill (normalize common variations)
   - skill_type: "Hard" (technical) or "Soft" (interpersonal)
   - is_required: true if explicitly required, false if nice-to-have
   - years_requested: number if specified, null otherwise

2. CULTURE_TEXT: Extract ONLY text about company culture, values, team environment,
   benefits, and "About Us" content. Do NOT include requirements, responsibilities,
   or technical skills in this section.

Job posting:
{description}

Return JSON:
{
  "skills": [...],
  "culture_text": "..."  // Empty string if no culture content found
}
```

**Example extraction:**

Input:
```
About Acme Corp: We're a fast-paced startup that values innovation and work-life balance.
Our engineering team is collaborative and loves solving hard problems.

Requirements:
- 5+ years Python experience
- Strong communication skills
- Experience with AWS

Benefits: Unlimited PTO, remote-first, equity
```

Output:
```json
{
  "skills": [
    {"skill_name": "Python", "skill_type": "Hard", "is_required": true, "years_requested": 5},
    {"skill_name": "Communication", "skill_type": "Soft", "is_required": true, "years_requested": null},
    {"skill_name": "AWS", "skill_type": "Hard", "is_required": true, "years_requested": null}
  ],
  "culture_text": "We're a fast-paced startup that values innovation and work-life balance. Our engineering team is collaborative and loves solving hard problems. Benefits: Unlimited PTO, remote-first, equity"
}
```

**Model:** Haiku/GPT-4o-mini/Flash (fast, cheap, sufficient for extraction)

**Storage:** The `culture_text` is stored on the JobPosting record and used by the Strategist to generate the `job_culture` embedding (see REQ-008 §6.4).

**Note:** This is a Scouter-specific task (high volume, simple extraction). The Strategist uses Sonnet for scoring analysis (see §11.2). Don't confuse these — skill extraction happens during job discovery, scoring happens after.

**Implementation Note (Shared Service):** The extraction logic in §6.3 and §6.4 MUST be abstracted into a shared service function (e.g., `extract_job_data(raw_text) -> ParsedJob`) that can be called by:
1. The Scouter's background polling loop (async, batch processing)
2. The `/job-postings/ingest` API endpoint (sync, single job from Chrome Extension — see REQ-006 §5.6)

This enables on-demand job ingestion without duplicating extraction logic.

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
| Persona updated | Regenerate embeddings → Re-score all jobs |
| Manual request | "Re-analyze job 123" |

**CRITICAL: Embedding Regeneration on Persona Update**

When Persona data changes (new skill, updated work history, changed non-negotiables), existing Persona Embeddings become stale. The Strategist must use fresh embeddings to avoid the "cold start" problem where new skills don't match jobs.

**Update Flow:**
```
Persona Updated (skill added, job added, etc.)
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Regenerate Persona Embeddings    │
│    • Recalculate hard_skills vector │
│    • Recalculate soft_skills vector │
│    • Recalculate logistics vector   │
│    DELETE old embeddings            │
│    POST /persona-embeddings         │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Re-score All Discovered Jobs     │
│    • Filter to status=Discovered    │
│    • Invoke Strategist for each     │
│    • Update fit_score, stretch_score│
└─────────────────────────────────────┘
```

**Optimization:** Only regenerate affected embedding types:
- Skill added → Regenerate `hard_skills` or `soft_skills` (based on skill_type)
- Non-negotiable changed → Regenerate `logistics`
- Work history added → Regenerate all (bullets may contain skill signals)

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

### 7.6 Strategist Prompt Templates

#### 7.6.1 Score Rationale Generation

After calculating numeric scores, the Strategist generates a human-readable explanation.

**System Prompt:**
```
You are a career match analyst explaining job fit to a job seeker.

Your task: Given the match data, write a 2-3 sentence rationale that:
1. Highlights the strongest alignment (what makes this a good/poor fit)
2. Notes any significant gaps or stretch opportunities
3. Uses specific skill names, not vague language

Tone: Direct, helpful, specific. Avoid generic phrases like "great opportunity" or "good match."

Output format: Plain text, 2-3 sentences max.
```

**User Prompt:**
```
Job: {job_title} at {company_name}

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

Write a 2-3 sentence rationale for this candidate.
```

**Example Output:**
```
Strong technical fit — you have 4 of 5 required skills including the critical ones
(Python, PostgreSQL, FastAPI). The "Kubernetes" requirement is a stretch, but aligns
with your growth target. Salary range ($140-160k) exceeds your minimum.
```

#### 7.6.2 Non-Negotiables Explanation

When a job fails non-negotiables, explain why clearly.

**System Prompt:**
```
You explain why a job posting failed the user's non-negotiable requirements.

Be direct and factual. Don't apologize or soften the message.
One sentence per failed requirement.
```

**User Prompt:**
```
Job: {job_title} at {company_name}

Failed requirements:
{failed_list}

User's settings:
{user_non_negotiables}

Explain each failure in one sentence.
```

**Example Output:**
```
• Remote: This role requires onsite presence in Austin, TX — you specified Remote Only.
• Salary: Listed range ($90-110k) is below your $120k minimum.
```

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

**CRITICAL: Duplicate Prevention**

Before generating materials, the Ghostwriter must check for existing JobVariants to prevent race conditions (user clicking "Draft" multiple times while LLM is generating).

```
[Job Posting] + [Persona] + [BaseResume]
         │
         ▼
┌─────────────────────────────────────┐
│ 0. Check Existing JobVariant        │
│    GET /job-variants?job_posting_id=│
│                                     │
│    ├── None exists → Proceed        │
│    │                                │
│    ├── Draft exists → Resume/Update │
│    │   "I'm already working on this.│
│    │    Want me to start fresh?"    │
│    │                                │
│    └── Approved exists → STOP       │
│        "You already have an approved│
│         resume for this job."       │
└─────────────────┬───────────────────┘
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

**Race Condition Handling:**

| Scenario | Behavior |
|----------|----------|
| User triggers draft while one is in progress | Return existing draft, show progress |
| User triggers draft, previous draft exists | Ask: "Overwrite existing draft?" |
| User triggers draft, approved variant exists | Block: "You already approved materials for this job" |
| User explicitly asks to regenerate | Archive old draft, create new one |

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

### 10.4 Concurrency & Race Conditions

**CRITICAL:** These scenarios can corrupt data or confuse users if not handled explicitly.

#### 10.4.1 Stale Embeddings ("Cold Start" Problem)

**Scenario:** User adds skill "Kubernetes" → Scouter runs → Strategist scores jobs using old embeddings (without Kubernetes) → User doesn't see Kubernetes-related matches.

**Prevention:**
```
Persona Update Event
         │
         ▼
┌─────────────────────────────────────┐
│ 1. BLOCK: Pause any in-flight       │
│    Scouter/Strategist runs          │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Invalidate Persona Embeddings    │
│    DELETE FROM persona_embeddings   │
│    WHERE persona_id = ?             │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. Regenerate Embeddings            │
│    POST /personas/{id}/embeddings   │
└─────────────────┬───────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. UNBLOCK: Resume Scouter/Strategist│
│    Now using fresh embeddings       │
└─────────────────────────────────────┘
```

**Implementation:** Use a `persona_embedding_version` counter. Strategist checks version before scoring; if stale, waits for regeneration.

#### 10.4.2 Duplicate JobVariant Generation

**Scenario:** User clicks "Draft materials" → LLM takes 15 seconds → User thinks it's stuck, clicks again → Two Draft JobVariants created for same job.

**Prevention:**
```python
def ghostwriter_start(job_posting_id: str):
    # Check for existing variant
    existing = db.query(JobVariant).filter(
        job_posting_id=job_posting_id,
        status__in=['Draft', 'Approved']
    ).first()

    if existing and existing.status == 'Draft':
        return {"action": "resume", "variant_id": existing.id,
                "message": "Already drafting materials for this job."}

    if existing and existing.status == 'Approved':
        return {"action": "block",
                "message": "You already have approved materials for this job."}

    # Safe to proceed
    return {"action": "create"}
```

**User Experience:**
- If Draft exists: "I'm already working on this. Check back in a moment!"
- If Approved exists: "You already have an approved resume for this job. Would you like to create a new version?"

#### 10.4.3 Expired Job During Draft

**Scenario:** User opens job, starts "Draft materials" → During generation, Scouter marks job as Expired (posting disappeared) → Ghostwriter finishes, but job is gone.

**Prevention:**
```python
def ghostwriter_complete(job_posting_id: str, variant: JobVariant):
    job = db.query(JobPosting).get(job_posting_id)

    if job.status == 'Expired':
        return {
            "variant": variant,  # Still save the work
            "warning": "Heads up: This job posting appears to have been removed. "
                       "Your materials are saved in case it reappears or you want "
                       "to use them for a similar role."
        }
```

#### 10.4.4 Concurrent Persona Edits

**Scenario:** User says "Add Python to my skills" in chat → Meanwhile, user also edits Persona in UI → Race condition on Persona record.

**Prevention:** Optimistic locking with `updated_at` check.
```python
def update_persona(persona_id: str, changes: dict, expected_version: datetime):
    persona = db.query(Persona).get(persona_id)

    if persona.updated_at != expected_version:
        raise ConflictError("Persona was modified. Please refresh and retry.")

    persona.update(changes)
    persona.updated_at = now()
```

#### 10.4.5 Summary Table

| Race Condition | Detection | Prevention | User Message |
|----------------|-----------|------------|--------------|
| Stale embeddings | Version counter mismatch | Block scoring until regen | "Updating your matches with new skills..." |
| Duplicate variant | Existing Draft/Approved check | Return existing or block | "Already working on this job" |
| Expired job | Status check on completion | Warn but save work | "Job may have been removed" |
| Concurrent edits | `updated_at` mismatch | Optimistic locking | "Please refresh and retry" |

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
| 1 | LangGraph vs. custom state machine? | **Resolved** | LangGraph confirmed. See §15 for graph specifications. |
| 2 | Embedding model choice? | TBD | OpenAI text-embedding-3-small vs. Cohere. Defer to implementation. |
| 3 | How to handle multi-turn clarification? | **Resolved** | LangGraph interrupt + resume. See §15.2 (Onboarding) for checkpoint pattern. |
| 4 | Batch vs. streaming for Scouter? | **Resolved** | Batch. Scouter runs as background job, no streaming needed. |
| 5 | Agent memory across sessions? | **Resolved** | Redis for LangGraph checkpoints (24h TTL). Chat history persisted via API. |

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
| 2026-01-25 | 0.2 | **Critical fixes from peer review:** (1) Added embedding regeneration flow to §7.1 and §5.5 — fixes "cold start" problem where Persona updates weren't reflected in job matching. (2) Added duplicate JobVariant check to §8.2 step 0 — prevents race condition when user triggers draft multiple times. (3) Clarified model usage in §6.4 — Scouter uses Haiku for extraction, Strategist uses Sonnet for scoring. |
| 2026-01-25 | 0.3 | **Coding agent support:** Added §5.6 Onboarding Prompt Templates (interviewer persona, step-specific prompts). Added §7.6 Strategist Prompt Templates (score rationale, non-negotiables explanation). Added §10.4 Concurrency & Race Conditions (stale embeddings, duplicate variants, expired jobs, concurrent edits). Added §15 Graph Specifications (LangGraph node/edge definitions for all agents). |
| 2026-01-25 | 0.4 | **Culture text extraction:** Updated §6.4 to extract `culture_text` alongside skills — required for soft skills embedding (REQ-008 §6.1). Without this, Strategist would pollute culture matching with technical keywords from job description. |

---

## 15. Graph Specifications (LangGraph)

This section provides explicit node and edge definitions for implementing agents in LangGraph. These are prescriptive — the coding agent should implement these graphs as specified.

### 15.1 Chat Agent Graph

The Chat Agent is the main entry point for user interaction.

```python
from langgraph.graph import StateGraph, END

chat_graph = StateGraph(ChatAgentState)

# Nodes
chat_graph.add_node("receive_message", receive_message)      # Parse user input
chat_graph.add_node("classify_intent", classify_intent)      # Determine what user wants
chat_graph.add_node("select_tools", select_tools)            # Pick appropriate tools
chat_graph.add_node("execute_tools", execute_tools)          # Run selected tools
chat_graph.add_node("generate_response", generate_response)  # Formulate reply
chat_graph.add_node("stream_response", stream_response)      # Send via SSE
chat_graph.add_node("delegate_onboarding", delegate_onboarding)  # Sub-graph
chat_graph.add_node("delegate_ghostwriter", delegate_ghostwriter) # Sub-graph
chat_graph.add_node("request_clarification", request_clarification)

# Entry point
chat_graph.set_entry_point("receive_message")

# Edges
chat_graph.add_edge("receive_message", "classify_intent")

# Conditional edges from classify_intent
chat_graph.add_conditional_edges(
    "classify_intent",
    route_by_intent,
    {
        "tool_call": "select_tools",
        "onboarding": "delegate_onboarding",
        "ghostwriter": "delegate_ghostwriter",
        "clarification_needed": "request_clarification",
        "direct_response": "generate_response"
    }
)

# Tool execution flow
chat_graph.add_edge("select_tools", "execute_tools")
chat_graph.add_conditional_edges(
    "execute_tools",
    check_tool_result,
    {
        "success": "generate_response",
        "needs_more_tools": "select_tools",
        "error": "generate_response"
    }
)

# Sub-graph returns
chat_graph.add_edge("delegate_onboarding", "generate_response")
chat_graph.add_edge("delegate_ghostwriter", "generate_response")
chat_graph.add_edge("request_clarification", "stream_response")

# Final output
chat_graph.add_edge("generate_response", "stream_response")
chat_graph.add_edge("stream_response", END)
```

**Routing Function:**
```python
def route_by_intent(state: ChatAgentState) -> str:
    intent = state["classified_intent"]

    if intent.type == "onboarding_request":
        return "onboarding"
    if intent.type == "draft_materials":
        return "ghostwriter"
    if intent.confidence < 0.7:
        return "clarification_needed"
    if intent.requires_tools:
        return "tool_call"
    return "direct_response"
```

### 15.2 Onboarding Agent Graph

Structured interview flow with HITL checkpoints.

```python
onboarding_graph = StateGraph(OnboardingState)

# Nodes (one per interview step)
onboarding_graph.add_node("check_resume_upload", check_resume_upload)
onboarding_graph.add_node("gather_basic_info", gather_basic_info)
onboarding_graph.add_node("gather_work_history", gather_work_history)
onboarding_graph.add_node("expand_bullets", expand_bullets)
onboarding_graph.add_node("gather_education", gather_education)
onboarding_graph.add_node("gather_skills", gather_skills)
onboarding_graph.add_node("gather_certifications", gather_certifications)
onboarding_graph.add_node("gather_stories", gather_stories)
onboarding_graph.add_node("gather_non_negotiables", gather_non_negotiables)
onboarding_graph.add_node("gather_growth_targets", gather_growth_targets)
onboarding_graph.add_node("derive_voice_profile", derive_voice_profile)
onboarding_graph.add_node("review_persona", review_persona)
onboarding_graph.add_node("setup_base_resume", setup_base_resume)
onboarding_graph.add_node("complete_onboarding", complete_onboarding)

# HITL checkpoint nodes
onboarding_graph.add_node("wait_for_input", wait_for_input)  # Pause for user response

# Entry point (resume checkpoint-aware)
onboarding_graph.set_entry_point("check_resume_upload")

# Linear flow with HITL pauses
STEPS = [
    ("check_resume_upload", "gather_basic_info"),
    ("gather_basic_info", "gather_work_history"),
    ("gather_work_history", "expand_bullets"),
    ("expand_bullets", "gather_education"),
    ("gather_education", "gather_skills"),
    ("gather_skills", "gather_certifications"),
    ("gather_certifications", "gather_stories"),
    ("gather_stories", "gather_non_negotiables"),
    ("gather_non_negotiables", "gather_growth_targets"),
    ("gather_growth_targets", "derive_voice_profile"),
    ("derive_voice_profile", "review_persona"),
    ("review_persona", "setup_base_resume"),
    ("setup_base_resume", "complete_onboarding"),
]

for from_node, to_node in STEPS:
    # Each step waits for user input before proceeding
    onboarding_graph.add_conditional_edges(
        from_node,
        check_step_complete,
        {
            "needs_input": "wait_for_input",
            "complete": to_node,
            "skip_requested": to_node  # User asked to skip optional section
        }
    )
    onboarding_graph.add_edge("wait_for_input", from_node)  # Return after input

onboarding_graph.add_edge("complete_onboarding", END)
```

**State Schema:**
```python
class OnboardingState(TypedDict):
    persona_id: str
    current_step: str  # Persisted for resume
    gathered_data: dict  # Accumulated responses
    conversation_history: List[dict]
    pending_question: Optional[str]
    user_response: Optional[str]
    skipped_sections: List[str]
```

### 15.3 Scouter Agent Graph

Job discovery pipeline with parallel source fetching.

```python
scouter_graph = StateGraph(ScouterState)

# Nodes
scouter_graph.add_node("get_enabled_sources", get_enabled_sources)
scouter_graph.add_node("fetch_adzuna", fetch_adzuna)
scouter_graph.add_node("fetch_muse", fetch_muse)
scouter_graph.add_node("fetch_remoteok", fetch_remoteok)
scouter_graph.add_node("fetch_usajobs", fetch_usajobs)
scouter_graph.add_node("merge_results", merge_results)
scouter_graph.add_node("deduplicate_jobs", deduplicate_jobs)
scouter_graph.add_node("extract_skills", extract_skills)  # LLM call (Haiku)
scouter_graph.add_node("calculate_ghost_score", calculate_ghost_score)
scouter_graph.add_node("save_jobs", save_jobs)
scouter_graph.add_node("invoke_strategist", invoke_strategist)  # Sub-graph
scouter_graph.add_node("update_poll_state", update_poll_state)

# Entry
scouter_graph.set_entry_point("get_enabled_sources")

# Parallel fetch (fan-out)
scouter_graph.add_conditional_edges(
    "get_enabled_sources",
    get_source_nodes,
    {
        "adzuna": "fetch_adzuna",
        "muse": "fetch_muse",
        "remoteok": "fetch_remoteok",
        "usajobs": "fetch_usajobs",
    }
)

# Fan-in: all fetchers merge
for source in ["fetch_adzuna", "fetch_muse", "fetch_remoteok", "fetch_usajobs"]:
    scouter_graph.add_edge(source, "merge_results")

# Processing pipeline
scouter_graph.add_edge("merge_results", "deduplicate_jobs")

scouter_graph.add_conditional_edges(
    "deduplicate_jobs",
    check_new_jobs,
    {
        "has_new_jobs": "extract_skills",
        "no_new_jobs": "update_poll_state"
    }
)

scouter_graph.add_edge("extract_skills", "calculate_ghost_score")
scouter_graph.add_edge("calculate_ghost_score", "save_jobs")
scouter_graph.add_edge("save_jobs", "invoke_strategist")
scouter_graph.add_edge("invoke_strategist", "update_poll_state")
scouter_graph.add_edge("update_poll_state", END)
```

**Routing Functions:**
```python
def get_source_nodes(state: ScouterState) -> List[str]:
    """Return list of enabled source node names."""
    return [s.source_name for s in state["enabled_sources"]]

def check_new_jobs(state: ScouterState) -> str:
    return "has_new_jobs" if len(state["new_jobs"]) > 0 else "no_new_jobs"
```

### 15.4 Strategist Agent Graph

Scoring and matching (invoked as sub-graph by Scouter or Chat).

```python
strategist_graph = StateGraph(StrategistState)

# Nodes
strategist_graph.add_node("load_persona_embeddings", load_persona_embeddings)
strategist_graph.add_node("check_embedding_freshness", check_embedding_freshness)
strategist_graph.add_node("regenerate_embeddings", regenerate_embeddings)
strategist_graph.add_node("filter_non_negotiables", filter_non_negotiables)
strategist_graph.add_node("generate_job_embeddings", generate_job_embeddings)
strategist_graph.add_node("calculate_fit_score", calculate_fit_score)
strategist_graph.add_node("calculate_stretch_score", calculate_stretch_score)
strategist_graph.add_node("generate_rationale", generate_rationale)  # LLM call (Sonnet)
strategist_graph.add_node("save_scores", save_scores)
strategist_graph.add_node("trigger_ghostwriter", trigger_ghostwriter)

# Entry
strategist_graph.set_entry_point("load_persona_embeddings")

# Embedding freshness check (prevents cold start problem)
strategist_graph.add_edge("load_persona_embeddings", "check_embedding_freshness")
strategist_graph.add_conditional_edges(
    "check_embedding_freshness",
    is_embedding_stale,
    {
        "stale": "regenerate_embeddings",
        "fresh": "filter_non_negotiables"
    }
)
strategist_graph.add_edge("regenerate_embeddings", "filter_non_negotiables")

# Non-negotiables filter (early exit for failed jobs)
strategist_graph.add_conditional_edges(
    "filter_non_negotiables",
    check_non_negotiables_pass,
    {
        "pass": "generate_job_embeddings",
        "fail": "save_scores"  # Save with failed_non_negotiables, skip scoring
    }
)

# Scoring pipeline
strategist_graph.add_edge("generate_job_embeddings", "calculate_fit_score")
strategist_graph.add_edge("calculate_fit_score", "calculate_stretch_score")
strategist_graph.add_edge("calculate_stretch_score", "generate_rationale")
strategist_graph.add_edge("generate_rationale", "save_scores")

# Auto-draft trigger
strategist_graph.add_conditional_edges(
    "save_scores",
    check_auto_draft_threshold,
    {
        "above_threshold": "trigger_ghostwriter",
        "below_threshold": END
    }
)
strategist_graph.add_edge("trigger_ghostwriter", END)
```

**Routing Functions:**
```python
def is_embedding_stale(state: StrategistState) -> str:
    """Check if persona embeddings are stale (version mismatch)."""
    current_version = state["persona_embedding_version"]
    expected_version = state["persona"].embedding_version
    return "stale" if current_version != expected_version else "fresh"

def check_auto_draft_threshold(state: StrategistState) -> str:
    threshold = state["persona"].auto_draft_threshold
    return "above_threshold" if state["fit_score"] >= threshold else "below_threshold"
```

### 15.5 Ghostwriter Agent Graph

Content generation with duplicate prevention.

```python
ghostwriter_graph = StateGraph(GhostwriterState)

# Nodes
ghostwriter_graph.add_node("check_existing_variant", check_existing_variant)
ghostwriter_graph.add_node("handle_duplicate", handle_duplicate)
ghostwriter_graph.add_node("select_base_resume", select_base_resume)
ghostwriter_graph.add_node("evaluate_tailoring_need", evaluate_tailoring_need)
ghostwriter_graph.add_node("create_job_variant", create_job_variant)  # LLM call
ghostwriter_graph.add_node("select_achievement_stories", select_achievement_stories)
ghostwriter_graph.add_node("generate_cover_letter", generate_cover_letter)  # LLM call (Sonnet)
ghostwriter_graph.add_node("check_job_still_active", check_job_still_active)
ghostwriter_graph.add_node("present_for_review", present_for_review)

# Entry
ghostwriter_graph.set_entry_point("check_existing_variant")

# Duplicate prevention (critical!)
ghostwriter_graph.add_conditional_edges(
    "check_existing_variant",
    route_existing_variant,
    {
        "none_exists": "select_base_resume",
        "draft_exists": "handle_duplicate",
        "approved_exists": "handle_duplicate"
    }
)
ghostwriter_graph.add_edge("handle_duplicate", END)  # Exit with message

# Generation flow
ghostwriter_graph.add_edge("select_base_resume", "evaluate_tailoring_need")
ghostwriter_graph.add_conditional_edges(
    "evaluate_tailoring_need",
    needs_tailoring,
    {
        "needs_tailoring": "create_job_variant",
        "no_tailoring": "select_achievement_stories"  # Use BaseResume as-is
    }
)
ghostwriter_graph.add_edge("create_job_variant", "select_achievement_stories")
ghostwriter_graph.add_edge("select_achievement_stories", "generate_cover_letter")

# Check job status before presenting
ghostwriter_graph.add_edge("generate_cover_letter", "check_job_still_active")
ghostwriter_graph.add_conditional_edges(
    "check_job_still_active",
    is_job_active,
    {
        "active": "present_for_review",
        "expired": "present_for_review"  # Still present, but with warning
    }
)
ghostwriter_graph.add_edge("present_for_review", END)
```

**Routing Functions:**
```python
def route_existing_variant(state: GhostwriterState) -> str:
    existing = state.get("existing_variant")
    if not existing:
        return "none_exists"
    return "draft_exists" if existing.status == "Draft" else "approved_exists"

def needs_tailoring(state: GhostwriterState) -> str:
    """Check if BaseResume needs modification for this job."""
    analysis = state["tailoring_analysis"]
    return "needs_tailoring" if analysis.modification_needed else "no_tailoring"
```

### 15.6 Graph Invocation Patterns

**Chat Agent invoking sub-graphs:**
```python
# In Chat Agent's delegate_ghostwriter node
async def delegate_ghostwriter(state: ChatAgentState) -> ChatAgentState:
    ghostwriter_state = GhostwriterState(
        job_posting_id=state["target_job_id"],
        persona_id=state["persona_id"],
        user_id=state["user_id"]
    )

    result = await ghostwriter_graph.ainvoke(ghostwriter_state)

    state["tool_results"].append({
        "tool": "ghostwriter",
        "result": result
    })
    return state
```

**Scheduled Scouter invocation:**
```python
# Triggered by scheduler (e.g., Celery beat)
async def scheduled_scouter_run(user_id: str):
    persona = await get_persona(user_id)

    scouter_state = ScouterState(
        user_id=user_id,
        persona_id=persona.id,
        enabled_sources=await get_enabled_sources(user_id)
    )

    await scouter_graph.ainvoke(scouter_state)
```

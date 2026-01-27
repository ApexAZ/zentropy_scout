# 🌀 PRD: Zentropy Scout

**Version:** 2.2 (Final Review Pass)
**License:** AGPL-3.0
**Status:** Approved for Development

---

## 1. Executive Summary

**The Problem:** Job searching is broken. Candidates spend hours tailoring resumes, writing cover letters, and tracking applications in spreadsheets — only to spray dozens of applications and pray for responses. It's exhausting, inefficient, and demoralizing.

**The Solution:** Zentropy Scout is an AI-powered job search assistant that works *with* you, not instead of you. It learns who you are — your skills, your stories, your dealbreakers — then continuously scans the market for roles that actually fit. When it finds a match, it drafts tailored application materials for your review. You stay in control; the AI handles the grunt work.

**How It Works:**
1. **You share your story** — Upload your resume and complete a guided interview so the system understands your experience, strengths, and what you're looking for.
2. **Scout finds opportunities** — AI agents periodically scan job boards, filtering out noise and surfacing high-quality matches.
3. **Review and refine** — For each opportunity, you see a match score, a tailored resume, and a draft cover letter. Edit or approve with one click.
4. **Track your progress** — A built-in dashboard tracks every application from draft to offer, keeping your job search organized.

**Key Principles:**
- **Human-in-the-Loop:** The AI proposes, you decide. Nothing is sent without your approval.
- **No Spam:** Every application is uniquely tailored to the specific job. The system never generates generic, one-size-fits-all materials.
- **Full Traceability:** Every application is linked to the exact resume version, cover letter version, and job posting snapshot used — so you always know what you submitted and when.

---

## 2. Product Goals & Objectives

### 2.1 Primary Objectives

- **High-Fidelity Scouting:** Identify roles that align not just with keywords, but with the user's nuanced history and "Value Criteria" (e.g., remote culture, specific tech stacks, industries to avoid).

- **Proactive Application Engineering:** Automatically generate a tailored Cover Letter and a "Redline" Resume version for high-match opportunities.

- **Collaborative Refinement:** Provide a specialized interface where users can review, edit, and accept the agent's proposed resume changes before creating a final PDF.

- **Application Lifecycle Tracking:** Maintain a clear view of all applications from discovery through outcome, with status updates and notes.

- **Document Version Control:** Track all resume and cover letter versions, linking each to the specific applications where they were used.

### 2.2 Strategic Value

- **Zero-Friction Starts:** The user never faces a blank page. Applications begin with AI-generated drafts ready for review.

- **Deep Context Utilization:** The agent mines the user's full history (including "hidden" wins discovered during onboarding) to surface relevance that standard keyword matching misses.

- **Terminology Alignment:** Generated content mirrors the job posting's language and keywords to improve ATS compatibility and reader resonance.

### 2.3 Success Metrics

| Metric | Measured By |
|--------|-------------|
| **Match Quality** | Are high-quality, relevant jobs being surfaced and low-quality jobs filtered out? |
| **Resume Integrity** | Are resumes refined for fit without distorting actual experience and skills? |
| **Tracking Integrity** | Are applications logged with correct resume/cover letter linkage? |
| **Document Organization** | Can users easily find and compare document versions? |

### 2.4 Non-Goals (MVP)

The following are explicitly out of scope for MVP but may be considered for future enhancements:

- **No Auto-Submit:** The system will not interact with external application portals (clicking "Submit") without manual user action.

- **No Fabrication:** The system will never invent experience, skills, or credentials. Tailoring means highlighting and reframing, not lying.

- **No Data Selling:** User data (resume, persona, application history) is never sold to recruiters or third parties.

- **No Interview Prep:** Scope is limited to getting interviews, not preparing for them.

- **No Career Coaching:** The system executes on user-defined goals; it does not advise on career direction.

---

## 3. The Persona Framework

The persona is the user's complete professional profile — a combination of resume data and enriched context gathered through a guided interview. It serves as the "Source of Truth" for all matching and content generation.

### 3.1 Resume Foundation

Users are encouraged to upload an existing resume (PDF or DOCX) as the starting point:

- System extracts baseline data: contact info, work history, education, skills, accomplishments
- Original document is stored for reference and version tracking
- Extracted data becomes the foundation for the persona

**No resume?** Users without a resume can skip this step. The Discovery Interview will expand to gather baseline information directly. Future enhancement: generate a starter resume from interview data.

### 3.2 Discovery Interview

An AI agent reviews any uploaded resume, then conducts a guided conversation to fill gaps and add depth. The interview focuses on five areas:

| Area | Purpose |
|------|---------|
| **Achievement Stories** | Capture accomplishments and problem-solving examples not on the resume |
| **Skill Proficiency Levels** | Distinguish expertise depth (expert vs. familiar) to weight scoring accurately |
| **Non-Negotiables** | Define hard filters: industries to avoid, location requirements, minimum compensation, etc. |
| **Professional Voice** | Understand the user's tone and style for authentic content generation |
| **Growth Targets** | Identify skills or roles the user wants to grow into |

### 3.3 Persona Structure

The combined data forms a structured profile organized for matching:

| Aspect | Used For |
|--------|----------|
| **Hard Skills** | Technical matching, ATS keyword alignment |
| **Soft Skills** | Culture and communication style matching |
| **Logistics & Values** | Non-negotiables filtering, preference scoring |

The persona is editable — users can update it as their goals or circumstances change.

---

## 4. Core Agentic Capabilities

The system uses four specialized AI agents, each with a distinct role in the job search workflow.

### 4.1 The Onboarding Agent

**Role:** Persona Building

Conducts the Discovery Interview described in Section 3. Reviews any uploaded resume, then guides the user through a conversation to extract deep context: achievement stories, skill proficiency levels, non-negotiables, professional voice, and growth targets.

**Behavior:**
- Adapts questions based on resume content (or lack thereof)
- Validates completeness before unlocking the dashboard
- Can be re-engaged later to update the persona

### 4.2 The Scouter

**Role:** Job Discovery

Monitors job sources on a user-configurable schedule (default: once per day) to find new opportunities. Integrates with major job boards, company career pages, and aggregators.

**Filtering:**
- **Ghost Job Detection:** Analyzes posting patterns (repost frequency, listing age) to filter out stale or fake postings.
- **Duplicate Prevention:** Cross-references discovered jobs against application history and dismissed jobs to avoid surfacing positions already seen.
- **Dismissed Job Awareness:** Jobs dismissed by the user are excluded from future results.

### 4.3 The Strategist

**Role:** Match Analysis

Evaluates discovered jobs against the user's persona using a two-phase process:

**Phase 1: Non-Negotiables Filter (Pass/Fail)**

Jobs must pass all user-defined dealbreakers before scoring:
- Location / Remote policy
- Visa sponsorship requirements
- Industry exclusions
- Minimum compensation threshold

Jobs that fail any Non-Negotiable are filtered out and never shown to the user.

**Phase 2: Weighted Scoring (0-100)**

Surviving jobs are scored using vector similarity across three embedded aspects:

| Aspect | Default Weight | Embedding Source |
|--------|----------------|------------------|
| Hard Skills | 40% | Technical stack, tools, languages |
| Soft Skills | 30% | Leadership style, communication, collaboration |
| Logistics | 30% | Culture fit, work style, growth opportunity |

Weights are user-configurable with the option to reset to system defaults.

**Gap Analysis:** For high-scoring roles, identifies skill gaps (e.g., "Job requires Kubernetes, User has Docker") to inform the Ghostwriter.

### 4.4 The Ghostwriter

**Role:** Content Generation

Generates tailored application materials for high-match opportunities.

**Auto-Draft Setting:** When enabled, the Ghostwriter automatically generates materials for jobs exceeding the match threshold (user-configurable, default: 90%). When disabled, users manually trigger drafting for jobs they're interested in.

- **Resume Redlining:** Creates a job-specific copy of the resume, re-ordering bullet points to prioritize relevant skills and adjusting the summary to align with job terminology.

- **Cover Letter Generation:** Selects an Achievement Story that demonstrates fitness for the role and drafts a narrative letter in the user's voice.

---

## 5. Technical Architecture

### 5.1 LLM Provider Strategy

The system will have two separate implementations to cleanly separate personal and public use cases.

**Implementation Phases:**

| Phase | Target | Provider | Priority |
|-------|--------|----------|----------|
| **Phase 1 (MVP)** | Personal use | Claude SDK/CLI | Primary focus |
| **Phase 2 (Future, TBD)** | Public deployment | BYOK (Bring Your Own Key) | If pursued |

**Phase 1: Personal Use (MVP)**

| Provider | Authentication | Notes |
|----------|----------------|-------|
| **Claude SDK/CLI** | Local Claude Code auth (Max subscription) | Uses existing subscription quota, no per-token cost |

The Claude SDK/CLI leverages an authenticated local Claude Code installation. Authentication is performed via `claude login` and credentials are stored locally in `~/.claude/`. This is suitable only for the machine where authentication was performed.

**Phase 2: Public Deployment (Future, If Pursued)**

| Provider | Authentication | Notes |
|----------|----------------|-------|
| **Claude API** | User's API key | Primary option |
| **OpenAI API** | User's API key | Alternative |
| **Gemini API** | User's API key | Alternative |

In the BYOK model, each user provides their own API key and pays their own per-token costs. The application does not subsidize or proxy LLM usage for public users.

**Model Routing by Agent:**

| Agent | Claude | OpenAI | Gemini | Rationale |
|-------|--------|--------|--------|-----------|
| **Scouter** | Haiku | GPT-4o-mini | Flash | High volume, simple extraction |
| **Strategist** | Sonnet | GPT-4o | Pro | Reasoning, scoring |
| **Ghostwriter** | Sonnet | GPT-4o | Pro | Writing quality critical |
| **Onboarding** | Sonnet | GPT-4o | Pro | Conversational nuance |

### 5.2 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js (React) | Dashboard, Persona Manager, Diff View interface |
| **Backend** | FastAPI | Async Python API for agent orchestration |
| **Agent Framework** | LangGraph (or equivalent) | Stateful workflows with pause/resume for HITL |
| **Database** | PostgreSQL + pgvector | Relational data + vector embeddings for semantic matching |
| **Task Queue** | Redis | Background jobs, agent state checkpoints |
| **Containerization** | Docker Compose | Local development and deployment |

### 5.3 Deployment

**MVP:** Local deployment via Docker Compose.

**Future:** Cloud hosting (e.g., Render) if productionized for public use.

---

## 6. Data Strategy

### 6.1 Hybrid Storage Approach

The system leverages **PostgreSQL** as a hybrid store, combining the data integrity of SQL with the flexibility of NoSQL.

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| **Rigid Tables** | Standard SQL | Core relationships (Users, IDs, timestamps, status flags). Ensures data integrity and efficient indexing |
| **JSONB Columns** | PostgreSQL JSONB | Complex, variable data (Resume structures, Job Descriptions, API configurations). Allows schema evolution without breaking the application |
| **Vector Embeddings** | pgvector | Mathematical representation of user personas and job descriptions, enabling semantic "meaning-based" matching |

### 6.2 Core Entities

| Entity | Purpose | Key Relationships |
|--------|---------|-------------------|
| **User** | Account and authentication | One-to-one with Persona |
| **Persona** | Professional profile (resume + interview data) | Links to Embeddings, owned by User |
| **Resume** | Document versions (base, master, variants) | Belongs to Persona, linked to Applications |
| **CoverLetter** | Generated and edited letters | Linked to Applications |
| **JobPosting** | Discovered job opportunities | Scored against Persona, linked to Applications |
| **Application** | Tracks submission lifecycle | Links JobPosting + Resume + CoverLetter |
| **Embedding** | Vector representations for matching | Belongs to Persona or JobPosting |

### 6.3 Embedding Strategy

Vector embeddings power the semantic matching between personas and job postings.

**What Gets Embedded:**

| Source | Embedding Type | When Generated |
|--------|----------------|----------------|
| **Persona: Hard Skills** | Skills vector | On persona creation/update |
| **Persona: Soft Skills** | Communication/style vector | On persona creation/update |
| **Persona: Logistics** | Values/preferences vector | On persona creation/update |
| **JobPosting: Requirements** | Requirements vector | On job ingestion |
| **JobPosting: Culture Signals** | Culture vector | On job ingestion |

**How Matching Works:**

1. Each persona aspect is embedded separately (not one giant vector)
2. Each job posting is embedded into comparable vectors
3. Cosine similarity is computed for each aspect pair
4. Weighted combination produces the final match score (see §4.3)

**Embedding Model:** TBD during implementation. Options include OpenAI `text-embedding-3-small`, Cohere `embed-v3`, or Claude's embedding capabilities.

### 6.4 Data Retention

| Data Type | Retention Policy |
|-----------|------------------|
| **Persona** | Indefinite (user-owned data) |
| **Resume Versions** | Indefinite (full history preserved) |
| **Cover Letter Versions** | Indefinite (full history preserved) |
| **Job Postings** | Indefinite for applied jobs; configurable for unapplied (default: 90 days) |
| **Application Records** | Indefinite (audit trail) |
| **Embeddings** | Regenerated on source update; old versions discarded |

### 6.5 Privacy Considerations

**MVP (Single-User):**
- All data stored locally in PostgreSQL container
- No data leaves the user's machine except for LLM API calls
- LLM prompts contain persona/job data — user accepts this by using the system

**Future (Multi-User, If Pursued):**
- User data isolated by account (row-level security)
- No cross-user data sharing
- No selling or sharing of user data with third parties (see §2.4 Non-Goals)
- Consider data export/delete functionality for compliance

---

## 7. User Interface & Workflow

### 7.1 Entry Point & Onboarding Gate

When a user lands on the application, the system checks their onboarding status:

| User State | Behavior |
|------------|----------|
| **New User** | Redirect to Onboarding flow (resume upload → Discovery Interview) |
| **Incomplete Onboarding** | Prompt to continue where they left off |
| **Onboarded** | Show Dashboard with full functionality |

The user cannot access the Dashboard features until onboarding is complete. This ensures the system has sufficient context to provide value.

**MVP Note:** Phase 1 assumes Claude SDK/CLI is pre-configured on the local machine. No in-app provider configuration is needed. Future public deployment (Phase 2) would add a provider configuration step during onboarding.

### 7.2 Chat Interface

A persistent chat interface is available on all screens, enabling conversational interaction with the agents. Users can:
- Ask questions about jobs or their persona
- Update application status via conversation
- Provide attachments (screenshots, emails) for the agent to extract data
- Trigger actions that would otherwise require manual UI interaction

The chat interface serves as the primary interaction method, with traditional UI controls available as a fallback.

### 7.3 Dashboard (Default Landing Page)

The Dashboard is the command center, organized into three tabs:

| Tab | Purpose | Content |
|-----|---------|---------|
| **Opportunities** | Job discovery | High-match jobs feed, sorted by match score (starred jobs at top). Quick actions: Star, Dismiss, Mark Applied |
| **In Progress** | Application tracking | Active applications with status pipeline and next actions |
| **History** | Record keeping | Completed/closed applications with outcomes for retrospective analysis |

**Quick Actions:**
- **Star:** Bookmark a job for easy access. Starred jobs appear at the top of the list.
- **Dismiss:** Archive a job and hide from view. Can be undone. Dismissed jobs are remembered so the Scouter won't resurface them.
- **Mark Applied:** Indicate you've submitted an application externally (can also be done via chat).

**Sorting Options:** Default sort by match score (descending). Additional options: date discovered, company name, starred first.

**Critical Info Panel (Always Visible):**
- Profile completeness indicator
- Active applications count
- Pending reviews count (jobs with drafted materials awaiting user review)
- Recent activity summary

### 7.4 Application Flow

The flow depends on the Auto-Draft setting:

**With Auto-Draft Enabled:**
1. **Discover:** System finds high-match job and auto-generates materials
2. **Review:** User sees match score, redlined resume, and draft cover letter
3. **Edit:** User refines drafts in the collaborative editor (or accepts as-is)
4. **Export:** User downloads final application package (PDF)
5. **Apply:** User submits externally, then marks as "Applied" (via chat or UI)
6. **Track:** Application moves to "In Progress" tab

**With Auto-Draft Disabled:**
1. **Discover:** System finds high-match job (no materials generated yet)
2. **Initiate:** User triggers drafting (via chat: "Draft materials for this job" or UI button)
3. **Review → Track:** Same as above

---

## 8. Document Management

### 8.1 Resume Version Control

The system maintains a complete history of resume versions:

| Concept | Description |
|---------|-------------|
| **Base Resume** | The original uploaded document (PDF/DOCX stored) |
| **Extracted Data** | Structured data parsed from the base resume |
| **Master Version** | The current "canonical" resume content (editable) |
| **Job Variants** | Auto-generated, job-specific versions with redlines applied |

**Version Tracking:**
- Each version has a unique ID, timestamp, and parent reference
- Users can compare versions (diff view)
- Users can promote a variant back to Master if desired

### 8.2 Cover Letter Management

Cover letters follow a similar pattern:

| Concept | Description |
|---------|-------------|
| **Templates** | User-defined base structures (optional) |
| **Generated Drafts** | Job-specific letters created by the Ghostwriter |
| **Final Versions** | User-approved letters linked to specific applications |

### 8.3 Application-Document Linking

Every application record maintains references to:
- The specific resume version used
- The specific cover letter version used
- The job posting snapshot (in case the posting changes/disappears)

This creates full traceability: "For this job, I applied with resume v2.3 and cover letter v1.1 on Jan 15."

---

## 9. Application Lifecycle

### 9.1 Status Pipeline

**User Setting: Auto-Draft Materials** (configured during onboarding, adjustable in settings)

When enabled, the Ghostwriter automatically generates application materials for high-match jobs. When disabled, the user manually initiates drafting.

**Pre-Application Flow (System-Driven):**

| Auto-Draft | Flow |
|------------|------|
| **Enabled** | Discovered → Drafted → Pending Review |
| **Disabled** | Discovered → Pending Review |

**Post-Application Flow (User-Driven):**

```
[Pending Review] → [Applied] → [Interviewing] → [Offer/Rejected/Withdrawn]
```

**Status Definitions:**

| Status | Meaning | Triggered By |
|--------|---------|--------------|
| **Discovered** | Job identified as high match | System (auto) |
| **Drafted** | Application materials generated | System (if auto-draft) or User action |
| **Pending Review** | Ready for user to review and apply | System (auto) |
| **Applied** | User submitted externally | User (via agent or manual) |
| **Interviewing** | In active interview process | User updates status |
| **Offer** | Received job offer | User updates status |
| **Rejected** | Application declined | User updates status |
| **Withdrawn** | User chose not to proceed | User updates status |
| **Dismissed** | User not interested; hidden from view | User action (can be undone) |

### 9.2 Status Transitions

**Agent-Driven (Primary):**

The agent manages status transitions through conversation. Users can provide updates via chat, and the agent will:
- Confirm which job is being updated (fuzzy match + confirmation)
- Extract relevant data from attachments (screenshots, confirmation emails, etc.)
- Update the status and log captured information

**Manual Fallback:**

Users can also update status directly via UI controls on the job card or application detail view.

### 9.3 Application Record

Each application tracks:
- Job posting (snapshot + original URL)
- Resume version used
- Cover letter version used
- Application details (date applied, portal, confirmation number)
- Status history with timestamps
- Notes (interview feedback, follow-up reminders)
- Outcome metadata (if applicable)

Detailed field definitions will be specified in requirements documentation.

### 9.4 Analytics (Future)

The History tab enables retrospective analysis:
- Response rate by resume version
- Success rate by job source
- Time-in-stage metrics
- Common rejection patterns

---

## 10. Roadmap

| Phase | Name | Deliverables |
|-------|------|--------------|
| **Phase 1** | Foundation | Database schema, Claude SDK integration, basic UI shell, Onboarding Agent (persona capture) |
| **Phase 2** | Discovery | Scouter agent (job ingestion), Strategist agent (scoring), Opportunities dashboard |
| **Phase 3** | Application Loop | Ghostwriter agent (resume/cover letter generation), Diff View UI, Application tracking, agent-driven status management |

---

## Appendix: Key Terms

| Term | Definition |
|------|------------|
| **Auto-Draft** | User setting that, when enabled, automatically generates application materials for jobs exceeding the match threshold (default: 90%) |
| **ATS (Applicant Tracking System)** | Software used by employers to filter and manage job applications |
| **Dismiss** | Archive a job and hide from view. Dismissed jobs are remembered so the Scouter won't resurface them. Can be undone. |
| **Full Traceability** | Every application is linked to the exact resume version, cover letter version, and job posting snapshot used — so you always know what you submitted and when |
| **HITL (Human-in-the-Loop)** | Design principle ensuring humans maintain final decision authority over all actions |
| **Match Threshold** | The minimum match score (0-100) required to trigger auto-drafting. User-configurable, default 90%. |
| **No Spam** | Every application is uniquely tailored to the specific job. The system never generates generic, one-size-fits-all materials. |
| **pgvector** | PostgreSQL extension for storing and querying vector embeddings |
| **Redlining** | Process of marking up a document to show proposed changes (borrowed from legal terminology) |
| **Star** | Bookmark a job for easy access. Starred jobs appear at the top of the Opportunities list. |
| **Vector Similarity** | Mathematical technique (cosine similarity) for comparing semantic meaning between texts |

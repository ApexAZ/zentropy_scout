# REQ-019: Onboarding Service Layer Redesign

**Status:** Implemented
**Version:** 1.0
**Supersedes:** REQ-007 §5 (Onboarding Agent), §15.2 (Onboarding Agent Graph)
**PRD Reference:** §4.1 Onboarding
**Last Updated:** 2026-02-27

---

## §1 Overview & Motivation

### 1.1 What This Document Does

This document specifies the redesign of Zentropy Scout's Onboarding from a LangGraph chat-based agent into an HTML form wizard with optional LLM-powered resume parsing. It replaces REQ-007 §5 (Onboarding Agent) and §15.2 (Onboarding Agent Graph) in their entirety.

### 1.2 Why the Redesign Is Needed

The Onboarding Agent is implemented in `onboarding.py` (2,490 lines) as a 13-node LangGraph `StateGraph`. It is the most complete agent in the codebase — and that's exactly what reveals the problem. Code review (2026-02-23) found:

1. **It's a form wizard implemented as a chatbot.** Every step function uses fragile keyword matching on `pending_question` to determine which field the user's response belongs to:
   ```python
   if "name" in pending_question.lower():
       basic_info["full_name"] = user_response
   elif "email" in pending_question.lower():
       basic_info["email"] = user_response
   elif "phone" in pending_question.lower():
       basic_info["phone"] = user_response
   ```
   ~1,600 lines of the 2,490 total are keyword matching state machines.

2. **Zero LLM calls.** No LLM interprets user responses. No adaptive behavior. No reasoning. The "agent" is a deterministic state machine that asks fixed questions in a fixed order.

3. **The frontend already has the wizard.** The frontend (`frontend/src/components/onboarding/`) has a complete 12-step wizard implementation with 43 component files (~15,000 lines): form fields, validation, progress bar, back/skip navigation, checkpoint persistence. The backend "chat-based" onboarding duplicates this as a worse version.

4. **A form wizard is strictly better for structured data collection:**

| Concern | Chat-based | Form wizard |
|---------|------------|-------------|
| Field validation | Fragile keyword matching | Native HTML validation |
| User experience | Type answers in chat box | Labeled fields, dropdowns, sliders |
| Back button | Not supported in graph | Native step navigation |
| Progress feedback | Inferred from conversation | Progress bar with X of N |
| Accessibility | Chat-only interface | Standard form accessibility |
| Maintainability | 2,490 lines of state machines | Simple form components |
| Error recovery | Re-ask the question | Highlight the invalid field |

### 1.3 What Changes

| Aspect | Before | After |
|--------|--------|-------|
| Architecture | LangGraph `StateGraph` with 13 nodes | Form wizard (frontend) + REST endpoints (backend) |
| Data collection | Chat-based keyword matching | HTML form fields with native validation |
| Resume parsing | Not implemented (step exists but no LLM) | `ResumeParsingService` with Gemini 2.5 Flash |
| Voice profile | Conversation transcript analysis (prompt exists, no LLM) | Inferred from resume text + manual form fields |
| Step count | 12 steps (includes `base_resume_setup`) | 11 steps (remove `base_resume_setup` — see §3.2) |
| Backend entry point | `onboarding_graph.ainvoke(state)` | `POST /api/v1/onboarding/steps/{step}` |
| State management | `OnboardingState` TypedDict in LangGraph | Frontend React state + checkpoint API |
| Dependencies | `langgraph` package | `pdfplumber` (new — PDF text extraction) |

### 1.4 What Does NOT Change

- `onboarding_workflow.py` (528L) — Persistence logic for finalizing onboarding. Untouched.
- Frontend wizard components (43 files, ~15,000L) — Already implemented. Minor modifications only.
- Frontend `onboarding-provider.tsx` (439L) — State management and checkpointing. Untouched.
- E2E test structure — Test the same wizard flow with same assertions.

---

## §2 Dependencies & Prerequisites

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-001 Persona Schema v0.8 | Entity definitions | Persona fields, onboarding steps |
| REQ-005 Database Schema v0.10 | Schema | `personas`, `work_history`, `skills`, etc. |
| REQ-006 API Contract v0.8 | Integration | Onboarding endpoints |
| REQ-009 Provider Abstraction v0.3 | Integration | LLM provider for resume parsing |
| REQ-012 Frontend Application v0.1 | Integration | Wizard UI components |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-007 §15.2 | Superseded | This document replaces §15.2 entirely |

### 2.3 Cross-REQ Implementation Order

```
REQ-016 (Scouter) ──┐
                     ├──→ REQ-017 (Strategist) ──→ REQ-018 (Ghostwriter)
REQ-019 (Onboarding)┘
```

**This document (REQ-019) has no dependencies on the other 3 REQs** and can be implemented in parallel with REQ-016. It touches no shared scoring or content generation infrastructure.

### 2.4 New Dependency

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `pdfplumber` | ≥0.11.0 | PDF text extraction for resume parsing | MIT |

**Why `pdfplumber`:** Pure Python, no system dependencies (unlike `poppler`/`pdftotext`). Extracts text with layout preservation. Handles multi-column resumes well. Widely used (10M+ downloads/month). MIT licensed.

---

## §3 Design Decisions

### 3.1 Replacement Architecture: Form Wizard + Resume Parsing Service

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Form wizard (frontend) + REST endpoints (backend) + `ResumeParsingService` | ✅ | The frontend wizard already exists. The backend needs REST endpoints to receive step data and a parsing service for the one real LLM use case (resume upload). Everything else is standard CRUD. |
| Keep chat-based but fix keyword matching | — | Fundamental UX problem. Chat is the wrong interface for collecting 50+ structured fields. Even with perfect NLP, users would prefer labeled form fields for data like phone numbers, salary ranges, and proficiency ratings. |
| Keep LangGraph but simplify | — | 2,490 lines of code with zero LLM calls. LangGraph adds state schema overhead, checkpoint infrastructure, and routing functions for a deterministic sequence. |

### 3.2 Remove `base_resume_setup` Step

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Remove `base_resume_setup` step (12 → 11 steps) | ✅ | This step asks users to select which work history entries and skills to include on their first resume. At onboarding time, users have just entered all their data — they have no context to make these selections meaningfully. Better to auto-create a BaseResume using all entered data and let users edit later from the Resume Management page (REQ-012 §9). |
| Keep `base_resume_setup` | — | Requires users to make decisions they don't have context for yet. Adds friction to a flow that should be "get your data in, see results fast." |

**Migration:** The `base-resume-setup-step.tsx` component (599L) is retained for potential reuse in Resume Management. The onboarding wizard simply no longer routes to it.

### 3.3 Resume Parsing: Gemini 2.5 Flash (Platform-Funded)

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Gemini 2.5 Flash for resume parsing | ✅ | Cost: ~$0.00135 per resume. Platform funds this as customer acquisition cost — first impressions matter, and a well-parsed resume accelerates the entire onboarding experience. Not Flash-Lite — reliability on first impression matters more than the fraction-of-a-cent cost difference. |
| Claude Haiku | — | Higher cost per call. Gemini Flash is sufficient for structured extraction. |
| No LLM (regex extraction only) | — | Resume formats are too varied for regex. Names, dates, skills, and bullets appear in hundreds of layouts. LLM handles this naturally. |

**Cost projection:** $50 Gemini credit covers ~37,000 resume uploads.

### 3.4 Voice Profile: Inferred from Resume + Manual Form

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Infer from resume text + manual form fields | ✅ | The resume parse LLM call returns structured persona data AND voice profile suggestions in one call. What's inferable: writing style (results-focused vs narrative), vocabulary level (technical/accessible/business), personality markers (collaborative vs independent). What's NOT inferable: tone preference (offer presets), things to avoid (user fills manually). If inference confidence < 0.7, leave fields empty for manual entry. |
| Derive from chat conversation transcript | — | Current approach (prompt exists at line ~2200 in `onboarding.py`). Requires chat-based onboarding, which this redesign removes. |
| Manual only (no inference) | — | Misses the opportunity to leverage resume text. Users often can't articulate their writing style — showing them an inference they can edit is better than a blank form. |

---

## §4 Current State Inventory

### 4.1 Files to Modify or Delete

| File | Lines | Role | Action |
|------|-------|------|--------|
| `backend/app/agents/onboarding.py` | 2,490 | LangGraph graph: 13 nodes, keyword matching, state machines | **MODIFY** (keep ~450L of post-onboarding utilities, delete ~2,040L) |
| `backend/app/agents/state.py` | 404 | Contains `OnboardingState` TypedDict (~30 lines) | **MODIFY** (remove `OnboardingState`) |
| `backend/app/agents/__init__.py` | 196 | Re-exports onboarding graph | **MODIFY** (remove onboarding graph exports) |

### 4.2 What to Keep from `onboarding.py` (~450 lines)

These functions support post-onboarding persona updates (when users edit their profile after initial onboarding). They are framework-independent and work with the existing API:

| Function/Constant | Lines (approx.) | Purpose |
|-------------------|-----------------|---------|
| `UPDATE_REQUEST_PATTERNS` | ~30 | Regex patterns for detecting "Update my skills" type requests |
| `SECTION_DETECTION_PATTERNS` | ~40 | Maps user messages to persona sections |
| `is_update_request()` | ~10 | Checks if message is a post-onboarding update |
| `is_post_onboarding_update()` | ~10 | Confirms onboarding is complete + message is update |
| `detect_update_section()` | ~15 | Identifies which section to update |
| `SECTIONS_REQUIRING_RESCORE` | ~10 | Sections that trigger embedding regeneration |
| `SECTION_AFFECTED_EMBEDDINGS` | ~10 | Maps sections to embedding types |
| `get_affected_embeddings()` | ~10 | Returns embedding types for a section |
| `get_update_completion_message()` | ~20 | Custom completion message per section |
| `create_update_state()` | ~20 | State factory for partial re-onboarding |
| `format_gathered_data_summary()` | ~30 | Formats collected data for display |
| `_format_basic_info()` | ~15 | Helper formatter |
| `_format_work_history()` | ~20 | Helper formatter |
| `_format_skills()` | ~15 | Helper formatter |
| `_format_stories()` | ~15 | Helper formatter |
| `_format_skipped_sections()` | ~10 | Helper formatter |
| Prompt templates (voice profile, stories) | ~100 | Used by post-onboarding voice profile derivation |

### 4.3 What to Delete from `onboarding.py` (~2,040 lines)

| Category | Lines (approx.) | What |
|----------|-----------------|------|
| Step handler functions (12) | ~1,200 | `gather_basic_info()`, `gather_work_history()`, `gather_education()`, `gather_skills()`, `gather_certifications()`, `gather_stories()`, `gather_non_negotiables()`, `gather_growth_targets()`, `derive_voice_profile()`, `review_persona()`, `setup_base_resume()`, `complete_onboarding()` |
| Response parsing helpers (~25) | ~400 | `_handle_work_history_response()`, `_handle_education_response()`, `_handle_skills_response()`, `_handle_certifications_response()`, `_handle_stories_response()`, `_handle_non_negotiables_response()`, `_handle_voice_profile_response()`, etc. |
| Navigation functions | ~100 | `get_next_step()`, `is_step_optional()`, `handle_skip()`, `check_step_complete()`, `wait_for_input()` |
| Graph construction | ~100 | `create_onboarding_graph()`, `get_onboarding_graph()` |
| System prompt templates | ~100 | `SYSTEM_PROMPT_TEMPLATE`, step-specific prompts (for chat interview — not reusable in form wizard) |
| Trigger functions | ~50 | `should_start_onboarding()`, `check_resume_upload()` |
| Prompt builder functions | ~90 | `get_system_prompt()`, `get_work_history_prompt()`, `get_achievement_story_prompt()`, `get_transition_prompt()` |

### 4.4 Files That Stay Unchanged

| File | Lines | Role | Why Unchanged |
|------|-------|------|---------------|
| `backend/app/services/onboarding_workflow.py` | 528 | Persistence logic (`finalize_onboarding()`) | Framework-independent. Called by API endpoint instead of graph node. |
| `frontend/src/lib/onboarding-provider.tsx` | 439 | React state management + checkpointing | Already manages wizard state independently of backend architecture. |
| `frontend/src/components/onboarding/onboarding-shell.tsx` | 138 | Layout wrapper (progress bar, nav) | Already a form wizard shell. |
| `frontend/src/components/onboarding/onboarding-steps.ts` | 89 | Step definitions | Update step count from 12 to 11. |
| Frontend step components (12 + 17 supporting) | ~15,000 | Form UIs | Minor modifications only (see §13). |

---

## §5 Deletion Plan

### 5.1 Code to Delete from `onboarding.py`

~2,040 lines removed. The file shrinks from 2,490 to ~450 lines of post-onboarding update utilities.

**Deleted categories:**
- All 12 step handler functions
- All ~25 response parsing helpers
- Navigation functions (replaced by frontend wizard navigation)
- Graph construction functions
- System prompt templates for chat interview
- Trigger functions
- Chat-specific prompt builders

### 5.2 Code to Remove from Other Files

| File | What to Remove | Reason |
|------|---------------|--------|
| `backend/app/agents/state.py` | `OnboardingState` TypedDict (~30 lines) | Replaced by frontend React state + API request bodies |
| `backend/app/agents/__init__.py` | Onboarding graph imports/re-exports | No longer exists |

### 5.3 Prompt Templates

| Prompt | Action | Reason |
|--------|--------|--------|
| `SYSTEM_PROMPT_TEMPLATE` (interviewer persona) | **DELETE** | Chat-based interview is removed. Form wizard doesn't need an interviewer persona. |
| `ACHIEVEMENT_STORY_PROMPT` (STAR format) | **KEEP** | Used by post-onboarding story expansion and potentially by resume parsing service. |
| `VOICE_PROFILE_DERIVATION_PROMPT` | **KEEP** | Used by `ResumeParsingService` and post-onboarding voice profile updates. |
| `WORK_HISTORY_EXPANSION_PROMPT` | **KEEP** | Used by post-onboarding work history updates. |
| Step-specific chat prompts | **DELETE** | Not needed for form wizard. |
| `TRANSITION_PROMPTS` | **DELETE** | Between-step transitions handled by wizard UI. |

---

## §6 New Architecture

### 6.1 Service Overview

```
Frontend Wizard (existing)
  Step 1: Resume Upload → POST /api/v1/onboarding/resume-parse
  Steps 2–10: Form data → POST /api/v1/onboarding/steps/{step}
  Step 11: Review → POST /api/v1/onboarding/complete
      │
      ├── ResumeParsingService (new)
      │     pdfplumber → text extraction
      │     Gemini 2.5 Flash → structured parsing + voice inference
      │
      └── OnboardingWorkflowService (existing, unchanged)
            finalize_onboarding() → persist all data
```

### 6.2 `ResumeParsingService` (`backend/app/services/resume_parsing_service.py`)

**Responsibility:** Extract structured persona data from a PDF resume using LLM.

```python
BILLING_MODE = "platform"  # Never charged to user credits

class ResumeParsingService:
    """Parses uploaded resumes into structured persona data."""

    async def parse_resume(
        self,
        pdf_content: bytes,
        provider: LLMProvider,
    ) -> ResumeParseResult:
        """Parse a PDF resume into structured persona data.

        Pipeline:
        1. Extract text from PDF using pdfplumber
        2. Send text to Gemini 2.5 Flash with structured extraction prompt
        3. Parse LLM response into ResumeParseResult

        Returns:
            ResumeParseResult with work_history, education, skills,
            certifications, and voice_suggestions.
        """
```

**LLM output schema (single call, two outputs):**
```json
{
  "basic_info": {
    "full_name": "...",
    "email": "...",
    "phone": "...",
    "location": "...",
    "linkedin_url": "...",
    "portfolio_url": "..."
  },
  "work_history": [
    {
      "job_title": "...",
      "company_name": "...",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM or null",
      "is_current": true,
      "bullets": ["..."]
    }
  ],
  "education": [
    {
      "institution": "...",
      "degree": "...",
      "field_of_study": "...",
      "graduation_date": "YYYY-MM"
    }
  ],
  "skills": [
    {
      "name": "...",
      "type": "Hard or Soft",
      "proficiency": "Learning | Familiar | Proficient | Expert"
    }
  ],
  "certifications": [
    {
      "name": "...",
      "issuer": "...",
      "date_obtained": "YYYY-MM"
    }
  ],
  "voice_suggestions": {
    "writing_style": "results-focused | narrative | technical | concise",
    "vocabulary_level": "technical | accessible | business",
    "personality_markers": "...",
    "confidence": 0.85
  }
}
```

**Voice profile inference rules:**
- If `confidence >= 0.7`: pre-populate voice profile form fields with suggestions
- If `confidence < 0.7`: leave voice profile fields empty for manual entry
- User always sees and can edit the inferred values — inference is a starting point, not final

### 6.3 Backend API Endpoints (`backend/app/api/v1/onboarding.py`)

The existing onboarding endpoints are updated to support the form wizard:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/onboarding/resume-parse` | POST | Upload PDF → return parsed data (pre-populate steps 2–6 + voice) |
| `/api/v1/onboarding/checkpoint` | GET | Load saved checkpoint (current step + partial data) |
| `/api/v1/onboarding/checkpoint` | PUT | Save checkpoint (step number + partial data) |
| `/api/v1/onboarding/complete` | POST | Finalize onboarding → calls `onboarding_workflow.finalize_onboarding()` |

**Note:** Individual step data is saved via existing persona/work-history/skills endpoints. The checkpoint endpoint only tracks which step the user is on and any partial form data not yet submitted.

---

## §7 Behavioral Specification

### 7.1 11-Step Wizard Flow

| Step | Name | Required | Pre-populated from Resume | Fields |
|------|------|----------|--------------------------|--------|
| 1 | Resume Upload | Optional | N/A | PDF file drop zone |
| 2 | Basic Info | Yes | Yes | name, email, phone, location, linkedin, portfolio |
| 3 | Work History | Yes (min 1 entry) | Yes | job entries with bullets (CRUD) |
| 4 | Education | Optional | Yes | education entries (CRUD) |
| 5 | Skills | Yes (min 1 skill) | Yes | skills with proficiency + type (CRUD) |
| 6 | Certifications | Optional | Yes | certification entries (CRUD) |
| 7 | Achievement Stories | Yes (min 1, encouraged 3–5) | No | STAR format stories (CRUD) |
| 8 | Non-Negotiables | Yes | No | remote pref, salary floor, visa, exclusions |
| 9 | Growth Targets | Yes | No | target roles, target skills |
| 10 | Voice Profile | Yes | Yes (from resume parse) | tone, vocabulary, personality, things to avoid |
| 11 | Review | Yes | N/A | Read-only summary with edit links, submit button |

### 7.2 Resume Upload Flow (Step 1)

```
User drops/selects PDF
    │
    ▼
Frontend sends PDF to POST /api/v1/onboarding/resume-parse
    │
    ▼
ResumeParsingService:
  1. pdfplumber extracts text from PDF
  2. Text sent to Gemini 2.5 Flash with extraction prompt
  3. LLM returns structured JSON
  4. Parse into ResumeParseResult
    │
    ▼
Frontend receives parsed data:
  - Pre-populates steps 2–6 form fields
  - Pre-populates step 10 (voice profile) if confidence ≥ 0.7
  - User reviews and edits before advancing
```

**Error handling:**
- PDF too large (>10MB) → reject before upload
- PDF text extraction fails → message: "Couldn't read this PDF. You can skip this step and enter your info manually."
- LLM extraction fails → same message (fail gracefully to manual entry)

### 7.3 Checkpoint Behavior

| Scenario | Behavior |
|----------|----------|
| User exits mid-flow | Frontend saves checkpoint (step number + partial data) via `PUT /checkpoint` |
| User returns | Frontend loads checkpoint via `GET /checkpoint`, resumes at saved step |
| Checkpoint expired (>24h) | Frontend shows "Welcome back" prompt, option to resume or start fresh |
| User wants to restart | Reset checkpoint, start at step 1 |

### 7.4 Post-Onboarding Updates (unchanged)

User can update persona anytime via:
- Direct editing on persona management page (REQ-012 §7)
- Chat commands like "Update my skills" (uses `UPDATE_REQUEST_PATTERNS` from `onboarding.py`)

Both trigger embedding regeneration and job rescoring as specified in REQ-007 §5.5 (retained code).

---

## §8 Prompt Specifications

### 8.1 Resume Parsing Prompt (new)

**System prompt:**
```
You are an expert resume parser. Extract structured data from the resume text below.

Rules:
1. Extract ALL work history entries, even if formatting is inconsistent
2. For each skill, infer proficiency from context (years of experience, role seniority)
3. Normalize date formats to YYYY-MM
4. If a field is ambiguous or missing, use null rather than guessing
5. For voice_suggestions, analyze the writing style:
   - writing_style: How are accomplishments presented? (results-focused, narrative, technical, concise)
   - vocabulary_level: What level of language is used? (technical, accessible, business)
   - personality_markers: What traits come through? (e.g., "collaborative", "independent contributor")
   - confidence: How confident are you in these assessments? (0.0-1.0)

Output ONLY valid JSON matching the schema. No markdown, no explanation.
```

**User prompt:**
```
Resume text:
{extracted_text}

Parse this resume into structured JSON with these keys:
basic_info, work_history, education, skills, certifications, voice_suggestions
```

**Model:** Gemini 2.5 Flash (via provider abstraction layer)
**Input:** Full text extracted by pdfplumber (no truncation — resumes are typically 1–3 pages)
**Input sanitization:** `sanitize_llm_input()` from `llm_sanitization.py`

### 8.2 Retained Prompts (from `onboarding.py`)

| Prompt | Location | Used By |
|--------|----------|---------|
| `VOICE_PROFILE_DERIVATION_PROMPT` | `onboarding.py` (kept section) | Post-onboarding voice profile updates via chat |
| `ACHIEVEMENT_STORY_PROMPT` | `onboarding.py` (kept section) | Post-onboarding story expansion |
| `WORK_HISTORY_EXPANSION_PROMPT` | `onboarding.py` (kept section) | Post-onboarding work history updates |

---

## §9 Configuration & Environment

### 9.1 New Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `RESUME_PARSE_MAX_SIZE_MB` | 10 | Maximum PDF upload size |

### 9.2 Existing Configuration (unchanged)

| Variable | Used For |
|----------|----------|
| `LLM_PROVIDER` | Resume parsing model selection |

---

## §10 Migration Path

### 10.1 Implementation Order

| Step | Action | Depends On |
|------|--------|------------|
| 1 | Add `pdfplumber` dependency to `pyproject.toml` | Nothing |
| 2 | Create `ResumeParsingService` | Step 1 |
| 3 | Create/update `POST /api/v1/onboarding/resume-parse` endpoint | Step 2 |
| 4 | Update `onboarding-steps.ts` to 11 steps (remove `base_resume_setup`) | Nothing |
| 5 | Update `resume-upload-step.tsx` to call new parsing endpoint | Step 3 |
| 6 | Delete ~2,040 lines from `onboarding.py` (keep ~450 lines of post-onboarding utilities) | Nothing |
| 7 | Remove `OnboardingState` from `state.py` | Step 6 |
| 8 | Update `__init__.py` exports | Step 6 |
| 9 | Write new unit tests for `ResumeParsingService` | Step 2 |
| 10 | Update E2E tests for 11-step flow | Steps 4–5 |

### 10.2 Rollback Strategy

- `pdfplumber` is a new dependency but has no side effects if unused
- `onboarding.py` changes are code deletion — git revert restores
- Frontend step count change is a single constant
- No database schema changes

---

## §11 Test Impact Analysis

### 11.1 Backend Tests

| Test File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `tests/unit/test_onboarding_agent.py` | ~164 (class-based) | **DELETE** (mostly) | Tests keyword matching state machines, graph construction, step handler functions — all deleted code. Keep tests for post-onboarding utility functions that survive. |
| `tests/unit/test_onboarding_workflow.py` | ~25 (class-based) | **KEEP** | Tests `finalize_onboarding()` persistence logic. Framework-independent. |

### 11.2 New Tests to Create

| Test File | Est. Tests | Coverage |
|-----------|-----------|----------|
| `tests/unit/test_resume_parsing_service.py` | ~20 | PDF text extraction, LLM mock, structured output parsing, voice confidence threshold, error handling (bad PDF, LLM failure), sanitization |
| `tests/unit/test_onboarding_utilities.py` | ~15 | Post-onboarding update detection, section detection, rescore triggering, embedding mapping — tests for the ~450 lines retained from `onboarding.py` |

### 11.3 Test Migration Notes

- Step handler tests → **deleted** (no step handlers)
- Graph construction tests → **deleted** (no graph)
- Keyword matching tests → **deleted** (no keyword matching)
- Post-onboarding utility tests → **migrated** to `test_onboarding_utilities.py`
- `finalize_onboarding()` tests → **kept** as-is in `test_onboarding_workflow.py`

---

## §12 E2E Test Impact

| Spec File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `frontend/tests/e2e/onboarding.spec.ts` | 18 | **MODIFY** | Update step count from 12 to 11 (remove `base_resume_setup`). Update resume upload test to verify parsing endpoint call. Core wizard flow tests remain valid. |

### 12.1 Specific E2E Changes

1. **Step count assertions:** Update "Step X of 12" → "Step X of 11"
2. **Resume upload test:** Add assertion that `POST /onboarding/resume-parse` is called on file drop
3. **Step 12 tests** (base resume setup): **DELETE** — step removed from wizard
4. **Happy path test:** Update to skip from step 10 (voice profile) → step 11 (review) → complete
5. **Progress bar assertions:** Update percentage calculations for 11 steps

---

## §13 Frontend Impact

### 13.1 Files to Modify

| File | Change | Reason |
|------|--------|--------|
| `frontend/src/components/onboarding/onboarding-steps.ts` | Change `TOTAL_STEPS` from 12 to 11, remove step 12 (`base-resume-setup`) definition | Step removed |
| `frontend/src/app/onboarding/page.tsx` | Update `StepRouter` case count (remove case 12) | Step removed |
| `frontend/src/components/onboarding/steps/resume-upload-step.tsx` | Call new `POST /onboarding/resume-parse` endpoint, populate later step forms with parsed data | Real resume parsing |
| `frontend/src/lib/onboarding-provider.tsx` | Adjust step validation and navigation for 11 steps | Step removed |

### 13.2 Frontend Vitest Test Files to Update

| File | Change | Reason |
|------|--------|--------|
| `frontend/src/components/onboarding/onboarding-steps.test.ts` | Update step count assertions from 12 to 11 | Step removed |
| `frontend/src/components/onboarding/onboarding-shell.test.tsx` | Update progress bar calculations if hardcoded | Step removed |
| `frontend/src/lib/onboarding-provider.test.tsx` | Update step navigation and validation tests | Step removed |

### 13.3 Files Unchanged

All other step components (basic-info, work-history, education, skills, certifications, stories, non-negotiables, growth-targets, voice-profile, review) remain unchanged. They already render form fields and submit via the existing API.

### 13.4 Files Retained but Unused

| File | Status | Reason |
|------|--------|--------|
| `steps/base-resume-setup-step.tsx` (599L) | **Retain** | Potentially reusable in Resume Management page. Not worth deleting if it may be needed later. Remove from wizard routing but keep the file. |

---

## §14 Open Questions & Future Considerations

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Should `base_resume_setup` be auto-created on onboarding complete? | **Yes** | When `finalize_onboarding()` runs, auto-create one BaseResume using all entered work history and skills. No user selection step needed. |
| 2 | Should resume parsing support DOCX? | Deferred | `pdfplumber` is PDF-only. DOCX support would require `python-docx`. Most resumes are PDFs. Add DOCX support when user feedback demands it. |
| 3 | What if the resume parse takes >10 seconds? | Handle with loading state | Frontend shows a progress indicator ("Analyzing your resume..."). Gemini Flash typically responds in 3–5 seconds for 1–3 page documents. Set 30-second timeout on the endpoint. |
| 4 | Should the post-onboarding utilities (~450L) be extracted to a separate file? | Deferred | They could move to `backend/app/services/onboarding_updates.py`. Low priority — they work fine in `onboarding.py`. |

---

## §15 Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-23 | 0.2 | Audit fixes: added cross-REQ implementation order to §2, added frontend Vitest test files to §13.2, renumbered §13.3→§13.4. |
| 2026-02-23 | 0.1 | Initial draft. Specifies replacement of LangGraph Onboarding Agent with form wizard + ResumeParsingService. |

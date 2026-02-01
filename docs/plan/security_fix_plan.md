# Security Findings Remediation Plan

**Created:** 2026-02-01
**Status:** 🟡 Planning
**Total Findings:** 11 actionable (1 dismissed as working correctly)

---

## Workflow Per Finding (FOLLOW THIS EXACTLY)

For each finding marked ⬜, execute these steps in order:

### Step 1: REQ-READER
```
Use the req-reader subagent to cross-reference requirements.
Prompt: "Look up [REQ-XXX §X.X] to understand the expected behavior for [description]. What does the spec say?"
```

### Step 2: CODE-REVIEWER Consensus
```
Use the code-reviewer subagent to get consensus on the fix approach.
Prompt: "Review this security finding and proposed fix. Do you agree with the approach?

FINDING: [copy the Problem section from this plan]
PROPOSED FIX: [copy the Fix section from this plan]
FILE: [file path]

Please confirm the fix is correct and follows project conventions."
```

### Step 3: IMPLEMENT Fix
```
Make the code change as described in the Fix section.
Follow TDD if adding new behavior (write test first).
```

### Step 4: VALIDATE
```
Run both reviewers in PARALLEL to validate:

1. code-reviewer: "Validate this security fix was implemented correctly.
   ISSUE: [copy Problem section]
   FIX APPLIED: [describe what was changed]
   FILE: [file path and line numbers]"

2. security-reviewer: "Validate this security fix addresses the vulnerability.
   VULNERABILITY: [copy Problem section]
   MITIGATION: [describe what was changed]
   FILE: [file path]"
```

### Step 5: MARK COMPLETE
```
Update this plan:
- Change ⬜ to ✅ in the Progress Tracker
- Add completion timestamp
- Commit the fix with message: "fix(security): [F-XX] [short description]"
```

### Step 6: COMPACT CHECK
```
After completing a finding, ask user: "Continue to next finding, or compact first?"
If compact: Update this file, then compact. After compact, re-read this file.
```

---

## Compact Recovery Instructions

**After ANY context compact, do this FIRST:**

1. Read this file: `/home/brianhusk/repos/zentropy_scout/docs/plan/security_fix_plan.md`
2. Check the Progress Tracker table at the bottom
3. Find the first ⬜ (Not Started) or 🟡 (In Progress) finding
4. Read that finding's section for full context
5. Continue from the appropriate workflow step

---

## Priority 1: High Priority Fixes

### F-01: Header Injection in base_resumes.py Download
- **Status:** ✅ Complete (2026-02-01)
- **Severity:** Medium
- **File:** `backend/app/api/v1/base_resumes.py:101-104`
- **Requirements:** REQ-006 §2.7 (File downloads), §5.2 (Base resumes)
- **Validated by:** code-reviewer ✅, security-reviewer ✅

**Problem:**
```python
# CURRENT (VULNERABLE) - line 101:
filename = f"{base_resume.name.replace(' ', '_')}.pdf"
headers={"Content-Disposition": f'attachment; filename="{filename}"'}
```
The `base_resume.name` is user-controlled. Only spaces are replaced. A malicious name like `resume\r\nX-Injected: header` could inject HTTP headers.

**Correct Pattern (from files.py:219-225):**
```python
from app.core.file_validation import sanitize_filename_for_header
safe_filename = sanitize_filename_for_header(resume_file.file_name)
headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
```

**Fix:**
1. Add import: `from app.core.file_validation import sanitize_filename_for_header`
2. Replace lines 100-101 with:
   ```python
   safe_filename = sanitize_filename_for_header(f"{base_resume.name}.pdf")
   ```
3. Update line 106 to use `safe_filename`

**Validation:**
- Verify import added
- Verify `sanitize_filename_for_header()` is called
- Run: `pytest tests/unit/api/v1/test_base_resumes.py -v` (or related tests)

---

### F-02: CORS Allows All Headers
- **Status:** ⬜ Not Started
- **Severity:** Medium
- **File:** `backend/app/main.py:168-174`
- **Requirements:** REQ-006 (CORS not explicitly specified - gap in requirements)

**Problem:**
```python
# Line 173:
allow_headers=["*"],  # TOO PERMISSIVE with allow_credentials=True
```

**Fix:**
Replace line 173 with explicit list:
```python
allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
```

**Validation:**
- Verify only specific headers are allowed
- Frontend should still work (uses Content-Type)
- Manual test: OPTIONS request should only allow listed headers

---

### F-03: No max_length on Chat Message Content
- **Status:** ⬜ Not Started
- **Severity:** Medium
- **File:** `backend/app/schemas/chat.py:35`
- **Requirements:** REQ-006 §5.2 (Chat endpoints)

**Problem:**
```python
# Line 35:
content: str = Field(..., description="User message content")
# No max_length - could send huge messages to LLM causing cost explosion
```

**Fix:**
```python
content: str = Field(..., max_length=50000, description="User message content")
```

**Rationale:** 50k chars is ~12k tokens, well under Claude's context limit but prevents abuse.

**Validation:**
- Verify max_length added
- Test that messages over 50k chars are rejected with 422 validation error
- Run: `pytest tests/unit/schemas/test_chat.py -v` (if exists)

---

### F-04: Schema Mismatch in Extracted Skills
- **Status:** ⬜ Not Started
- **Severity:** Low (but causes data loss)
- **File:** `backend/app/api/v1/job_postings.py:190-196`
- **Requirements:** REQ-007 §6.4 (Skills extraction)

**Problem:**
```python
# job_postings.py lines 190-196 uses WRONG field name:
extracted_skills=[
    {
        "skill_name": s.get("skill_name", ""),
        "importance_level": s.get("importance_level", "Preferred"),  # WRONG!
    }
    for s in extracted.get("extracted_skills", [])
],
```

The LLM extraction (job_extraction.py) returns `is_required: bool`, but this code looks for `importance_level` which doesn't exist, causing skill data to be lost.

**Correct Schema (from ingest.py ExtractedSkillPreview):**
```python
skill_name: str
skill_type: str = "Hard"
is_required: bool = True
years_requested: int | None = None
```

**Fix:**
Replace lines 190-196 with:
```python
extracted_skills=[
    {
        "skill_name": s.get("skill_name", ""),
        "skill_type": s.get("skill_type", "Hard"),
        "is_required": s.get("is_required", True),
        "years_requested": s.get("years_requested"),
    }
    for s in extracted.get("extracted_skills", [])
],
```

**Validation:**
- Field names match between extraction, preview, and confirm flows
- Run: `pytest tests/unit/services/test_job_extraction.py -v`
- Run: `pytest tests/unit/api/v1/test_job_postings.py -v`

---

## Priority 2: Medium Priority Fixes

### F-05: No max_length on Job Posting raw_text
- **Status:** ⬜ Not Started
- **Severity:** Medium (mitigated by LLM truncation at 15k)
- **File:** `backend/app/schemas/ingest.py:69-72`
- **Requirements:** REQ-006 §5.6 (Chrome extension ingest)

**Problem:**
```python
# Lines 69-72:
raw_text: str = Field(
    ...,
    min_length=1,
    description="Full job posting text",
)
# No max_length - storage/memory unbounded
```

**Mitigating Factor:** `job_extraction.py:39` truncates to 15k chars before LLM call.

**Fix:**
```python
raw_text: str = Field(
    ...,
    min_length=1,
    max_length=100000,  # 100k chars reasonable for any job posting
    description="Full job posting text",
)
```

**Validation:**
- Verify max_length added
- Test that text over 100k chars is rejected with 422
- Run: `pytest tests/unit/schemas/test_ingest.py -v` (if exists)

---

### F-06: Missing Content-Security-Policy Header
- **Status:** ⬜ Not Started
- **Severity:** Low
- **File:** `backend/app/main.py:28-64` (SecurityHeadersMiddleware)
- **Requirements:** Not specified (security best practice)

**Current State:** Code has comment at line 38 acknowledging this: "CSP and HSTS should be added when HTTPS is configured for production."

**Fix:**
Add after line 62 in `SecurityHeadersMiddleware.dispatch()`:
```python
# Content Security Policy for API-only backend
response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
```

**Validation:**
- Verify CSP header is present in all API responses
- Run: `curl -I http://localhost:8000/health` and check headers

---

### F-07: Missing HSTS Header
- **Status:** ⬜ Not Started
- **Severity:** Low
- **File:** `backend/app/main.py:28-64` (SecurityHeadersMiddleware)
- **Requirements:** Not specified (security best practice for HTTPS)

**Note:** Only applies when HTTPS is configured. For local-first MVP over HTTP, this would break things.

**Fix:**
Add after CSP header, conditional on production:
```python
# HSTS only in production (assumes HTTPS via reverse proxy)
if settings.environment == "production":
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
```

Requires adding import: `from app.core.config import settings`

**Validation:**
- Verify header is present when ENVIRONMENT=production
- Verify header is NOT present when ENVIRONMENT=development

---

### F-08: IDOR Risk in Stub Endpoints
- **Status:** ⬜ Not Started
- **Severity:** Low (endpoints are stubs returning empty data)
- **Files:** Multiple files in `backend/app/api/v1/`
- **Requirements:** REQ-006 §6.2 (Authorization)

**Problem:** Many endpoints are stubs that don't verify user ownership. When implemented, they need ownership checks.

**Affected Files:**
- `personas.py`: get_persona, update_persona, delete_persona
- `job_postings.py`: get_job_posting, update_job_posting, delete_job_posting
- `applications.py`: all endpoints
- `cover_letters.py`: all endpoints
- `job_variants.py`: all endpoints
- `user_source_preferences.py`: get, update, delete

**Correct Pattern (from files.py):**
```python
result = await db.execute(
    select(Resource)
    .join(Persona, Resource.persona_id == Persona.id)
    .where(Resource.id == resource_id, Persona.user_id == user_id)
)
resource = result.scalar_one_or_none()
if not resource:
    raise NotFoundError("Resource", str(resource_id))
```

**Fix:** Add a TODO comment at the top of each affected file:
```python
# SECURITY TODO: When implementing stub endpoints, add ownership verification
# using the JOIN pattern from files.py - see docs/plan/security_fix_plan.md F-08
```

**Validation:**
- Verify TODO comments added
- No functional changes needed until stubs are implemented

---

## Priority 3: Acknowledged (No Fix Needed)

### F-09: SQL Echo in Development
- **Status:** ✅ Acknowledged
- **Severity:** Low
- **File:** `backend/app/core/database.py:19`
- **Decision:** Acceptable for development. No fix needed.

---

### F-10: In-Memory Token Store Cleanup
- **Status:** ✅ Acknowledged
- **Severity:** Low
- **File:** `backend/app/services/ingest_token_store.py`
- **Decision:** Already cleans on access (line 119-121). Documented as intentional for MVP. No fix needed now.

---

### F-11: Auth Model for MVP
- **Status:** ✅ Acknowledged
- **Severity:** Medium (by design)
- **File:** `backend/app/api/deps.py`, `backend/app/core/config.py`
- **Decision:** Working as designed per REQ-006 §6.1. This is intentional for local-first MVP.

---

## Dismissed Finding

### F-XX: extracted_skills Modifiable in Ingest Confirm
- **Status:** ❌ Dismissed
- **Reason:** This is correct behavior. Users should be able to correct LLM extraction errors before confirming. The whitelist (`ALLOWED_INGEST_MODIFICATIONS` in job_postings.py:52-63) properly prevents modification of sensitive fields like `id`, `persona_id`, etc.

---

## Progress Tracker

| ID | Finding | Severity | Status | Validated | Committed |
|----|---------|----------|--------|-----------|-----------|
| F-01 | Header injection in base_resumes.py | Medium | ✅ | ✅ | ✅ |
| F-02 | CORS allows all headers | Medium | ⬜ | ⬜ | ⬜ |
| F-03 | No max_length on chat content | Medium | ⬜ | ⬜ | ⬜ |
| F-04 | Schema mismatch (skills) | Low | ⬜ | ⬜ | ⬜ |
| F-05 | No max_length on raw_text | Medium | ⬜ | ⬜ | ⬜ |
| F-06 | Missing CSP header | Low | ⬜ | ⬜ | ⬜ |
| F-07 | Missing HSTS header | Low | ⬜ | ⬜ | ⬜ |
| F-08 | IDOR in stub endpoints | Low | ⬜ | ⬜ | ⬜ |
| F-09 | SQL echo in dev | Low | ✅ Ack | N/A | N/A |
| F-10 | Token store cleanup | Low | ✅ Ack | N/A | N/A |
| F-11 | Auth model for MVP | Medium | ✅ Ack | N/A | N/A |

**Legend:** ⬜ Not Started | 🟡 In Progress | ✅ Complete | ❌ Dismissed | Ack = Acknowledged

---

## Commit Message Format

For each fix, use conventional commit format:
```
fix(security): [F-XX] short description

- What was the vulnerability
- What was changed to fix it
- Reference to security plan
```

Example:
```
fix(security): [F-01] sanitize filename in base resume download

- base_resume.name was used directly in Content-Disposition header
- Added sanitize_filename_for_header() to prevent header injection
- See docs/plan/security_fix_plan.md F-01
```

---

*Last updated: 2026-02-01 (F-01 complete)*

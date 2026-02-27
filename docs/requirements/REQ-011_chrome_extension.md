# REQ-011: Chrome Extension

**Status:** Postponed
**Version:** 0.1
**PRD Reference:** §4.2 Scouter (Manual Job Submission)
**Last Updated:** 2026-02-27

---

## 1. Overview

This document specifies the Zentropy Scout Chrome Extension: a browser companion that allows users to capture job postings from any website and send them to the Zentropy Scout backend for parsing, scoring, and tracking.

**Key Principle:** The extension is a thin client. It captures raw content and delegates all parsing, skill extraction, and scoring to the backend. This keeps the extension simple, updatable, and secure.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| Job posting capture from any website | Automated job board scraping |
| Raw text + URL submission to backend | Client-side skill extraction |
| Preview display before saving | Full application tracking UI |
| Quick-save and edit workflow | Resume generation |
| Status badges for visited job URLs | Chat agent interface |
| Authentication with local backend | Multi-user/hosted auth (future) |

### 1.2 User Value

| Pain Point | Extension Solution |
|------------|-------------------|
| "I found a job on a niche site not in any aggregator" | Capture from ANY website |
| "Copy-pasting job descriptions is tedious" | One-click capture |
| "I forget which jobs I've already looked at" | URL badges show saved status |
| "I want to quickly save now, review later" | Quick-save with minimal friction |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-003 Job Posting Schema v0.4 | Data model | JobPosting fields, status enum |
| REQ-006 API Contract v0.7 | Integration | `POST /job-postings/ingest` endpoint |
| REQ-007 Agent Behavior v0.4 | Integration | Scouter extraction logic |
| REQ-008 Scoring Algorithm v0.2 | Integration | Strategist scoring after save |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| (Future) Implementation | Extension spec | Build instructions |

---

## 3. Architecture

### 3.1 Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Chrome Extension                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Popup     │  │  Content    │  │  Background         │  │
│  │   (React)   │  │  Script     │  │  Service Worker     │  │
│  │             │  │             │  │                     │  │
│  │ • Preview   │  │ • Text      │  │ • API calls         │  │
│  │ • Edit      │  │   selection │  │ • Token storage     │  │
│  │ • Save      │  │ • URL badge │  │ • Badge updates     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Zentropy Scout API                        │
│                                                              │
│  POST /job-postings/ingest      → Parse raw text            │
│  POST /job-postings/ingest/confirm → Save job posting       │
│  GET  /job-postings?source_url= → Check if URL exists       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

```
User on LinkedIn job page
         │
         │ Clicks extension icon
         ▼
┌─────────────────────────┐
│ Content Script          │
│ • Extracts page text    │
│ • Gets current URL      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Background Worker       │
│ • POST /ingest          │
│ • Receives preview      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Popup UI                │
│ • Shows extracted data  │
│ • User can edit fields  │
│ • User confirms save    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Background Worker       │
│ • POST /ingest/confirm  │
│ • Updates URL badge     │
└─────────────────────────┘
```

---

## 4. User Interface

### 4.1 Extension States

| State | Trigger | UI |
|-------|---------|-----|
| **Idle** | No job page detected | Gray icon, "Open a job posting to capture" |
| **Ready** | Job-like page detected | Colored icon, "Capture this job" |
| **Loading** | Submitting to API | Spinner, "Parsing job details..." |
| **Preview** | API returned preview | Editable form with extracted data |
| **Saved** | User confirmed | Success message, link to open in app |
| **Already Saved** | URL matches existing job | "Already saved" badge, link to view |
| **Error** | API error | Error message with retry option |

### 4.2 Popup Layout (Preview State)

```
┌─────────────────────────────────────────┐
│  Zentropy Scout                    [×]  │
├─────────────────────────────────────────┤
│                                         │
│  Job Title                              │
│  ┌─────────────────────────────────┐    │
│  │ Senior Software Engineer        │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Company                                │
│  ┌─────────────────────────────────┐    │
│  │ Acme Corp                       │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Location                               │
│  ┌─────────────────────────────────┐    │
│  │ San Francisco, CA (Hybrid)      │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Salary Range                           │
│  ┌──────────┐  to  ┌──────────┐         │
│  │ $150,000 │      │ $200,000 │         │
│  └──────────┘      └──────────┘         │
│                                         │
│  Extracted Skills (5)           [Edit]  │
│  ┌─────────────────────────────────┐    │
│  │ Python (Required)               │    │
│  │ Kubernetes (Required)           │    │
│  │ AWS (Preferred)                 │    │
│  │ ...                             │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │         💾 Save Job             │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │    ↗ Open in Zentropy Scout     │    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
```

### 4.3 URL Badge System

The extension shows visual indicators on job board pages:

| Badge | Meaning | Visual |
|-------|---------|--------|
| None | Not yet captured | No badge |
| 🟢 Green checkmark | Saved, status = Discovered | Small green dot on icon |
| ⭐ Star | Saved + Favorited | Yellow star on icon |
| 📝 Blue | Applied | Blue checkmark |
| ❌ Gray | Dismissed | Grayed out |

**Implementation:** Background worker queries `GET /job-postings?source_url={url}` on page load.

---

## 5. Content Extraction

### 5.1 Text Extraction Strategy

The content script extracts text for the backend to parse:

```javascript
function extractJobText() {
  // Strategy 1: Look for structured data (JSON-LD)
  const jsonLd = document.querySelector('script[type="application/ld+json"]');
  if (jsonLd) {
    try {
      const data = JSON.parse(jsonLd.textContent);
      if (data['@type'] === 'JobPosting') {
        return { type: 'structured', data };
      }
    } catch (e) { /* fall through */ }
  }

  // Strategy 2: Look for common job description containers
  const selectors = [
    '[data-testid="job-description"]',  // LinkedIn
    '.job-description',
    '.jobDescriptionContent',
    '#job-details',
    'article',
    'main'
  ];

  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.length > 500) {
      return { type: 'text', data: el.textContent };
    }
  }

  // Strategy 3: Fallback to body text
  return { type: 'text', data: document.body.innerText };
}
```

**Why server-side parsing?**
- LLM extraction is more accurate than regex
- Parsing logic updates without extension republish
- Keeps extension lightweight (no ML dependencies)
- Consistent extraction across all sources

### 5.2 Page Detection Heuristics

The extension determines if a page is "job-like":

| Signal | Weight | Example |
|--------|--------|---------|
| URL contains `/job` | +2 | linkedin.com/jobs/view/123 |
| URL contains `career` | +2 | company.com/careers/posting |
| Page has "Apply" button | +3 | Button text matches /apply|submit/i |
| JSON-LD JobPosting | +5 | Structured data present |
| Text >1000 chars with job keywords | +2 | "responsibilities", "qualifications" |

**Threshold:** Score ≥ 3 → Show "Ready" state.

---

## 6. API Integration

### 6.1 Ingest Flow

**Step 1: Submit raw text**

```javascript
// Background service worker
async function submitJob(rawText, sourceUrl) {
  const response = await fetch(`${API_BASE}/job-postings/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${await getToken()}`
    },
    body: JSON.stringify({
      raw_text: rawText,
      source_url: sourceUrl,
      source_name: detectSourceName(sourceUrl)
    })
  });

  if (!response.ok) {
    throw new ApiError(await response.json());
  }

  return response.json();  // { preview, confirmation_token, expires_at }
}
```

**Step 2: Confirm with optional edits**

```javascript
async function confirmJob(token, modifications = {}) {
  const response = await fetch(`${API_BASE}/job-postings/ingest/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${await getToken()}`
    },
    body: JSON.stringify({
      confirmation_token: token,
      modifications
    })
  });

  return response.json();  // Full JobPosting
}
```

### 6.2 Duplicate Detection

Before showing the capture UI, check if URL already exists:

```javascript
async function checkExisting(url) {
  const response = await fetch(
    `${API_BASE}/job-postings?source_url=${encodeURIComponent(url)}`,
    { headers: { 'Authorization': `Bearer ${await getToken()}` } }
  );

  const { data } = await response.json();
  return data.length > 0 ? data[0] : null;
}
```

**UI Behavior:**
- If exists → Show "Already Saved" state with link to view
- If not exists → Proceed with capture flow

### 6.3 Error Handling

| Error Code | User Message | Action |
|------------|--------------|--------|
| `EXTRACTION_FAILED` | "Couldn't parse this job posting. Try selecting the text manually." | Show manual selection UI |
| `DUPLICATE_JOB` | "You've already saved this job." | Show link to existing |
| `TOKEN_EXPIRED` | "Preview expired. Please try again." | Auto-retry submission |
| `UNAUTHORIZED` | "Please connect to Zentropy Scout" | Show connection settings |
| `NETWORK_ERROR` | "Can't reach Zentropy Scout. Is it running?" | Show connection help |

---

## 7. Authentication

### 7.1 Local Mode (MVP)

For local self-hosted deployments:

| Setting | Value |
|---------|-------|
| API Base URL | `http://localhost:8000/api/v1` |
| Auth Mode | None (uses `DEFAULT_USER_ID`) |
| Token | Not required |

**Configuration UI:**
```
┌─────────────────────────────────────────┐
│  Settings                          [×]  │
├─────────────────────────────────────────┤
│                                         │
│  API Server URL                         │
│  ┌─────────────────────────────────┐    │
│  │ http://localhost:8000           │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Status: ✅ Connected                   │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │         Test Connection         │    │
│  └─────────────────────────────────┘    │
│                                         │
└─────────────────────────────────────────┘
```

### 7.2 Future: Hosted Mode

When hosted deployment is available:

| Setting | Value |
|---------|-------|
| API Base URL | `https://api.zentropyscout.com/v1` |
| Auth Mode | OAuth / API Key |
| Token | Stored in `chrome.storage.sync` |

---

## 8. Permissions

### 8.1 Required Permissions

| Permission | Reason |
|------------|--------|
| `activeTab` | Read current page content when user clicks icon |
| `storage` | Store API URL and auth token |
| `host_permissions: <all_urls>` | Capture jobs from any website |

### 8.2 Optional Permissions

| Permission | Reason | When Requested |
|------------|--------|----------------|
| `tabs` | Badge updates on navigation | First use |
| `notifications` | Notify when job scoring complete | User opts in |

**Privacy Note:** Extension only activates when user clicks. No background scraping.

---

## 9. Edge Cases

### 9.1 Content Extraction Failures

| Scenario | Handling |
|----------|----------|
| Page behind login wall | Show "Log in first, then try again" |
| PDF job posting | Show "PDF not supported, copy text manually" |
| Iframe content | Attempt to access if same-origin; otherwise show manual mode |
| Very short text (<200 chars) | Show "Not enough content. Is this a job posting?" |
| Non-English content | Submit anyway; backend handles multilingual |

### 9.2 Network Issues

| Scenario | Handling |
|----------|----------|
| API unreachable | Cache submission locally, retry when connected |
| Slow response (>10s) | Show progress, allow cancel |
| Rate limited | Show "Too many requests, please wait" with countdown |

### 9.3 Duplicate Handling

| Scenario | Handling |
|----------|----------|
| Same URL, different text | Offer to update existing or create new |
| Similar job, different URL | Backend deduplication (future); save as new for MVP |
| User dismissed previously | Allow re-save with status reset to Discovered |

---

## 10. Design Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Server-side parsing | Client / Server | Server | LLM extraction more accurate; updates without republish |
| Preview before save | Auto-save / Preview | Preview | Users want to verify extracted data |
| Popup vs Side Panel | Popup / Side Panel / Both | Popup | Simpler UX; side panel for future power features |
| Badge system | None / Simple / Detailed | Simple | Low overhead; shows saved status without clutter |
| All-URLs permission | Specific domains / All URLs | All URLs | Users find jobs on any website; can't predict |

---

## 11. Open Questions

| Question | Impact | Proposed Resolution |
|----------|--------|---------------------|
| Should we support manual text selection? | Fallback for extraction failures | Yes, add "Select text" mode |
| Should badges persist across sessions? | UX continuity | Yes, cache in storage, refresh periodically |
| Should we support keyboard shortcuts? | Power user efficiency | Add Ctrl+Shift+Z to capture (post-MVP) |
| How to handle job boards with infinite scroll? | Multiple jobs on one page | Focus on single-job pages; multi-capture post-MVP |

---

## 12. Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-01-25 | Initial draft | Claude |

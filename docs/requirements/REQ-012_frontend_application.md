# REQ-012: Frontend Application

**Status:** Draft
**Version:** 0.1
**PRD Reference:** §7 User Interface & Workflow
**Last Updated:** 2026-02-08

---

## 1. Overview

This document specifies the Zentropy Scout frontend application: a Next.js web interface that enables users to build their professional persona, discover and evaluate job opportunities, generate tailored application materials, and track their job search — all through a combination of direct UI controls and a conversational AI chat interface.

**Key Principle:** The chat interface is the primary interaction method. Traditional UI controls exist as a visual complement and direct-manipulation fallback. Users should be able to accomplish any task through either channel.

### 1.1 Scope

| In Scope | Out of Scope |
|----------|--------------|
| Chat interface with SSE streaming | Chrome Extension UI (REQ-011, postponed) |
| Onboarding flow (12-step wizard) | Mobile native app |
| Persona management (all sections) | PDF rendering engine (backend concern) |
| Job dashboard with scoring display | LLM prompt engineering (REQ-010) |
| Resume management and variant review | Agent orchestration logic (REQ-007) |
| Cover letter management and editing | Embedding generation (REQ-009) |
| Application tracking and timeline | Database schema (REQ-005) |
| Settings and source configuration | API implementation (REQ-006) |
| Shared components and design system | Interview preparation features |

### 1.2 Design Principles

| Principle | Description | Enforcement |
|-----------|-------------|-------------|
| **Chat-First** | Every action accessible via chat; UI provides visual shortcuts | All UI actions map to agent tools |
| **Human-in-the-Loop** | AI proposes, user decides; nothing sent without approval | Explicit approve/reject on all generated content |
| **Progressive Disclosure** | Show summary first, details on demand | Expandable sections, drill-down views |
| **Transparent AI** | Users see what agents are doing and why | Tool execution indicators, agent reasoning display |
| **Full Traceability** | Every application linked to exact versions used | Version badges, snapshot displays, timeline |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-001 Persona Schema v0.8 | Data model | All persona fields, validation rules, deletion handling |
| REQ-002 Resume Schema v0.7 | Data model | BaseResume, JobVariant, SubmittedPDF lifecycle |
| REQ-002b Cover Letter Schema v0.5 | Data model | CoverLetter lifecycle, validation rules |
| REQ-003 Job Posting Schema v0.4 | Data model | JobPosting fields, ghost detection, cross-source |
| REQ-004 Application Schema v0.3 | Data model | Application lifecycle, timeline events, offer/rejection capture |
| REQ-006 API Contract v0.7 | Integration | All REST endpoints, SSE events, pagination, error handling |
| REQ-007 Agent Behavior v0.4 | Integration | Chat flow, HITL checkpoints, onboarding steps, agent tools |
| REQ-008 Scoring Algorithm v0.2 | Display | Fit/Stretch score components, explanation structure |
| REQ-010 Content Generation v0.1 | Display | Agent reasoning format, validation rules, regeneration feedback |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| (Future) Frontend Implementation Plan | Build spec | Implementation phases and task breakdown |
| (Future) E2E Test Plan | Test targets | Playwright test scenarios |

---

## 3. Information Architecture

### 3.1 Page Inventory

| Page | Route | Purpose | Auth Gate |
|------|-------|---------|-----------|
| **Onboarding** | `/onboarding` | 12-step persona wizard | New/incomplete users only |
| **Dashboard** | `/` | Job opportunities, applications, history | Onboarded |
| **Job Detail** | `/jobs/[id]` | Full job posting with scores and actions | Onboarded |
| **Persona** | `/persona` | View and edit professional profile | Onboarded |
| **Resumes** | `/resumes` | Base resume list and management | Onboarded |
| **Resume Detail** | `/resumes/[id]` | Base resume editor, variant list | Onboarded |
| **Applications** | `/applications` | Application tracking pipeline | Onboarded |
| **Application Detail** | `/applications/[id]` | Full application record with timeline | Onboarded |
| **Settings** | `/settings` | Source preferences, agent config | Onboarded |

### 3.2 Navigation Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Logo    Dashboard    Persona    Resumes    Applications    │
│                                              Settings  [?]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    Page Content Area                        │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                Chat Panel (collapsible sidebar/drawer)       │
│  [Pending Flags: 3]  [Pending Reviews: 2]                   │
└─────────────────────────────────────────────────────────────┘
```

**Primary navigation:** Horizontal top bar with links to major sections.

**Chat panel:** Persistent, collapsible sidebar or bottom drawer accessible from all pages. Always available.

**Critical info indicators** (always visible in navigation area):
- Pending persona change flags count (badge)
- Pending reviews count (materials awaiting approval)
- Active applications count

### 3.3 Routing and Entry Gate

| User State | Behavior |
|------------|----------|
| No persona exists | Redirect to `/onboarding` |
| `onboarding_complete = false` | Redirect to `/onboarding` (resumes at saved step) |
| `onboarding_complete = true` | Allow access to all routes |

MVP single-user: No login page. `DEFAULT_USER_ID` injected by backend middleware. Persona check on first load determines routing.

### 3.4 User Flows

#### 3.4.1 New User Flow

```
First visit → Check persona → None found → /onboarding
  → Resume upload (optional)
  → Basic info → Work history → Education → Skills → Certifications
  → Achievement stories → Non-negotiables → Growth targets
  → Voice profile review → Full persona review → Base resume setup
  → /dashboard (Scouter begins first scan)
```

#### 3.4.2 Returning User — Job Discovery Flow

```
/dashboard → Opportunities tab (sorted by fit score)
  → Click job → /jobs/[id] (score breakdown, extracted skills)
  → "Draft materials" (via chat or button)
  → Review variant + cover letter → Approve both
  → Download PDFs → Apply externally
  → Return → "Mark as Applied" → Application created
  → /applications/[id] (status tracking begins)
```

#### 3.4.3 Returning User — Application Tracking Flow

```
/applications → Active pipeline view
  → Update status (Interviewing, Offer, Rejected, Withdrawn)
  → Capture details (interview stage, offer terms, rejection feedback)
  → Follow-up suggestions from agent (5-day gap trigger)
  → Terminal state reached → Application moves to history
```

#### 3.4.4 Persona Update Flow

```
/persona → Edit any section
  → Save → Embeddings regenerate → Jobs rescored
  → PersonaChangeFlag created → Badge appears
  → Resolve flags (add to base resumes: all / some / skip)
```

---

## 4. Frontend Architecture

### 4.1 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Framework** | Next.js | 14+ | App Router, React Server Components |
| **Language** | TypeScript | 5.x | Type safety |
| **Styling** | Tailwind CSS | 3.x | Utility-first CSS |
| **Components** | shadcn/ui | latest | Accessible Radix + Tailwind components |
| **State Management** | TanStack Query | v5 | Server state caching, mutations, optimistic updates |
| **SSE Client** | Native EventSource | — | Browser-native SSE; custom reconnection wrapper |
| **Forms** | React Hook Form + Zod | latest | Form state, validation |
| **Icons** | Lucide React | latest | Consistent icon set (shadcn default) |

### 4.2 State Management Strategy

#### 4.2.1 Server State (TanStack Query)

All data from the backend API is server state, managed by TanStack Query:

```typescript
// Query keys follow a consistent hierarchy
const queryKeys = {
  personas: ['personas'] as const,
  persona: (id: string) => ['personas', id] as const,
  jobs: ['jobs'] as const,
  job: (id: string) => ['jobs', id] as const,
  applications: ['applications'] as const,
  application: (id: string) => ['applications', id] as const,
  resumes: ['resumes'] as const,
  variants: ['variants'] as const,
  coverLetters: ['cover-letters'] as const,
  changeFlags: ['change-flags'] as const,
  // ...
};
```

**Cache invalidation via SSE:** When the SSE stream emits a `data_changed` event, the corresponding query is invalidated:

```typescript
// SSE data_changed → TanStack Query invalidation
function handleDataChanged(event: DataChangedEvent) {
  switch (event.resource) {
    case 'job-posting':
      queryClient.invalidateQueries({ queryKey: ['jobs', event.id] });
      break;
    case 'application':
      queryClient.invalidateQueries({ queryKey: ['applications', event.id] });
      break;
    // ...
  }
}
```

**Optimistic updates** for instant feedback on user actions:

```typescript
// Example: favorite toggle
useMutation({
  mutationFn: (id: string) => api.favoriteJob(id),
  onMutate: async (id) => {
    // Optimistically update the cache
    await queryClient.cancelQueries({ queryKey: ['jobs', id] });
    const previous = queryClient.getQueryData(['jobs', id]);
    queryClient.setQueryData(['jobs', id], (old) => ({
      ...old,
      is_favorite: !old.is_favorite,
    }));
    return { previous };
  },
  onError: (err, id, context) => {
    // Rollback on failure
    queryClient.setQueryData(['jobs', id], context.previous);
  },
});
```

#### 4.2.2 Client State (React Context / useState)

Minimal client-only state, managed locally:

| State | Scope | Storage |
|-------|-------|---------|
| Chat panel open/closed | Global | React Context |
| Active dashboard tab | Page | URL query param |
| Multi-select mode (bulk ops) | Page | useState |
| Form dirty state | Component | React Hook Form |
| SSE connection status | Global | React Context |

#### 4.2.3 URL State

Filters, sort order, pagination, and active tabs live in URL query parameters for shareability and browser history:

```
/jobs?status=Discovered&sort=-fit_score&page=1
/applications?status=Applied,Interviewing
```

### 4.3 API Client

A typed API client wraps all REST calls with consistent error handling:

```typescript
// Typed response envelope matching REQ-006 conventions
interface ApiResponse<T> {
  data: T;
  meta?: { total: number; page: number; per_page: number };
}

interface ApiError {
  error: { code: string; message: string; details?: unknown[] };
}

// All endpoints typed with request/response shapes
const api = {
  personas: {
    get: (id: string) => fetch<ApiResponse<Persona>>(`/api/v1/personas/${id}`),
    update: (id: string, data: Partial<Persona>) =>
      fetch<ApiResponse<Persona>>(`/api/v1/personas/${id}`, { method: 'PATCH', body: data }),
    // ...
  },
  jobs: {
    list: (params: JobListParams) => fetch<ApiResponse<JobPosting[]>>('/api/v1/job-postings', { params }),
    // ...
  },
};
```

**Error handling:** All API errors follow the REQ-006 shape. The client:
1. Parses the `error.code` for programmatic handling (e.g., `INVALID_STATE_TRANSITION`)
2. Displays `error.message` to the user via toast notification
3. Logs `error.details` for debugging

**Rate limit handling:** 429 responses trigger a retry with exponential backoff (max 3 attempts).

### 4.4 SSE Client

A custom EventSource wrapper handles the single SSE connection:

```typescript
interface SSEClientConfig {
  url: string;                    // /api/v1/chat/stream
  onChatToken: (text: string) => void;
  onChatDone: (messageId: string) => void;
  onToolStart: (tool: string, args: Record<string, unknown>) => void;
  onToolResult: (tool: string, success: boolean) => void;
  onDataChanged: (resource: string, id: string, action: string) => void;
  onDisconnect: () => void;
  onReconnect: () => void;
}
```

**Reconnection strategy:**
- On disconnect: attempt reconnect with exponential backoff (1s, 2s, 4s, max 30s)
- On tab inactive > 5 minutes: close SSE, reconnect + full REST refresh on return
- On reconnect: fire `onReconnect` callback which triggers `queryClient.invalidateQueries()` for all active queries
- Show connection status indicator (connected / reconnecting / disconnected)

**Tab visibility detection:**
```typescript
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    startInactivityTimer(5 * 60 * 1000); // 5 minutes
  } else {
    if (wasInactiveOver5Min()) {
      reconnectSSE();
      queryClient.invalidateQueries(); // Full refresh
    }
  }
});
```

### 4.5 Responsive Strategy

| Breakpoint | Target | Layout |
|------------|--------|--------|
| `< 768px` (sm) | Mobile | Single column, chat as full-screen overlay, simplified tables → card lists |
| `768-1024px` (md) | Tablet | Two-column where needed, collapsible chat sidebar |
| `> 1024px` (lg) | Desktop | Full layout with persistent chat sidebar option |

**Mobile-first approach:** Base styles target mobile; `md:` and `lg:` prefixes add complexity for larger screens.

**Mobile-specific adaptations:**
- Job list: cards instead of table rows
- Score drill-down: accordion instead of side panel
- Chat: full-screen overlay instead of sidebar
- Bulk operations: long-press to enter selection mode
- Drag-and-drop reordering: replaced with up/down buttons on mobile

### 4.6 Authentication Strategy

**MVP (single-user):** No auth UI. Backend injects `DEFAULT_USER_ID` via middleware. Frontend sends no auth headers.

**Future (multi-tenant, hosted):**
- Login page at `/login` with OAuth or email/password
- Bearer token in `Authorization` header
- Token stored in httpOnly cookie (set by backend)
- TanStack Query cache cleared on logout
- All query keys implicitly scoped to authenticated user
- Middleware redirects unauthenticated requests to `/login`

The frontend architecture is designed so the auth transition requires:
1. Add a login page
2. Add an auth context provider
3. Add token to API client headers
4. Add auth middleware to the Next.js middleware chain

No component-level changes needed.

---

## 5. Chat Interface

**Surface area ref:** frontend_surface_area.md §1
**Backend refs:** REQ-006 §2.4-2.5, REQ-007 §4, §9.3, §15.1

### 5.1 Layout

The chat interface is a persistent panel accessible from all pages.

**Desktop (lg+):** Collapsible right sidebar, 400px wide. Toggle button in top nav. Retains scroll position when collapsed/expanded.

**Tablet (md):** Slide-over drawer from right edge. Overlay on page content.

**Mobile (sm):** Full-screen overlay with back button to return to page.

**Chat panel contents:**
```
┌─────────────────────────────┐
│  Chat            [_] [X]    │  ← Title, minimize, close
├─────────────────────────────┤
│                             │
│  Agent message bubble       │  ← Left-aligned
│                             │
│        User message bubble  │  ← Right-aligned
│                             │
│  Agent message with         │
│  ┌─────────────────────┐   │
│  │ Tool: Favoriting... │   │  ← Inline tool indicator
│  └─────────────────────┘   │
│                             │
│  Agent typing indicator...  │  ← During streaming
│                             │
├─────────────────────────────┤
│  [attachment] Type message  │  ← Input area
│                    [Send]   │
└─────────────────────────────┘
```

### 5.2 Message Types

| Type | Alignment | Styling | Content |
|------|-----------|---------|---------|
| User message | Right | Primary color background | Plain text, may include attachments |
| Agent text | Left | Muted background | Markdown-rendered text |
| Agent structured card | Left | Card component | Job details, score summaries (see §5.3) |
| Agent option list | Left | Interactive list | Numbered clickable options (ambiguity resolution) |
| Tool execution | Left, inline | Badge/chip | "Favoriting job..." → "Job favorited ✓" |
| Error | Left | Destructive color | Error explanation + suggested action |
| System notice | Center | Muted, small | "Connected", "Reconnecting...", session boundaries |

### 5.3 Structured Chat Cards

When the agent presents job data, scores, or application info, render as structured components within the chat — not raw text.

**Job card (compact):**
```
┌──────────────────────────────────┐
│ Senior Scrum Master              │
│ Acme Corp · Austin, TX · Remote  │
│ Fit: 92  Stretch: 45             │
│ $140k-$160k                      │
│ [View] [Favorite ♡] [Dismiss]   │
└──────────────────────────────────┘
```

**Score summary card:**
```
┌──────────────────────────────────┐
│ Fit Score: 92 (High)             │
│ ├ Hard Skills:  82  (40%)        │
│ ├ Experience:   95  (25%)        │
│ ├ Soft Skills:  88  (15%)        │
│ ├ Role Title:   90  (10%)        │
│ └ Location:    100  (10%)        │
│                                  │
│ Stretch Score: 45 (Lateral)      │
│                                  │
│ Strengths: Python, FastAPI, SQL  │
│ Gaps: Kubernetes (required)      │
└──────────────────────────────────┘
```

Actions within chat cards trigger the same API calls as dashboard UI controls.

### 5.4 SSE Streaming Display

**Token-by-token rendering:**
- Append each `chat_token` to the current message bubble
- Show a blinking cursor at the end during streaming
- On `chat_done`, remove cursor, mark message complete, re-enable input

**Tool execution visualization:**
- On `tool_start`: insert inline badge below the last chat token — "Favoriting job..." with spinner
- On `tool_result`: replace spinner with success (✓) or failure (✗) icon
- Continue appending `chat_token` events after tool completes

**Typing indicator:** While tokens are streaming, show a "Scout is typing..." indicator above the input. Disappear on `chat_done`.

### 5.5 Reconnection UX

| State | Indicator | User Action |
|-------|-----------|-------------|
| Connected | Green dot in chat header | None needed |
| Reconnecting | Amber dot + "Reconnecting..." system message | Wait; auto-resolves |
| Disconnected | Red dot + "Connection lost. Refresh to reconnect." | Manual refresh button |
| Tab returned (>5 min) | Brief "Refreshing..." overlay | Auto-resolves |

On reconnect, the chat history is preserved (loaded from backend on reconnection).

### 5.6 Ambiguity Resolution UI

When the agent presents numbered options (REQ-007 §4.4):

```
Agent: "Which job would you like to dismiss?"
┌──────────────────────────────────┐
│ 1. Scrum Master at Acme Corp     │  ← Clickable
│ 2. Product Owner at TechCo       │  ← Clickable
│ 3. Agile Coach at StartupX       │  ← Clickable
└──────────────────────────────────┘
[Or type to describe...]
```

- Options rendered as clickable list items within a chat card
- Clicking an option sends the selection as a user message ("1" or the full text)
- User can also type a free-text response instead
- Destructive confirmations render as a distinct card with explicit "Proceed" / "Cancel" buttons

### 5.7 Chat Input

- Text input with send button (Enter to send, Shift+Enter for newline)
- Attachment button for file uploads (images, PDFs — forwarded to agent)
- Input disabled while agent is streaming a response
- Character limit indicator (for feedback messages, 500 char max)
- Placeholder text changes contextually: "Ask Scout anything..." (default), "Type your answer..." (during ambiguity resolution)

### 5.8 Chat History

- Messages persist across page navigation (panel retains state)
- On page load: fetch recent chat history via REST, then establish SSE
- Scroll to bottom on new messages (unless user has scrolled up)
- "Jump to latest" button appears when scrolled up and new messages arrive

---

## 6. Onboarding Flow

**Surface area ref:** frontend_surface_area.md §2
**Backend refs:** REQ-001 §6, REQ-007 §5, §15.2

### 6.1 Entry and Routing

| Condition | Route | Behavior |
|-----------|-------|----------|
| No persona exists | `/onboarding` | Begin step 1 |
| `onboarding_complete = false` | `/onboarding` | Resume at saved `onboarding_step` |
| `onboarding_complete = true` | `/` | Dashboard (skip onboarding) |

All non-onboarding routes redirect to `/onboarding` until completion.

### 6.2 Layout

Full-screen layout (no main navigation bar). Minimal chrome:

```
┌─────────────────────────────────────────────┐
│  Zentropy Scout        Step 3 of 12  [···]  │  ← Logo, progress
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │                                     │    │
│  │     Chat-style conversation area    │    │
│  │     (agent questions + user input)  │    │
│  │                                     │    │
│  │     ── or ──                        │    │
│  │                                     │    │
│  │     Form area (for structured       │    │
│  │     input steps like basic_info)    │    │
│  │                                     │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  [Back]                    [Skip] [Next]    │  ← Navigation
└─────────────────────────────────────────────┘
```

**Progress indicator:** Step number (e.g., "Step 3 of 12") + horizontal progress bar. Steps are labeled but detailed names only shown on hover/click (to avoid clutter).

### 6.3 Step-by-Step Specifications

#### 6.3.1 Step 1: Resume Upload (`resume_upload`)

**UI mode:** Upload widget + skip option

```
┌─────────────────────────────────────┐
│                                     │
│  "Got a resume? Upload it and I'll  │
│   use it to pre-fill your profile." │
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │   Drop PDF or DOCX here    │    │
│  │   or click to browse       │    │
│  │                             │    │
│  │   Max 10MB · PDF or DOCX   │    │
│  └─────────────────────────────┘    │
│                                     │
│  [Skip — I'll enter manually]       │
└─────────────────────────────────────┘
```

**Behavior:**
- Drag-and-drop or file picker (PDF/DOCX only)
- Upload via `POST /api/v1/resume-files` (`multipart/form-data`)
- Show upload progress bar
- On success: display "Resume uploaded! I'll use this to pre-fill your profile." → auto-advance
- On failure: display error message, allow retry
- File size validation: client-side check before upload (max 10MB)
- Skip option always visible — advances to step 2 without upload

#### 6.3.2 Step 2: Basic Info (`basic_info`)

**UI mode:** Form

| Field | Input Type | Required | Validation |
|-------|-----------|----------|------------|
| Full name | Text | Yes | Non-empty |
| Email | Email | Yes | Email format, unique |
| Phone | Tel | Yes | Non-empty |
| LinkedIn URL | URL | No | URL format if provided |
| Portfolio URL | URL | No | URL format if provided |
| City | Text | Yes | Non-empty |
| State | Text | Yes | Non-empty |
| Country | Text/Select | Yes | Non-empty |

If resume was uploaded, pre-fill from extracted data. User confirms or corrects.

#### 6.3.3 Step 3: Work History (`work_history`)

**UI mode:** Hybrid (form + conversational)

If resume uploaded:
- Display extracted jobs in editable cards
- Each card shows: title, company, dates, location, work model
- User confirms, edits, or deletes each
- "Add another job" button at bottom
- Agent prompt: "I found these roles in your resume. Look right?"

If no resume:
- Agent asks: "Tell me about your current or most recent role."
- After capture: "Any other roles to add?"
- Minimum 1 job required to proceed

**Per-job bullet editing:**
- Each job card expands to show accomplishment bullets
- Min 1 bullet per job
- "Add bullet" button
- Agent may prompt: "Can you quantify that result?"

#### 6.3.4 Step 4: Education (`education`)

**UI mode:** Form (skippable)

If resume uploaded: display extracted education for confirmation.

Otherwise: "Do you have any formal education to include? (This is optional)"

- Skip button: "Skip — No education to add"
- Add form: degree, field, institution, graduation year, optional GPA/honors

#### 6.3.5 Step 5: Skills (`skills`)

**UI mode:** Interactive list + conversational

If resume uploaded:
- Display extracted skills as chips/tags
- Each skill needs: type (Hard/Soft), category, proficiency rating, years used, last used
- Agent prompt: "I found these skills. Rate your proficiency for each."

**Proficiency selector per skill:**
```
┌──────────────────────────────────┐
│ Python                    Hard   │
│ Category: Programming Language   │
│                                  │
│ Proficiency:                     │
│ ○ Learning  ○ Familiar           │
│ ● Proficient  ○ Expert           │
│                                  │
│ Years used: [5]  Last used: [Current] │
└──────────────────────────────────┘
```

- Tooltip on each proficiency level with definition (see REQ-001 §3.4)
- Category dropdown changes options based on Hard vs. Soft type
- "Add skill" button at bottom
- All 6 fields required per skill

#### 6.3.6 Step 6: Certifications (`certifications`)

**UI mode:** Form (skippable)

"Do you have any professional certifications?"

- Skip button: "Skip — No certifications"
- Add form: name, issuer, date obtained, optional expiration/credential ID/URL
- "Does not expire" checkbox that nulls the expiration date field

#### 6.3.7 Step 7: Achievement Stories (`achievement_stories`)

**UI mode:** Conversational

This is the most conversational step. The agent conducts a guided interview:

```
Agent: "Now I'd like to hear about times you made a real impact.
        Think of a situation where you solved a problem, led a team,
        or achieved something you're proud of."

Agent: "What was the situation?" → User responds → captures `context`
Agent: "What did you do?"       → User responds → captures `action`
Agent: "What was the result?"   → User responds → captures `outcome`
Agent: "Can you quantify that?" → User responds → refines `outcome`
Agent: "Which skills did this demonstrate?" → skill picker → captures `skills_demonstrated`
```

**Story counter:** "Story 2 of 3-5 (minimum 3)" displayed in progress area.

After each story, agent asks: "Great story! Want to add another, or are we good?"

**Story review card** shown after capture:
```
┌──────────────────────────────────┐
│ "Turned around failing project"  │
│                                  │
│ Context: Team was behind...      │
│ Action: Reorganized sprints...   │
│ Outcome: Delivered 2 weeks...    │
│ Skills: Leadership, Agile        │
│                                  │
│ [Edit]  [Delete]                 │
└──────────────────────────────────┘
```

#### 6.3.8 Step 8: Non-Negotiables (`non_negotiables`)

**UI mode:** Form with sections

Three sections with clear headers:

**Location:**
- Remote preference: radio group (Remote Only / Hybrid OK / Onsite OK / No Preference)
- Commutable cities: tag input (hidden if Remote Only)
- Max commute: number input (hidden if Remote Only)
- Open to relocation: toggle
- Relocation cities: tag input (hidden if relocation = false)

**Compensation:**
- Minimum base salary: currency input with currency selector (default USD)
- "Prefer not to set" option that nulls the field

**Other filters:**
- Visa sponsorship required: toggle
- Industry exclusions: tag input
- Company size preference: radio group
- Max travel: radio group

**Custom non-negotiables:** "Add custom filter" button → modal/inline form:
- Filter name (text)
- Type: Exclude / Require (radio)
- Field to check: dropdown with suggestions (company_name, description, job_title) + custom text
- Value to match (text)
- List of existing custom filters with edit/delete

#### 6.3.9 Step 9: Growth Targets (`growth_targets`)

**UI mode:** Form

- Target roles: tag input (e.g., "Engineering Manager", "Staff Engineer")
- Target skills: tag input (e.g., "Kubernetes", "People Management")
- Stretch appetite: radio group with descriptions:
  - Low: "Show me roles I'm already qualified for"
  - Medium: "Mix of comfortable and stretch roles" (default)
  - High: "Challenge me — I want to grow into new areas"

#### 6.3.10 Step 10: Voice Profile (`voice_profile`)

**UI mode:** Review and edit (agent-derived)

Agent presents derived voice profile:
```
Agent: "Based on our conversation, here's how I'd describe
        your writing voice:"

┌──────────────────────────────────┐
│ Tone: Direct, confident          │ [Edit]
│ Style: Short sentences, active   │ [Edit]
│ Vocabulary: Technical when       │ [Edit]
│   relevant, plain otherwise      │
│ Personality: Occasional dry      │ [Edit]
│   humor                          │
│ Sample phrases:                  │
│   • "I led..."                   │ [Edit]
│   • "The result was..."          │
│ Avoid:                           │
│   • "Passionate"                 │ [Edit]
│   • "Synergy"                    │
└──────────────────────────────────┘

Agent: "Does this sound like you? Edit anything that
        doesn't feel right."

[Looks good!]  [Let me edit]
```

If "Let me edit": each field becomes editable inline. Tag inputs for `sample_phrases` and `things_to_avoid`.

Optional: "Paste a writing sample for better voice matching" → textarea → `writing_sample_text`.

#### 6.3.11 Step 11: Review (`review`)

**UI mode:** Structured summary

Full persona displayed in collapsible sections:
- Basic info
- Professional overview
- Work history (job count)
- Education (entry count)
- Skills (count by type)
- Certifications (count)
- Achievement stories (count)
- Non-negotiables summary
- Growth targets
- Voice profile summary

Each section has an "Edit" link that navigates back to the relevant step.

"Everything look good?" → [Confirm and Continue] button.

#### 6.3.12 Step 12: Base Resume Setup (`base_resume_setup`)

**UI mode:** Guided wizard

```
Agent: "What type of role are you primarily targeting?"
User: "Scrum Master"

Agent: "Great! I'll create a 'Scrum Master' resume. Let me
        suggest which of your experience to highlight..."
```

**Resume creation form:**
- Name: pre-filled from agent suggestion (e.g., "Scrum Master")
- Summary: agent drafts, user reviews/edits
- Included jobs: checkboxes (agent pre-selects relevant ones)
- Bullets per job: checkboxes within each job (agent pre-selects)
- Education: checkboxes (default: all)
- Certifications: checkboxes (default: all)
- Skills emphasis: checkboxes (agent pre-selects relevant)

Agent generates anchor PDF → preview → "Approve" button.

"Any other role types to target?" → repeat for additional base resumes, or "No, I'm good" → complete.

### 6.4 Checkpoint and Resume Behavior

| Event | Behavior |
|-------|----------|
| User closes browser | `onboarding_step` saved server-side |
| User returns | Show resume prompt: "Welcome back! We were on [step name]. Continue?" |
| Checkpoint TTL expired (24h) | "Your session expired. Let's pick up where we left off." (data is preserved, just the checkpoint) |
| User requests restart | "Start fresh or continue where we left off?" dialog |
| Skip optional step | Advance to next step, mark as skipped (not incomplete) |

### 6.5 Completion

On step 12 approval:
1. Set `onboarding_complete = true` on persona
2. Trigger Scouter for first job scan
3. Redirect to `/` (dashboard)
4. Show welcome message in chat: "You're all set! I'm scanning for jobs now — I'll let you know what I find."

---

## 7. Persona Management

**Surface area ref:** frontend_surface_area.md §3
**Backend refs:** REQ-001, REQ-006 §5.2-5.4

### 7.1 Persona Overview Page (`/persona`)

Top-level dashboard showing persona completeness and section summaries.

```
┌─────────────────────────────────────────────────────────────┐
│  Your Professional Profile                    [Edit Mode]   │
├──────────────────────────┬──────────────────────────────────┤
│                          │                                  │
│  Brian Husk              │  Professional Summary            │
│  brian@email.com         │  "Experienced Scrum Master..."   │
│  Austin, TX              │  8 years experience              │
│  LinkedIn · Portfolio    │  Current: Sr. Scrum Master       │
│                          │                                  │
├──────────────────────────┴──────────────────────────────────┤
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Work (4) │ │Skills(12)│ │Stories(5)│ │ Certs (3)│      │
│  │ Edit →   │ │ Edit →   │ │ Edit →   │ │ Edit →   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Edu (2)  │ │ Voice    │ │ Non-Neg  │ │ Growth   │      │
│  │ Edit →   │ │ Edit →   │ │ Edit →   │ │ Edit →   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  Discovery Preferences                                      │
│  Fit threshold: 50  Auto-draft: 90  Polling: Daily         │
│  [Edit →]                                                   │
│                                                             │
│  ⚠ 3 pending changes need review  [Review →]               │
└─────────────────────────────────────────────────────────────┘
```

Each section card shows count/summary and links to the editor. The PersonaChangeFlag banner shows if pending flags exist.

### 7.2 Section Editors

Each persona section is an inline-expandable or navigable editor. All editors share common patterns:

**Save behavior:** Auto-save on blur / explicit save button (TBD per section complexity). Changes trigger `PATCH` or `PUT` on the relevant sub-resource endpoint.

**Validation:** Client-side via Zod schemas matching backend constraints. Server-side errors displayed inline.

**Reordering:** Drag-and-drop via `display_order` field. Falls back to up/down arrow buttons on mobile.

#### 7.2.1 Basic Info & Professional Overview Editor

Two-column form (desktop) or stacked (mobile). All fields from §3.1.1 and §3.1.2. Standard text inputs with inline validation.

#### 7.2.2 Work History Editor

List of job cards, ordered by `display_order`. Each card expandable to show:
- Job fields (title, company, dates, location, model)
- Accomplishment bullets (nested list, also reorderable)
- Conditional: `end_date` disabled when `is_current` toggled on

**Add job:** Button opens inline form or modal.
**Delete job:** Triggers reference check flow (§7.5).

#### 7.2.3 Education & Certifications Editors

Simple list of entries with add/edit/delete. Certifications have "Does not expire" toggle.

#### 7.2.4 Skills Editor

Two-section layout: Hard Skills / Soft Skills (tabs or sections).

Each skill rendered as a card with all 6 required fields. Category dropdown options change based on type.

**Add skill:** Opens inline form. `skill_name` must be unique (validated client-side + server 409).

#### 7.2.5 Achievement Stories Editor

Card list. Each card shows title + brief context. Expand for full Context/Action/Outcome fields plus skill links and related job.

#### 7.2.6 Voice Profile Editor

Single form. `sample_phrases` and `things_to_avoid` as tag inputs. `writing_sample_text` as optional textarea.

#### 7.2.7 Non-Negotiables Editor

Section-based form matching §6.3.8. Custom non-negotiables as a sub-list with CRUD.

#### 7.2.8 Growth Targets Editor

Simple form matching §6.3.9.

#### 7.2.9 Discovery Preferences Editor

Three controls with behavioral explanations:

| Control | Input | Explanation Text |
|---------|-------|-----------------|
| Minimum fit threshold | Slider 0-100 (default 50) | "Jobs scoring below {n} will be hidden from your feed" |
| Auto-draft threshold | Slider 0-100 (default 90) | "I'll automatically draft materials for jobs scoring {n} or above" |
| Polling frequency | Select | "How often should I check for new jobs?" |

**Validation warning:** If `auto_draft_threshold < minimum_fit_threshold`, show: "Auto-draft threshold is below your fit threshold — you may get drafts for jobs that are hidden from your feed."

### 7.3 Conditional Field Logic

| Condition | Effect |
|-----------|--------|
| `is_current = true` | `end_date` input disabled, shows "Present" |
| `relocation_open = false` | `relocation_cities` hidden |
| `remote_preference = "Remote Only"` | `commutable_cities` and `max_commute_minutes` hidden |
| `expiration_date` toggle "No expiration" | `expiration_date` input hidden/cleared |
| `skill_type` changes | Category dropdown options swap (Hard vs Soft lists) |

### 7.4 Reordering

Six collections support drag-and-drop reordering via `display_order`:

| Collection | Scope | Mobile Fallback |
|------------|-------|-----------------|
| Work history jobs | Persona-wide | Up/down arrows |
| Bullets within a job | Per-job | Up/down arrows |
| Education entries | Persona-wide | Up/down arrows |
| Skills | Per-type (Hard/Soft) | Up/down arrows |
| Certifications | Persona-wide | Up/down arrows |
| Achievement stories | Persona-wide | Up/down arrows |

Reorder saves immediately via PATCH with updated `display_order` values.

### 7.5 Deletion Handling (REQ-001 §7b)

Before deleting any persona item (job, bullet, skill, education, certification, story):

1. **API request:** Backend checks references across BaseResumes and draft CoverLetters
2. **No references:** Delete immediately, show success toast
3. **References found (mutable only):** Show three-option dialog:

```
┌──────────────────────────────────────────┐
│ This skill is used in 2 base resumes     │
│                                          │
│ • "Scrum Master" base resume             │
│ • "Product Owner" base resume            │
│                                          │
│ [Remove from all & delete]               │
│ [Review each]                            │
│ [Cancel]                                 │
└──────────────────────────────────────────┘
```

4. **"Review each":** Expand to show each affected entity with individual remove/keep toggles
5. **Immutable reference (Approved variant or Approved cover letter):**

```
┌──────────────────────────────────────────┐
│ ⚠ Cannot delete                          │
│                                          │
│ This item is part of an application you  │
│ submitted to Acme Corp. You can archive  │
│ that application first if you want to    │
│ delete this item.                        │
│                                          │
│ [Go to Application]  [Cancel]            │
└──────────────────────────────────────────┘
```

### 7.6 PersonaChangeFlags

**Trigger:** Adding new items post-onboarding (job, bullet, skill, education, certification).

**Display:** Badge on persona page + notification banner.

**Resolution UI:**
```
┌──────────────────────────────────────────┐
│ ⚠ 3 changes need review                 │
├──────────────────────────────────────────┤
│ ✦ Added skill: Kubernetes                │
│   [Add to all resumes] [Add to some] [Skip] │
│                                          │
│ ✦ New bullet on "TechCorp" role          │
│   [Add to all resumes] [Add to some] [Skip] │
│                                          │
│ ✦ New certification: AWS SA              │
│   [Add to all resumes] [Add to some] [Skip] │
└──────────────────────────────────────────┘
```

"Add to some" expands a checklist of base resumes.

### 7.7 Embedding Staleness

After persona edits that affect matching (skills, work history, non-negotiables):
- Show brief "Updating your match profile..." indicator
- On completion (SSE `data_changed` for embeddings): "Match profile updated. Job scores may have changed."
- Job list refreshes with updated scores

---

## 8. Job Dashboard & Scoring

**Surface area ref:** frontend_surface_area.md §4
**Backend refs:** REQ-003, REQ-006 §5.5, REQ-007 §6-7, REQ-008

### 8.1 Dashboard Layout (`/`)

Three-tab layout (per PRD §7.3):

| Tab | Content | Default Sort |
|-----|---------|-------------|
| **Opportunities** | Discovered jobs (scored, not applied) | Fit score descending (favorites pinned to top) |
| **In Progress** | Active applications (Applied, Interviewing, Offer) | Status updated date |
| **History** | Terminal applications (Accepted, Rejected, Withdrawn) + archived | Applied date |

**Tab state:** Persisted in URL: `/?tab=opportunities`

### 8.2 Opportunities Tab — Job List

**Desktop:** Table/list view with columns:

| Column | Content | Sortable |
|--------|---------|----------|
| Favorite | ♡/♥ toggle | Yes (favorites first) |
| Job Title | Title + company | Yes |
| Location | City + work model badge | No |
| Salary | Range or "Not disclosed" | Yes |
| Fit | Score + tier label + color | Yes |
| Stretch | Score + tier label | Yes |
| Ghost | Warning icon if ≥ 50 | No |
| Discovered | "X days ago" | Yes |
| Actions | ⋮ menu (View, Dismiss, Draft) | No |

**Mobile:** Card list with key info (title, company, fit score, salary).

**Toolbar:**
```
[Search...]  [Status: Discovered ▾]  [Min Fit: 50 ▾]  [Sort: Fit ↓ ▾]
[☐ Select]  [Show filtered jobs]
```

**Multi-select mode:** Checkbox column appears. Toolbar changes to:
```
[3 selected]  [Bulk Dismiss]  [Bulk Favorite]  [Cancel]
```

**"Show filtered jobs" toggle:** When enabled, shows jobs that failed non-negotiables with dimmed styling and failure badges (e.g., "Failed: Salary below minimum").

### 8.3 Job Detail Page (`/jobs/[id]`)

```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to Jobs                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Senior Scrum Master                          ♡ Favorite     │
│ Acme Corp · Austin, TX · Remote · Senior                    │
│ $140,000 - $160,000 USD                                     │
│ Posted 3 days ago · Discovered 2 days ago                   │
│ Also found on: LinkedIn, Indeed                             │
│ [View Original ↗]  [Apply ↗]                               │
│                                                             │
├──────────────────────────┬──────────────────────────────────┤
│                          │                                  │
│  Fit Score: 92 (High)    │  Stretch Score: 45 (Lateral)    │
│  ▸ Hard Skills    82/40% │  ▸ Target Role     30/50%       │
│  ▸ Experience     95/25% │  ▸ Target Skills   60/40%       │
│  ▸ Soft Skills    88/15% │  ▸ Growth          70/10%       │
│  ▸ Role Title     90/10% │                                  │
│  ▸ Location      100/10% │  Weights are read-only           │
│                          │                                  │
├──────────────────────────┴──────────────────────────────────┤
│                                                             │
│  Explanation                                                │
│  Strong technical fit — you have 4 of 5 required skills     │
│  including Python, PostgreSQL, and FastAPI. Kubernetes is    │
│  a stretch but aligns with your growth target.              │
│                                                             │
│  ✓ Strengths: Python, FastAPI, SQL, 7yr experience match    │
│  ⚠ Gaps: Kubernetes (required), Terraform (preferred)       │
│  ↗ Stretch: Kubernetes aligns with growth targets           │
│  ⓘ Warnings: (none)                                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Extracted Skills                                           │
│  Required: [Python] [PostgreSQL] [FastAPI] [Kubernetes]     │
│  Preferred: [Terraform] [Redis] [Docker]                    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Description                                                │
│  [Full job description text...]                             │
│                                                             │
│  Culture Signals                                            │
│  "Fast-paced, collaborative team focused on innovation..."  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ⚠ Ghost Risk: 35 (Moderate)                               │
│  Open 45 days · Reposted 1 time                            │
│                                                             │
│  🔄 Repost History                                          │
│  Previously posted on Jan 5. You applied and were rejected. │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Draft Materials]  [Dismiss]  [Mark as Expired]            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 8.4 Score Display Rules

| State | Display |
|-------|---------|
| Scored (fit_score not null) | Numeric score + tier label + color |
| Not scored (null) | "Not scored" badge — no number shown |
| Failed non-negotiables | "Filtered" badge + failure reasons expandable |
| Scoring in progress | Spinner + "Scoring..." |

**Tier labels and colors:**

| Score Type | Range | Label | Color |
|------------|-------|-------|-------|
| Fit | 90-100 | High | Green |
| Fit | 75-89 | Medium | Blue |
| Fit | 60-74 | Low | Amber |
| Fit | 0-59 | Poor | Red |
| Stretch | 80-100 | High Growth | Purple |
| Stretch | 60-79 | Moderate Growth | Blue |
| Stretch | 40-59 | Lateral | Gray |
| Stretch | 0-39 | Low Growth | Muted |

**Component drill-down:** Expandable section. Each component shows: name, individual score, weight percentage, and weighted contribution.

### 8.5 Non-Negotiables Filter Display

Jobs hidden by non-negotiables are excluded from the default list.

**"Show filtered jobs" toggle** in toolbar reveals them with:
- Dimmed row styling
- Red "Filtered" badge
- Expandable failure reasons: "Salary below minimum ($90k < $120k)", "Requires onsite — your preference is Remote Only"
- Undisclosed data warnings (amber): "Salary not disclosed", "Work model unknown"

### 8.6 Ghost Detection Display

| Score Range | Icon | Tooltip |
|-------------|------|---------|
| 0-25 | (none) | — |
| 26-50 | ⚠ (amber) | "Moderate ghost risk — posting may be stale" |
| 51-75 | ⚠ (orange) | "Elevated ghost risk — verify before applying" |
| 76-100 | ⚠ (red) | "High ghost risk — likely stale or fake" |

Detail page shows signal breakdown: days open, repost count, vagueness, missing fields.

### 8.7 Manual Job Ingest

"Add Job" button in toolbar → two-step modal:

**Step 1: Submit**
```
┌──────────────────────────────────────────┐
│ Add a Job Posting                        │
│                                          │
│ Source URL (optional):                   │
│ [https://linkedin.com/jobs/view/123]     │
│                                          │
│ Source name:                             │
│ [LinkedIn ▾]                             │
│                                          │
│ Job description text:                    │
│ ┌──────────────────────────────────────┐ │
│ │ Paste the full job description here  │ │
│ │                                      │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ [Cancel]            [Extract & Preview]  │
└──────────────────────────────────────────┘
```

Shows loading state while backend extracts.

**Step 2: Preview & Confirm**
```
┌──────────────────────────────────────────┐
│ Review Extracted Data                    │
│ Expires in 14:32                         │
│                                          │
│ Title:    [Senior Software Engineer   ]  │
│ Company:  [Acme Corp                  ]  │
│ Location: [San Francisco, CA          ]  │
│ Model:    [Hybrid ▾]                     │
│ Salary:   [$150,000] - [$200,000] [USD]  │
│                                          │
│ Extracted Skills:                        │
│ [Python ✓] [Kubernetes ✓] [AWS ✓]       │
│                                          │
│ [Cancel]                      [Confirm]  │
└──────────────────────────────────────────┘
```

All fields editable before confirmation. Token expiry countdown shown. On confirm: job saved, scoring queued, redirect to job detail.

**Error handling:**
- 422 EXTRACTION_FAILED: "Couldn't extract job details. Try pasting more of the description."
- 409 DUPLICATE_JOB: "This job is already in your list." + link to existing
- 410 TOKEN_EXPIRED: "Preview expired. Please resubmit."

### 8.8 Scouter Progress

**Manual trigger:** "Refresh Jobs" button in toolbar → `POST /api/v1/refresh`

**Progress:** Displayed in chat panel:
- "Searching Adzuna... Found 12 new jobs."
- "Scoring matches..."
- "Found 8 matches above your threshold. Top 3: [cards]"

**Background scan results:** Appear as chat messages next time user opens chat or as `data_changed` events that refresh the job list.

### 8.9 Expiration Handling

- `last_verified_at` shown on job detail: "Last verified 2 hours ago"
- "Mark as Expired" button in job detail actions
- Agent notification on auto-expire: chat message + `data_changed` event
- Expired jobs remain visible but with "Expired" badge; applied applications continue independently

---

## 9. Resume Management

**Surface area ref:** frontend_surface_area.md §5
**Backend refs:** REQ-002, REQ-006 §2.7/§5.2, REQ-007 §8, REQ-010 §4/§9

### 9.1 Resume List Page (`/resumes`)

```
┌─────────────────────────────────────────────────────────────┐
│ Your Resumes                              [+ New Resume]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ★ Scrum Master (Primary)          Active                │ │
│ │ Target: Scrum Master roles                              │ │
│ │ Last updated: 2 days ago                                │ │
│ │ 3 job variants (1 pending review)                       │ │
│ │ [View & Edit]  [Download PDF]  [Archive]                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │   Product Owner                       Active            │ │
│ │ Target: Product Owner / PM roles                        │ │
│ │ Last updated: 1 week ago                                │ │
│ │ 1 job variant                                           │ │
│ │ [View & Edit]  [Download PDF]  [Archive]                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Show archived resumes]                                     │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Resume Detail Page (`/resumes/[id]`)

Two sections: Base Resume editor and Job Variants list.

**Base Resume editor:**
- Summary (editable textarea)
- Included jobs with bullet selections (checkbox tree)
- Bullet ordering per job (drag-and-drop)
- Education, certifications, skills emphasis (checkbox lists)
- Primary toggle (one per persona)
- "Re-render PDF" button if selections changed since last render
- PDF preview (inline viewer or download)
- Approval status indicator

**Job Variants list:**
```
┌─────────────────────────────────────────────────────────────┐
│ Job Variants                                                │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 📄 Scrum Master at Acme Corp          Draft  ⏳        │ │
│ │ Created: 1 hour ago                                     │ │
│ │ [Review & Approve]  [Archive]                           │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 📄 Agile Coach at TechCo              Approved ✓       │ │
│ │ Approved: 3 days ago · Applied                          │ │
│ │ [View]  [Download PDF]                                  │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 Variant Review Page

When reviewing a Draft variant, show side-by-side comparison:

```
┌──────────────────────────────┬──────────────────────────────┐
│ Base Resume                  │ Tailored Variant             │
├──────────────────────────────┼──────────────────────────────┤
│ Summary:                     │ Summary:                     │
│ Experienced Scrum Master     │ Experienced Scrum Master     │
│ with 8 years...              │ with 8 years in [scaled      │
│                              │ Agile] environments...       │
│                              │                     ← diff   │
├──────────────────────────────┼──────────────────────────────┤
│ TechCorp bullets:            │ TechCorp bullets:            │
│ 1. Led team of 12            │ 1. Implemented SAFe ← moved  │
│ 2. Reduced cycle time        │ 2. Led team of 12            │
│ 3. Improved velocity         │ 3. Reduced cycle time        │
│ 4. Implemented SAFe          │ 4. Improved velocity         │
└──────────────────────────────┴──────────────────────────────┘

Agent Reasoning:
"Added emphasis on 'SAFe' and 'scaled Agile' — mentioned 3x in
posting. Moved SAFe implementation bullet to position 1."

[Approve]  [Regenerate]  [Archive]
```

**Diff highlighting:** Changed text highlighted with color. Moved bullets shown with position indicators.

**Guardrail violations** (if any): displayed as error banners above the approve button — must be resolved before approval.

### 9.4 Modification Guardrails Display

When a variant exceeds allowed boundaries:

```
┌──────────────────────────────────────────┐
│ ⚠ Guardrail Violation                    │
│                                          │
│ • Summary mentions skills not in your    │
│   profile: "Go", "Rust"                 │
│   → Add these skills to your Persona    │
│     first, or ask me to regenerate.     │
│                                          │
│ [Regenerate]  [Go to Persona]            │
└──────────────────────────────────────────┘
```

### 9.5 Upload and Download

**Resume upload** (during onboarding or persona update):
- `POST /api/v1/resume-files` (`multipart/form-data`)
- Client-side: file type validation (PDF/DOCX), size check (max 10MB)
- Show upload progress

**PDF download:**
- Base resume anchor: `GET /base-resumes/{id}/download`
- Submitted resume: `GET /submitted-resume-pdfs/{id}/download`
- Opens in browser PDF viewer or triggers download

---

## 10. Cover Letter Management

**Surface area ref:** frontend_surface_area.md §6
**Backend refs:** REQ-002b, REQ-006 §5.2, REQ-007 §8, REQ-010 §5/§7/§9

### 10.1 Cover Letter Access

Cover letters are accessed from the job detail page or application detail page — not from a standalone list page. They are always in the context of a specific job.

**Job detail page:** "Cover Letter" section shows the current letter status (Draft/Approved/None) with actions.

**Application detail page:** Shows the linked cover letter with download option.

### 10.2 Cover Letter Review

When a draft cover letter exists (auto-drafted or manually requested):

```
┌─────────────────────────────────────────────────────────────┐
│ Cover Letter for: Scrum Master at Acme Corp      Draft      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Agent Reasoning:                                            │
│ "Selected 'Turned around failing project' because it        │
│  demonstrates leadership under pressure, aligning with      │
│  the job's emphasis on 'driving results in ambiguity'."     │
│                                                             │
│ Stories Used:                                               │
│ • Turned around failing project (Leadership, Agile)         │
│ • Scaled Agile adoption (SAFe, Coaching)                    │
│ [Change stories...]                                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Dear Hiring Manager,                                    │ │
│ │                                                         │ │
│ │ I'm excited to apply for the Scrum Master role at       │ │
│ │ Acme Corp. In my current role at TechCorp, I recently   │ │
│ │ turned around a failing project by reorganizing sprint   │ │
│ │ cadences and implementing SAFe practices across three    │ │
│ │ teams...                                                │ │
│ │                                                         │ │
│ │ [Editable text area while in Draft status]              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Word count: 312 / 250-350 target  ✓                        │
│                                                             │
│ Voice: "Direct, confident" ✓                                │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Validation:                                                 │
│ ⚠ Company name not in opening paragraph (warning)          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ [Approve]  [Regenerate ↻]  [Archive]                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 Validation Display

Validation issues shown between the editor and action buttons:

| Severity | Style | Behavior |
|----------|-------|----------|
| Error | Red banner with ✗ icon | Blocks auto-presentation (system re-generates) |
| Warning | Amber notice with ⚠ icon | Shown but does not block approval |

Rules: `length_min` (error), `length_max` (warning), `blacklist_violation` (error), `company_specificity` (warning), `metric_accuracy` (error), `potential_fabrication` (warning).

Word count always shown with visual indicator (green if 250-350, amber if outside range).

### 10.4 Regeneration Feedback

"Regenerate" button opens a feedback panel:

```
┌──────────────────────────────────────────┐
│ Regeneration Feedback                    │
│                                          │
│ What would you like changed?             │
│ ┌──────────────────────────────────────┐ │
│ │ e.g., "Make it less formal" or      │ │
│ │ "Focus more on technical skills"    │ │
│ └──────────────────────────────────────┘ │
│ 0/500 characters                         │
│                                          │
│ Exclude stories:                         │
│ ☐ Turned around failing project          │
│ ☐ Scaled Agile adoption                  │
│                                          │
│ Quick options:                           │
│ [Shorter] [Longer] [More formal]         │
│ [Less formal] [More technical]           │
│ [Start fresh]                            │
│                                          │
│ [Cancel]              [Regenerate]       │
└──────────────────────────────────────────┘
```

Quick option chips populate the feedback text. "Start fresh" clears all context.

### 10.5 Story Override

"Change stories..." link opens a modal showing all achievement stories ranked by relevance:

```
┌──────────────────────────────────────────┐
│ Select Stories                           │
│                                          │
│ Currently selected:                      │
│ ✓ Turned around failing project  (92pt)  │
│ ✓ Scaled Agile adoption          (87pt)  │
│                                          │
│ Available:                               │
│ ☐ Built CI/CD pipeline           (71pt)  │
│ ☐ Mentored junior engineers      (65pt)  │
│ ☐ Migrated legacy system         (58pt)  │
│                                          │
│ [Cancel]              [Regenerate with selection] │
└──────────────────────────────────────────┘
```

Score shown for transparency. Selecting different stories triggers regeneration.

### 10.6 Approval and PDF Flow

1. User clicks "Approve" → `PATCH /cover-letters/{id}` with `status=Approved`
2. Editor becomes read-only. Regenerate button hidden.
3. "Download PDF" button appears → `GET /submitted-cover-letter-pdfs/{id}/download`
4. First download generates PDF; subsequent downloads return stored version
5. PDF linked to Application when user marks "Applied"

### 10.7 Unified Ghostwriter Review

When the Ghostwriter completes (both resume variant + cover letter), present a combined review experience:

```
┌─────────────────────────────────────────────────────────────┐
│ Materials for: Scrum Master at Acme Corp                    │
├─────────────────────────────────────────────────────────────┤
│ [Resume Variant]  [Cover Letter]            ← Tab nav      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ (Active tab content - variant review or cover letter review)│
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ [Approve Both]  [Approve Resume Only]  [Approve Letter Only]│
└─────────────────────────────────────────────────────────────┘
```

"Approve Both" is the primary action. Individual approvals available for partial review.

---

## 11. Application Tracking

**Surface area ref:** frontend_surface_area.md §7
**Backend refs:** REQ-004, REQ-006 §2.6/§5.2

### 11.1 Applications Page (`/applications`)

**Default view:** Table/list grouped by status.

**Desktop table columns:**

| Column | Content |
|--------|---------|
| Job Title | Title + company |
| Status | Badge with color |
| Interview Stage | Sub-badge (if Interviewing) |
| Applied Date | "X days ago" |
| Last Updated | "X days ago" |
| Actions | ⋮ menu |

**Status badge colors:**

| Status | Color |
|--------|-------|
| Applied | Blue |
| Interviewing | Amber |
| Offer | Green |
| Accepted | Green (bold) |
| Rejected | Red |
| Withdrawn | Gray |

**Toolbar:**
```
[Search...]  [Status: All ▾]  [Sort: Updated ↓ ▾]
[☐ Select]  [Show archived]
```

**Multi-select:** Enables bulk archive.

### 11.2 Application Detail Page (`/applications/[id]`)

```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to Applications                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Scrum Master at Acme Corp                                   │
│ Applied: Jan 15, 2026 · Status: Interviewing (Onsite)       │
│                                                             │
│ [Update Status ▾]  [Pin 📌]  [Archive]                     │
│                                                             │
├────────────────────────┬────────────────────────────────────┤
│                        │                                    │
│ Documents              │ Timeline                           │
│                        │                                    │
│ Resume:                │ ● Jan 25 — Interview completed     │
│ "Scrum Master" v1      │   (Onsite)                         │
│ [View] [Download]      │                                    │
│                        │ ● Jan 20 — Interview scheduled     │
│ Cover Letter:          │   (Onsite) "With VP of Eng"        │
│ Approved Jan 15        │                                    │
│ [View] [Download]      │ ● Jan 18 — Status changed          │
│                        │   Applied → Interviewing            │
│ Job Snapshot:          │                                    │
│ Captured Jan 15        │ ● Jan 15 — Applied                 │
│ [View snapshot]        │   via LinkedIn                      │
│ [View live posting ↗]  │                                    │
│                        │ [+ Add Event]                       │
├────────────────────────┴────────────────────────────────────┤
│                                                             │
│ Notes                                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Recruiter: Sarah (sarah@acme.com)                       │ │
│ │ Interview prep: Review SAFe framework details           │ │
│ │ [Edit]                                                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Offer Details (if status = Offer/Accepted)                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Base: $155,000 · Bonus: 15% · RSU: $50k/4yr            │ │
│ │ Start: Mar 1 · Deadline: Feb 15 (7 days) ⏰            │ │
│ │ Benefits: 401k 6%, unlimited PTO                        │ │
│ │ [Edit]                                                  │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 11.3 Status Transitions

**Status update dropdown** on the detail page:

| Current | Available Transitions |
|---------|-----------------------|
| Applied | Interviewing, Rejected, Withdrawn |
| Interviewing | Offer, Rejected, Withdrawn |
| Offer | Accepted, Rejected, Withdrawn |
| Accepted | (none — terminal) |
| Rejected | (none — terminal) |
| Withdrawn | (none — terminal) |

On selecting a transition:
- **→ Interviewing:** Prompt for interview stage (Phone Screen / Onsite / Final Round)
- **→ Offer:** Open offer details capture form (§11.5)
- **→ Rejected:** Open rejection details capture form (§11.6)
- **→ Accepted / Withdrawn:** Confirmation dialog, then transition

Terminal states disable the status dropdown.

### 11.4 "Mark as Applied" Flow

From job detail page with approved materials:

```
┌──────────────────────────────────────────┐
│ Ready to Apply                           │
│                                          │
│ 1. Download your materials:              │
│    [Download Resume PDF]                 │
│    [Download Cover Letter PDF]           │
│                                          │
│ 2. Submit at:                            │
│    [Apply on LinkedIn ↗]                 │
│                                          │
│ 3. Come back and confirm:               │
│    [I've Applied ✓]                      │
└──────────────────────────────────────────┘
```

"I've Applied" creates the Application, links PDFs, captures job snapshot, creates timeline event.

**One application per job:** If already applied, show "Already applied on [date]" with link to application.

### 11.5 Offer Details Form

Modal or inline form with all-optional fields:

| Field | Input | Notes |
|-------|-------|-------|
| Base salary | Currency input | With currency selector |
| Bonus | Percentage input | |
| Equity value | Currency input | |
| Equity type | Select (RSU/Options) | |
| Vesting years | Number | |
| Start date | Date picker | |
| Response deadline | Date picker | **Shown as countdown** in detail view |
| Benefits | Textarea | Free text |
| Notes | Textarea | e.g., "Negotiated from 140k" |

### 11.6 Rejection Details Form

Modal or inline form:

| Field | Input | Notes |
|-------|-------|-------|
| Stage | Select | Pre-populated from `current_interview_stage` |
| Reason | Text | e.g., "Culture fit concerns" |
| Feedback | Textarea | e.g., "Looking for more senior candidate" |
| When | Date/time | When rejection communicated |

### 11.7 Timeline

Chronological vertical timeline with event type icons:

| Event Type | Icon | Auto/Manual |
|------------|------|-------------|
| `applied` | 📤 | Auto |
| `status_changed` | 🔄 | Auto |
| `note_added` | 📝 | Auto |
| `interview_scheduled` | 📅 | Manual |
| `interview_completed` | ✓ | Manual |
| `offer_received` | 🎉 | Auto |
| `offer_accepted` | 🏆 | Auto |
| `rejected` | ✗ | Auto |
| `withdrawn` | ↩ | Auto |
| `follow_up_sent` | 📧 | Manual |
| `response_received` | 📨 | Manual |
| `custom` | 💬 | Manual |

**"Add Event" button** opens a form:
- Event type selector (manual types only)
- Description (text)
- Interview stage (if interview event)
- Date/time

**Timeline events are immutable** — no edit or delete UI. Users add clarifying events instead.

### 11.8 Follow-up Suggestions

Agent-driven, surfaced in chat: "It's been 7 days since your onsite at Acme. Want me to draft a follow-up?"

No dedicated UI needed — the chat panel handles this. Users record follow-ups via "Add Event" → `follow_up_sent`.

### 11.9 Pin and Archive

| Action | UI Element | Effect |
|--------|------------|--------|
| Pin | 📌 toggle on detail page | Excluded from auto-archive |
| Archive | Button on detail page or bulk action | Hidden from default view |
| Restore | Button in archived view | Returns to active view |
| Hard delete | Button in archived view (with confirmation) | Permanent removal |

"Show archived" toggle in list toolbar reveals archived applications.

### 11.10 Job Snapshot Display

Expandable section on application detail page showing frozen job data at application time. Shows all captured fields. Includes `captured_at` timestamp.

If live job posting still exists: "View live posting ↗" link alongside snapshot.
If live posting changed or disappeared: snapshot is the authoritative record.

---

## 12. Settings & Configuration

**Surface area ref:** frontend_surface_area.md §8
**Backend refs:** REQ-003 §4.2b, REQ-006 §6, REQ-007 §11

### 12.1 Settings Page Layout (`/settings`)

```
┌─────────────────────────────────────────────────────────────┐
│ Settings                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Job Sources                                                 │
│ ┌───────────────────────────────────────────────┐           │
│ │ ✓ Adzuna          Good US/UK coverage  [⠿]   │           │
│ │ ✓ The Muse        Curated companies    [⠿]   │           │
│ │ ✓ RemoteOK        Remote-focused       [⠿]   │           │
│ │ ✓ USAJobs         US federal jobs      [⠿]   │           │
│ │ — Chrome Ext.     (Not installed)      [⠿]   │           │
│ └───────────────────────────────────────────────┘           │
│ [⠿] = drag handle for reordering                           │
│                                                             │
│ Agent Configuration                                         │
│ ┌───────────────────────────────────────────────┐           │
│ │ Model routing (read-only):                    │           │
│ │ • Chat/Onboarding: Sonnet                     │           │
│ │ • Scouter/Ghost detection: Haiku              │           │
│ │ • Scoring/Generation: Sonnet                  │           │
│ │                                               │           │
│ │ Provider: Local (Claude SDK)                   │           │
│ └───────────────────────────────────────────────┘           │
│                                                             │
│ About                                                       │
│ Zentropy Scout v0.1.0 · AGPL-3.0                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 Job Source Preferences

- Toggle switch per source (enable/disable)
- Drag-and-drop reorder
- Source description tooltip
- System-inactive sources shown grayed out
- API: `GET /api/v1/job-sources` + `GET/PATCH /api/v1/user-source-preferences`

### 12.3 Discovery Preferences

Covered in §7.2.9 (Persona → Discovery Preferences editor). Not duplicated in settings.

### 12.4 Authentication (Future)

MVP: No auth settings. Section placeholder: "Single-user mode — no configuration needed."

Future: Provider selection (OAuth, email/password), API key management (BYOK mode).

---

## 13. Shared Components & Design System

### 13.1 Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | Blue-600 | Primary actions, links |
| `--destructive` | Red-600 | Delete, errors |
| `--success` | Green-600 | Approved, success states |
| `--warning` | Amber-500 | Warnings, moderate ghost |
| `--muted` | Gray-400 | Secondary text, disabled |
| `--background` | White / Gray-950 | Page background (light/dark) |
| `--card` | White / Gray-900 | Card backgrounds |
| `--border` | Gray-200 / Gray-800 | Borders |

**Typography:** System font stack. Body: 14px. Headings: 16-24px.

**Spacing:** 4px base unit. Padding: 16px (cards), 24px (sections), 32px (page).

**Dark mode:** Supported via Tailwind `dark:` variants and CSS variables. Toggle in settings (future) or OS preference.

### 13.2 Common Form Patterns

**Validation:** Inline errors below each field on blur. Form-level error summary on submit failure. Client-side via Zod; server errors mapped to fields.

**Optimistic updates:** For toggle actions (favorite, pin). Immediate UI feedback; rollback on error.

**Loading states:** Skeleton components for data loading. Disabled inputs during submission. Spinner on buttons during async operations.

**Error display:** Toast notifications for action results (success/failure). Inline errors for form validation. Banner for systemic issues (SSE disconnect, API down).

### 13.3 Table/List Component

Used for jobs, applications, resumes. Features:
- Column sorting (click header, toggle asc/desc)
- Column filtering (dropdown per column)
- Pagination (page selector, per-page: 20/50/100)
- Multi-select with checkbox column
- Row click → navigate to detail page
- Responsive: table on desktop, card list on mobile

### 13.4 PDF Viewer

Inline PDF preview component for resume and cover letter review:
- Renders PDF in an iframe or using a lightweight viewer (e.g., react-pdf)
- Zoom in/out controls
- Download button
- Full-screen toggle
- Fallback: direct download link if viewer fails

### 13.5 Notification/Toast System

**Trigger sources:**
- API success/failure responses (mutations)
- SSE `data_changed` events (for resources the user is currently viewing)
- Agent action results

**Toast variants:**

| Variant | Color | Duration | Example |
|---------|-------|----------|---------|
| Success | Green | 3 seconds | "Job favorited" |
| Error | Red | Persistent (dismiss) | "Failed to save. Please retry." |
| Warning | Amber | 5 seconds | "Your match profile is updating..." |
| Info | Blue | 5 seconds | "3 new jobs discovered" |

### 13.6 Loading States

| State | Component | Behavior |
|-------|-----------|----------|
| Initial page load | Skeleton screen | Gray placeholder shapes matching expected layout |
| Data refetch | Subtle loading indicator | Small spinner in header/corner; existing data remains visible |
| Long-running LLM operation | Progress message in chat | "Drafting your cover letter..." (5-30 seconds) |
| File upload | Progress bar | Percentage-based progress |
| Action pending | Button spinner | Button disabled with spinner icon |

### 13.7 Error States

| State | Display |
|-------|---------|
| No data yet (empty) | Illustration + "No [items] yet" + action prompt |
| Loading failed | "Failed to load. [Retry]" with error code |
| Partial data | Show what loaded; error badge on failed sections |
| Not found (404) | "This [item] doesn't exist. [Go back]" |
| Conflict (409) | "This was modified. [Refresh]" |

### 13.8 Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Keyboard navigation | All interactive elements focusable, Tab order logical |
| Screen reader | ARIA labels on icons, live regions for SSE updates |
| Color contrast | WCAG 2.1 AA (4.5:1 text, 3:1 UI components) |
| Focus management | Focus trapped in modals, restored on close |
| Motion | `prefers-reduced-motion` respected for animations |
| Announcements | Toast notifications announced via `aria-live="polite"` |

shadcn/ui components (built on Radix) handle most accessibility requirements by default.

### 13.9 Offline/Reconnection

| Scenario | Behavior |
|----------|----------|
| SSE disconnects | Status indicator changes; auto-reconnect with backoff |
| Tab inactive > 5 min | Close SSE; reconnect + full refresh on return |
| API request fails (network) | Toast error; retry button; TanStack Query retry (3 attempts) |
| API returns 5xx | Toast with "Server error. Please retry." |

No offline-first functionality in MVP. App requires active API connection.

---

## 14. Design Decisions

| # | Decision | Rationale | Alternatives Considered |
|---|----------|-----------|-------------------------|
| 1 | Chat-first interaction model | PRD §7.2: "primary interaction method" | Form-only (rejected: less flexible) |
| 2 | TanStack Query for server state | Best REST caching + SSE invalidation; optimistic updates; multi-tenant ready | SWR (lighter but less mutation support), Server Actions (poor SSE fit) |
| 3 | shadcn/ui component library | Accessible Radix primitives + Tailwind; own the code; no runtime CSS-in-JS | Fully custom (too much a11y work), MUI (wrong styling paradigm) |
| 4 | Single SSE connection | Simpler than WebSocket; sufficient for server→client push; browser-native | WebSocket (overkill for one-way), Polling (too latent) |
| 5 | Fit and Stretch scores independent | REQ-008 §7.3 cancellation: users have different search modes; no combined judgment | 2x2 matrix (cancelled) |
| 6 | URL-based filter/sort state | Shareable, back-button friendly, restores on refresh | Client-only state (lost on navigation) |
| 7 | Mobile-first responsive | Tailwind convention; ensures mobile works; desktop adds complexity | Desktop-first (mobile afterthought) |
| 8 | Verbose agent progress | REQ-007 §13.2: builds trust; users want to see agents working | Minimal progress (rejected: feels like black box) |

---

## 15. Open Questions

| # | Question | Impact | Proposed Resolution |
|---|----------|--------|---------------------|
| 1 | Max resume upload size? | File upload validation | Proposed: 10MB (REQ-002 §10) |
| 2 | Max application notes length? | Textarea limits | Proposed: 10,000 chars (REQ-004 §12) |
| 3 | Chat panel position: right sidebar vs bottom drawer? | Layout for all pages | Proposed: right sidebar (more space for conversation) |
| 4 | Dark mode: ship in MVP or defer? | Design tokens, testing | Proposed: defer; support OS preference only |
| 5 | Offer comparison view: dedicated page or inline? | Multi-offer users | Proposed: inline comparison on applications page |
| 6 | PDF viewer: inline (react-pdf) or browser native (iframe)? | Bundle size, compatibility | Proposed: browser native iframe (simpler, 0 bundle cost) |

---

## 16. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-08 | 0.1 | Initial draft — all sections |

---

## Appendix A: Backend Prerequisites

Issues identified during the surface area audit (Phase 0) that must be resolved before or during frontend implementation.

### A.1 Missing Application Pin/Archive Columns

**Problem:** REQ-002 §5.4 says Applications can be pinned and archived, but no `is_pinned` or `archived_at` columns exist on the `applications` table.

**Resolution:** Add `is_pinned: bool` (default false) and `archived_at: timestamp` (nullable) via migration. Matches existing pattern on BaseResume, JobVariant, CoverLetter.

### A.2 Timeline Event Immutability vs API Stubs

**Problem:** REQ-004 §9 declares timeline events immutable, but PATCH/DELETE stubs exist in the backend.

**Resolution:** Frontend treats timeline as append-only. Backend stubs should return 405 or be removed.

### A.3 Score Components Not Stored

**Problem:** FitScoreResult, StretchScoreResult, and ScoreExplanation are computed by service layer but not persisted. Only aggregate scores are columns.

**Resolution:** Store components and explanation in a JSONB column (`score_details`) on `job_postings`, populated at scoring time.

### A.4 Weight Configuration Deferred

**Status:** Deferred to v2 per REQ-008 §12. Frontend shows weights as read-only.

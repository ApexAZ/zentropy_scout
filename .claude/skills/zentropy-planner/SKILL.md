---
name: zentropy-planner
description: |
  Plan creation AND progress tracking for Zentropy Scout. ALWAYS load this skill when:
  - Creating a new implementation plan or adding tasks to an existing plan
  - Starting work on any implementation task
  - Completing a subtask
  - Resuming after context compaction or new session
  - Someone asks "where are we", "what's the status", or "create a plan"
  - Any task hint includes "plan"
autoload: true
triggers:
  - plan
  - implementing
  - phase
  - subtask
  - complete
  - done
  - finished
  - resume
  - continue
  - status
  - progress
  - create a plan
  - new feature
---

# Zentropy Planner — Plan Creation & Progress Tracking

---

## Part 1: Plan Creation

### Prerequisites: Requirements First

Plans implement requirements. Before creating a plan:

1. **Check if a REQ document exists** — `Glob "docs/requirements/REQ-*.md"` and search for the topic
2. **If no REQ exists** — Draft one with the user. Requirements live in `docs/requirements/` and are protected by a settings.json hook (the user must approve writes). Format: follow existing REQ documents as a template. The user may also create REQ documents outside of Claude Code.
3. **If a REQ exists** — Use `req-reader` to load the relevant sections before planning

Plans without requirements lead to scope creep. Always have a REQ to reference.

### When to Create a Plan

Use EnterPlanMode when adding new features, phases, or multi-task work. Every plan should follow the format below. Reference existing plans in `docs/plan/` for examples.

### Plan File Requirement (CRITICAL)

**Every plan MUST be persisted to `docs/plan/<name>_plan.md` BEFORE any implementation begins.** This is non-negotiable because:
1. The session start checklist (Step 3) discovers active plans via `Glob "docs/plan/*_plan.md"`
2. After context compaction, the plan file is the ONLY way to find the current task
3. The Claude Code task list (`TaskCreate`/`TaskUpdate`) is supplementary tracking — NOT a replacement

**If the user provides a plan inline (in a message, JSONL transcript, or other non-file format):**
1. Write it to `docs/plan/<name>_plan.md` first
2. Audit it against the REQ (via `req-reader`) and prior plan patterns before starting
3. Only then begin implementation

**Never start implementation without a plan file on disk.**

### Plan Format

Every phase in a plan must include these sections:

#### 1. Phase Header

```markdown
## Phase N: Phase Name

**Status:** ⬜ Incomplete

*Brief description of what this phase accomplishes and why.*
```

#### 2. Workflow Table

Tells the implementer which skills, subagents, and tools to use for this phase:

```markdown
#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-0XX §Y.Z |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-db` for migrations, `zentropy-api` for endpoints |
| ✅ **Verify** | `pytest -v`, `npm test`, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |
```

#### 3. Task Table with Hints

```markdown
#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | Description of what to implement | `skill1, skill2, plan` | ⬜ |
```

### Choosing Hints (CRITICAL)

Hints trigger skill auto-loading during implementation. **Before finalizing any plan, cross-reference the skills table in CLAUDE.md** and select keywords that match skill triggers.

#### Hint Reference

| Hint Keyword | Triggers Skill | Use When Task Involves |
|--------------|---------------|----------------------|
| `db` | zentropy-db | Database, migrations, schema, pgvector |
| `api` | zentropy-api | Endpoints, routers, response models |
| `tdd` / `test` | zentropy-tdd | Writing tests, TDD cycle, mocks, fixtures |
| `security` | security-reviewer | Auth, input validation, OWASP, injection |
| `provider` | zentropy-provider | LLM calls, Claude API, embeddings |
| `agents` | zentropy-agents | LangGraph, state machines, HITL |
| `lint` | zentropy-lint | Ruff, ESLint, Prettier, type checking |
| `playwright` / `e2e` | zentropy-playwright | E2E tests, UI testing, browser automation |
| `commands` | zentropy-commands | Docker, alembic, npm, CLI operations |
| `ui` | ui-reviewer | Brand palette, colors, elevation, typography, spacing, interactive states, accessibility |
| `plan` | zentropy-planner | Always include — triggers this skill |

**Rules:**
- Every task MUST include `plan` as a hint (triggers progress tracking)
- Include `tdd` or `test` for any task that creates or modifies code
- Include `security` for any task handling user input, auth, or external data
- Include `ui` for any task that creates or modifies frontend UI components (`.tsx` files)
- Include `e2e` / `playwright` at phase boundaries where UI behavior changes
- When in doubt, include the hint — loading an extra skill is cheap, missing one is expensive

### Task Sizing

- Each task = one unit of work = one commit
- Sized to fit within ~150k context window (including reading specs, TDD, reviewing)
- **Never combine multiple subtasks into one** — if a task seems too big, break it down further
- This prevents auto-compaction mid-implementation and ensures progress is captured

### Phase-Level Considerations

- **Every major phase MUST end with a test-runner task** — runs full backend + frontend + E2E suite as a gate before the next phase
- Add an E2E/Playwright task at phase boundaries when UI behavior changes
- Reference the specific REQ document section each task implements

#### Phase-End Test Gate Example

The last task in every phase should be a **phase gate** — uses the "Workflow: Phase Gate" process (see Part 2 below):
```markdown
| § | Task | Hints | Status |
|---|------|-------|--------|
| N | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ⬜ |
```
This task uses the `test-runner` subagent in **Full mode**. No feature code is written — it's a quality gate that verifies all subtask work and pushes to remote.

#### qa-reviewer (Automatic)

The `qa-reviewer` subagent runs automatically during step 4 (DISCOVERY) on every subtask. It does NOT need a plan hint — it's built into the workflow. It assesses whether the subtask's changes need new Playwright E2E tests and recommends them if so.

**qa-reviewer → plan task chain:**
1. qa-reviewer recommends E2E test(s) during DISCOVERY (step 4)
2. In RESOLUTION (step 5), mark the finding as "✅ Tracked" (not "✅ Fixed")
3. Add the recommended test as a **new task** in the plan, inserted before the next phase gate
4. The new task gets `playwright, e2e, plan` hints
5. The task is implemented in its own subtask cycle (TDD → review → commit)
6. Phase gate verifies it passes with the full E2E suite

---

## Part 2: Progress Tracking

### CRITICAL RULE

**After completing ANY subtask, you MUST update the plan file.**

This is non-negotiable because:
1. It helps the user understand progress
2. It helps YOU resume after context compaction
3. It provides checkpoints for new sessions
4. It's the single source of truth for project status

### Status Icons

| Icon | Meaning | When to Use |
|------|---------|-------------|
| ⬜ | Incomplete | Not started |
| 🟡 | In Progress | Currently working on |
| ✅ | DONE | Completed and verified |

### Workflow: Subtask (commit only, no push)

```
1. BEFORE starting
   → Use `req-reader` subagent to load the relevant REQ section
   → Read the workflow table for this phase (has skill hints)

2. START subtask
   → Update status to 🟡 in the active plan file

3. DO the work (TDD cycle)
   → Write failing test first
   → Write code to make it pass
   → Refactor if needed
   → Run affected tests only (files listed in task description)

4. REVIEW — PHASE 1: DISCOVERY
   → Run in parallel:
     - `bandit <modified_files> -f txt`
     - `gitleaks detect`
     - `code-reviewer` subagent — list modified file paths in prompt
     - `security-reviewer` subagent — list modified file paths AND specify
       which reference sections to load based on the routing table:
         app/agents/         → [LLM] + [BACKEND]
         app/providers/      → [LLM] + [BACKEND]
         app/api/, services/ → [BACKEND] (+ [OWASP] for endpoints)
         app/repositories/, models/ → [DATABASE]
         app/schemas/        → [BACKEND]
         sanitize/prompt/feedback keywords → [LLM]
       Example prompt: "Review backend/app/agents/ghostwriter_prompts.py —
       load [LLM] + [BACKEND] from security-references.md"
     - `qa-reviewer` subagent — list modified file paths, assesses whether
       new Playwright E2E tests are needed for user-visible changes
     - `ui-reviewer` subagent (for frontend subtasks only) — list modified
       `.tsx` file paths, audits brand palette compliance, elevation, typography,
       interactive states, and accessibility
   → STOP and enumerate ALL findings in a structured table:

     ## Review Findings
     | # | Source            | Severity | Finding                    |
     |---|-------------------|----------|----------------------------|
     | 1 | code-reviewer     | Medium   | TypedDicts defined unused  |
     | 2 | security-reviewer | Low      | No input size validation   |
     | 3 | bandit            | Low      | Assert used in production  |
     | 4 | qa-reviewer       | Info     | New E2E: skill editor flow |
     | 5 | ui-reviewer       | Major    | Hardcoded text-amber-500   |

   → If 0 findings → Skip to step 7 (COMPLETE)
   → If 1+ findings → MUST proceed to Phase 2 (step 5)

5. REVIEW — PHASE 2: RESOLUTION (required if any findings)
   → For EACH finding in the table:
     a) State: "Fixing finding #N: [description]"
     b) Implement the fix (TDD if code change — write test first)
     c) Mark resolution in table
   → Produce resolution table:

     ## Resolutions
     | # | Finding                    | Resolution              | Status   |
     |---|----------------------------|-------------------------|----------|
     | 1 | TypedDicts defined unused  | Updated function sigs   | ✅ Fixed   |
     | 2 | No input size validation   | Added _MAX_SKILLS check | ✅ Fixed   |
     | 3 | Assert used in production  | Changed to raise        | ✅ Fixed   |
     | 4 | New E2E: skill editor flow | Added as plan task §X.Y | ✅ Tracked |

   → ALL rows MUST show "✅ Fixed" or "✅ Tracked" before proceeding
   → qa-reviewer recommendations are resolved by adding them as new plan tasks
     before the next phase gate (not by writing E2E tests inline)
   → To defer ANY finding → use AskUserQuestion to get explicit approval
   → NO "acknowledged" or "will fix later" without user consent

6. REVIEW — PHASE 3: VERIFICATION
   → Re-run automated tools on modified files:
     - `bandit <modified_files> -f txt`
     - `ruff check <modified_files>`
   → Self-verify subagent findings by reading the fixed code:
     - State: "Finding #N: [desc] → Fixed by [change] → Verified at [file:line]"
   → Run affected tests to catch regressions
   → Produce verification summary:

     ## Verification
     | Tool/Finding      | Result                          |
     |-------------------|---------------------------------|
     | bandit            | ✅ No issues                    |
     | ruff              | ✅ All checks passed            |
     | Finding #1        | ✅ Verified at hard_skills:185  |
     | Finding #2        | ✅ Verified at hard_skills:188  |
     | pytest            | ✅ 42 passed (affected files)   |

   → If automated tools still report issues → return to Phase 2
   → If all clear → proceed to COMPLETE

7. COMPLETE subtask
   → Update status to ✅ in the active plan file
   → COMMIT immediately (code + plan update) — no push

8. STOP (MANDATORY)
   → Do NOT push — pushes happen only at phase gates
   → Use AskUserQuestion tool with options:
     - "Continue to next subtask" — Keep working on the next task
     - "Compact first" — Reduce context, provide compact summary (see template above)
     - "Stop for now" — End session
   → DO NOT proceed until user responds
   → This is a HARD STOP — not optional
```

### Workflow: Phase Gate (full quality gate + push)

Phase gates are the last task in each phase (e.g., §4, §8, §12, §18, §20). They verify all subtask work before pushing.

```
1. RUN full quality gate (use test-runner in Full mode)
   → cd backend && pytest -v
   → cd frontend && npm run test:run
   → cd frontend && npx playwright test
   → cd backend && ruff check .
   → cd frontend && npm run lint
   → cd frontend && npm run typecheck

2. FIX any regressions
   → If failures: check `git log` to identify which subtask introduced the issue
   → Fix and COMMIT the fix
   → Re-run full gate until all green

3. UPDATE plan
   → Mark phase gate task ✅
   → Update phase Status line to ✅ Complete (if all tasks done)
   → COMMIT the plan update

4. PUSH to remote
   → `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push` (SSH keep-alive needed — pre-push hooks ~5min cause timeout without it)
   → All unpushed subtask commits + gate fixes + plan update go to remote

5. STOP (MANDATORY)
   → Use AskUserQuestion tool with options:
     - "Continue to next phase" — Start the next phase
     - "Compact first" — Reduce context before next phase
     - "Stop for now" — End session
   → DO NOT proceed until user responds
```

**Why push only at phase gates:** Pushing triggers pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates. Trade-off: unpushed commits exist only locally between gates.

**CRITICAL RULES:**
- Invoke `req-reader` BEFORE starting work
- Run all review tools in parallel during DISCOVERY phase
- **NEVER skip findings** — every finding must be fixed or explicitly deferred with user approval
- **Structured tables are mandatory** — forces enumeration, prevents hand-waving
- Commit after EVERY subtask — but do NOT push (pushes happen only at phase gates)
- Do NOT batch commits
- Do NOT auto-push — subtasks commit only; phase gates handle push

### How to Update the Plan

The implementation plan has tables like:

```markdown
| § | Task | Hints | Status |
|---|------|-------|--------|
| 8 | Extensions Required (pgvector) | `db, commands, tdd` | ⬜ |
```

Change the status column:

```markdown
| § | Task | Hints | Status |
|---|------|-------|--------|
| 8 | Extensions Required (pgvector) | `db, commands, tdd` | ✅ |
```

### Compact Summary Template

When providing a compaction summary (user selects "Compact first"), use this format:

```
## Compaction Summary

**Plan:** docs/plan/<plan_file>.md
**Completed:** Phase X, §Y — <task title>
**Next:** Phase X, §Z — <task title>
**Pushed:** Yes/No (unpushed commits: <list commit hashes if any>)
**Blockers:** None / <describe any issues>
**Decisions:** <any in-flight decisions the next session needs to know>
```

### On Session Start / After Compaction

1. Discover the active plan file:
   - Use `Glob "docs/plan/*_plan.md"` to find all plan files
   - Read each to find the one with 🟡 or ⬜ tasks (active work)
   - Or ask the user which plan is in scope
2. Find the first 🟡 (in progress) or ⬜ (incomplete) task
3. Resume from there
4. Announce: "Resuming at Phase X.Y, Task §Z"

### Phase-Level Updates

When ALL subtasks in a phase section are ✅:
- Update the phase **Status:** line from `⬜ Incomplete` to `✅ Complete`

### Commit Convention

When committing plan updates:
```
docs(plan): mark Phase 1.1 §8 complete - pgvector extension
```

Or batch with code:
```
feat(db): add pgvector extension migration

- Enable pgvector and pgcrypto extensions
- docs(plan): mark §8 complete
```

### Quick Reference

**Plan locations:** Discover via `Glob "docs/plan/*_plan.md"` or ask the user which plan is active.

**Update triggers:**
- Subtask started → 🟡
- Subtask completed → ✅
- Phase completed → Update phase Status line

**Never forget:** The plan is your persistent memory. Update it religiously.

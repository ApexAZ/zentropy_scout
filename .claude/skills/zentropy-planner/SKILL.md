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

### When to Create a Plan

Use EnterPlanMode when adding new features, phases, or multi-task work. Every plan should follow the format established in `docs/plan/implementation_plan.md` and `docs/plan/frontend_implementation_plan.md`.

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
| `plan` | zentropy-planner | Always include — triggers this skill |

**Rules:**
- Every task MUST include `plan` as a hint (triggers progress tracking)
- Include `tdd` or `test` for any task that creates or modifies code
- Include `security` for any task handling user input, auth, or external data
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

The last task in every phase should be:
```markdown
| § | Task | Hints | Status |
|---|------|-------|--------|
| N | Run full test suite (backend + frontend + E2E) | `plan` | ⬜ |
```
This task uses the `test-runner` subagent to run all tests. No code is written — it's a verification gate.

#### qa-reviewer (Automatic)

The `qa-reviewer` subagent runs automatically during step 4 (DISCOVERY) on every subtask. It does NOT need a plan hint — it's built into the workflow. It assesses whether the subtask's changes need new Playwright E2E tests and recommends them if so. Any recommended E2E tests become new tasks added to the plan.

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

### Workflow: Every Subtask

```
1. BEFORE starting
   → Use `req-reader` subagent to load the relevant REQ section
   → Read the workflow table for this phase (has skill hints)

2. START subtask
   → Update status to 🟡 in implementation_plan.md

3. DO the work (TDD cycle)
   → Write failing test first
   → Write code to make it pass
   → Refactor if needed
   → Run full test suite

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
   → STOP and enumerate ALL findings in a structured table:

     ## Review Findings
     | # | Source            | Severity | Finding                    |
     |---|-------------------|----------|----------------------------|
     | 1 | code-reviewer     | Medium   | TypedDicts defined unused  |
     | 2 | security-reviewer | Low      | No input size validation   |
     | 3 | bandit            | Low      | Assert used in production  |
     | 4 | qa-reviewer       | Info     | New E2E: skill editor flow |

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
     (not by writing E2E tests inline — they are separate tasks)
   → To defer ANY finding → use AskUserQuestion to get explicit approval
   → NO "acknowledged" or "will fix later" without user consent

6. REVIEW — PHASE 3: VERIFICATION
   → Re-run automated tools on modified files:
     - `bandit <modified_files> -f txt`
     - `ruff check <modified_files>`
   → Self-verify subagent findings by reading the fixed code:
     - State: "Finding #N: [desc] → Fixed by [change] → Verified at [file:line]"
   → Run `pytest` to catch regressions
   → Produce verification summary:

     ## Verification
     | Tool/Finding      | Result                          |
     |-------------------|---------------------------------|
     | bandit            | ✅ No issues                    |
     | ruff              | ✅ All checks passed            |
     | Finding #1        | ✅ Verified at hard_skills:185  |
     | Finding #2        | ✅ Verified at hard_skills:188  |
     | pytest            | ✅ 1430 passed                  |

   → If automated tools still report issues → return to Phase 2
   → If all clear → proceed to COMPLETE

7. COMPLETE subtask
   → Update status to ✅ in implementation_plan.md
   → COMMIT immediately (code + plan update)

8. STOP (MANDATORY)
   → Use AskUserQuestion tool with options:
     - "Push and compact (Recommended)" — Push to remote, provide summary, user will compact
     - "Continue to next task" — Keep working without break
     - "Compact first, then continue" — Reduce context without pushing
     - "Stop for now" — End session without pushing
   → DO NOT proceed until user responds
   → This is a HARD STOP — not optional
   → If user selects "Push and compact": push, then provide a compaction summary
```

**CRITICAL RULES:**
- Invoke `req-reader` BEFORE starting work
- Run all review tools in parallel during DISCOVERY phase
- **NEVER skip findings** — every finding must be fixed or explicitly deferred with user approval
- **Structured tables are mandatory** — forces enumeration, prevents hand-waving
- Commit after EVERY subtask
- Do NOT batch commits
- Do NOT auto-push — use the STOP checkpoint to let user choose

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

### On Session Start / After Compaction

1. Read the relevant plan file:
   - Backend: `docs/plan/implementation_plan.md`
   - Frontend: `docs/plan/frontend_implementation_plan.md`
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

**Plan locations:**
- Backend: `docs/plan/implementation_plan.md`
- Frontend: `docs/plan/frontend_implementation_plan.md`

**Update triggers:**
- Subtask started → 🟡
- Subtask completed → ✅
- Phase completed → Update phase Status line

**Never forget:** The plan is your persistent memory. Update it religiously.

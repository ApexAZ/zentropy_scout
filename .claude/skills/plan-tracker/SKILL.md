---
name: plan-tracker
description: |
  Progress tracking for implementation plan. ALWAYS load this skill when:
  - Starting work on any implementation task
  - Completing a subtask
  - Resuming after context compaction or new session
  - Someone asks "where are we" or "what's the status"
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
---

# Plan Tracker — Implementation Progress

## CRITICAL RULE

**After completing ANY subtask, you MUST update `docs/plan/implementation_plan.md`.**

This is non-negotiable because:
1. It helps the user understand progress
2. It helps YOU resume after context compaction
3. It provides checkpoints for new sessions
4. It's the single source of truth for project status

## Why Tasks Are Small

**Tasks are intentionally granular to fit within the ~150k context window.**

Each subtask is sized so that:
- You can complete it fully before auto-compaction triggers
- Context isn't lost mid-implementation
- The plan captures progress even if compaction happens
- New sessions can resume cleanly from any checkpoint

**Never combine multiple subtasks into one.** If a task seems too big, break it down further rather than risking incomplete work from context overflow.

## Status Icons

| Icon | Meaning | When to Use |
|------|---------|-------------|
| ⬜ | Incomplete | Not started |
| 🟡 | In Progress | Currently working on |
| ✅ | DONE | Completed and verified |

## Workflow: Every Subtask

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
   → STOP and enumerate ALL findings in a structured table:

     ## Review Findings
     | # | Source            | Severity | Finding                    |
     |---|-------------------|----------|----------------------------|
     | 1 | code-reviewer     | Medium   | TypedDicts defined unused  |
     | 2 | security-reviewer | Low      | No input size validation   |
     | 3 | bandit            | Low      | Assert used in production  |

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
     | 1 | TypedDicts defined unused  | Updated function sigs   | ✅ Fixed |
     | 2 | No input size validation   | Added _MAX_SKILLS check | ✅ Fixed |
     | 3 | Assert used in production  | Changed to raise        | ✅ Fixed |

   → ALL rows MUST show "✅ Fixed" before proceeding
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

## How to Update the Plan

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

## On Session Start / After Compaction

1. Read `docs/plan/implementation_plan.md`
2. Find the first 🟡 (in progress) or ⬜ (incomplete) task
3. Resume from there
4. Announce: "Resuming at Phase X.Y, Task §Z"

## Phase-Level Updates

When ALL subtasks in a phase section are ✅:
- Update the phase **Status:** line from `⬜ Incomplete` to `✅ Complete`

Example:
```markdown
### 1.1 Database Schema (REQ-005)
**Status:** ✅ Complete
```

## Commit Convention

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

## Quick Reference

**Plan location:** `docs/plan/implementation_plan.md`

**Update triggers:**
- Subtask started → 🟡
- Subtask completed → ✅
- Phase completed → Update phase Status line

**Never forget:** The plan is your persistent memory. Update it religiously.

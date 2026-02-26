---
name: reflect
description: |
  Self-improvement system for capturing lessons learned. Invoke this skill when:
  - A mistake was made and you want to prevent it in the future
  - You discover a pattern that should become a rule
  - Someone says "remember this", "add a lesson", "we learned", or "never do X again"
  - After debugging a tricky issue that has a generalizable prevention
---

# Reflect: Self-Improvement System

## Purpose

Capture mistakes and insights as "Always/Never" rules in CLAUDE.md to prevent future occurrences. This creates a feedback loop where errors become documented patterns.

## When to Use

Invoke this skill when:
- A bug was caused by forgetting a project convention
- You discover an undocumented pattern that should be explicit
- A mistake took significant time to debug
- The same type of error has happened before

## Process

### Step 1: Root Cause Analysis

Before formulating a rule, identify:
1. **What happened?** — The specific mistake or issue
2. **Why did it happen?** — The underlying cause (not just symptoms)
3. **How was it discovered?** — Test failure, runtime error, review feedback
4. **Is it generalizable?** — Will this help prevent similar issues?

### Step 2: Formulate the Rule

Rules must follow this format:
```
- [category] Always/Never [action] because [reason].
```

**Categories:** `[db]`, `[api]`, `[testing]`, `[providers]`, `[agents]`, `[frontend]`, `[general]`

Examples:
- `[db] Always check REQ-005 before generating database migrations because schema definitions live there.`
- `[testing] Never mock the repository layer in integration tests because it defeats the purpose.`
- `[api] Always return 404 (not 400) for missing resources because it follows REST conventions.`

**Keep rules:**
- One line only
- Actionable (specific verb)
- Justified (includes "because")

### Step 3: Check for Duplicates

Before adding, scan the existing "## Learned Lessons" section in CLAUDE.md:
- If the rule already exists → skip
- If a similar rule exists → consider merging or refining
- If new → append

### Step 4: Append to CLAUDE.md

Add the new rule to the "## Learned Lessons" section, above the `<!-- Add new lessons above this line -->` marker.

### Step 5: Confirm (No Auto-Commit)

Tell the user:
- What rule was added
- Which category it belongs to

**Commit timing:** If you're mid-subtask, fold the CLAUDE.md change into the subtask commit (no separate commit needed). If you're between tasks, commit it standalone: `git commit -am "docs: add learned lesson [category]"`

---

## Graduation to Skills

When 3+ lessons accumulate in a category, consider "graduating" them:

1. User notices clustering and says "Graduate the [db] lessons"
2. Move the lessons into the appropriate skill (e.g., `zentropy-db`)
3. Remove them from Learned Lessons
4. Commit both changes together

This keeps CLAUDE.md lean while preserving knowledge in skills.

---

## Example Session

**User:** "I just spent 20 minutes debugging because I forgot to run migrations after pulling. Add a lesson."

**Claude (using reflect skill):**

1. **Root cause:** Schema changes in REQ-005 weren't reflected in local DB
2. **Rule:** `[db] Always run `alembic upgrade head` after pulling changes because schema may have changed.`
3. **Check:** No duplicate in Learned Lessons
4. **Append:** Added to CLAUDE.md
5. **Confirm:** "Added lesson. Commit when ready: `git commit -am "docs: add learned lesson [db]"`"

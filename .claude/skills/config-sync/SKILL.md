---
name: config-sync
description: |
  Ensures CLAUDE_TOOLS.md stays in sync with actual configuration. Load this skill when:
  - Creating, modifying, or deleting skills
  - Creating, modifying, or deleting subagents
  - Changing hooks in settings.json
  - Someone says "update documentation", "sync config", or "update CLAUDE_TOOLS"
  - After any changes to .claude/ directory
---

# Configuration Sync Protocol

When you modify anything in `.claude/`, you MUST update `CLAUDE_TOOLS.md` to match.

---

## Triggers

Update CLAUDE_TOOLS.md after ANY of these actions:

| Action | Update Required |
|--------|-----------------|
| Create a skill | Add to directory structure, skills table, context table |
| Delete a skill | Remove from directory structure, skills table, context table |
| Modify a skill | Update line count in context table |
| Create a subagent | Add to directory structure, subagents table |
| Delete a subagent | Remove from directory structure, subagents table |
| Modify a subagent | Update description in subagents table |
| Change settings.json hooks | Update hooks table |
| Change settings.json permissions | Update permissions section |

---

## Update Checklist

When updating CLAUDE_TOOLS.md, verify all sections:

### 1. Directory Structure
```
.claude/
├── settings.json
├── agents/
│   └── [all agents listed]
└── skills/
    └── [all skills listed with brief description]
```

### 2. Skills Overview Table
| Skill | Triggers On | What It Provides |
|-------|-------------|------------------|
| Every skill listed | Trigger keywords | Brief description |

### 3. Context Efficiency Table
| Source | Lines | Loaded |
|--------|-------|--------|
| Every skill with accurate line count | X | On-demand |

To get line counts:
```bash
wc -l .claude/skills/*/SKILL.md
```

### 4. Subagents Table
| Agent | Triggers On | Tools | Purpose |
|-------|-------------|-------|---------|
| Every agent listed | Keywords | Tool list | Brief purpose |

### 5. Hooks Table
| Hook | Event | Trigger | Action |
|------|-------|---------|--------|
| Every hook listed | Event type | Matcher | What it does |

### 6. Architecture Summary
- Update skill count: `SKILLS (N)`
- Update subagent count if changed
- Verify descriptions match current state

### 7. Metadata
- Update `*Last updated: YYYY-MM-DD*` at bottom

---

## CLAUDE.md Sync

Also update `CLAUDE.md` if the change affects:

| Changed | Update in CLAUDE.md |
|---------|---------------------|
| New skill | Add to "Skills Available" table |
| Deleted skill | Remove from "Skills Available" table |
| New subagent | Add to "Subagents Available" table |
| Deleted subagent | Remove from "Subagents Available" table |

---

## Quick Line Count Command

```bash
# Get all skill line counts
for f in .claude/skills/*/SKILL.md; do
  name=$(dirname "$f" | xargs basename)
  lines=$(wc -l < "$f")
  echo "| $name | $lines | On-demand |"
done
```

---

## Post-Update Verification

After updating, verify:

- [ ] Directory structure matches actual `.claude/` contents
- [ ] All skills appear in skills table
- [ ] All subagents appear in subagents table
- [ ] Line counts are accurate
- [ ] Hooks table matches `settings.json`
- [ ] Total line count is sum of all skills + CLAUDE.md
- [ ] Architecture summary counts are correct
- [ ] Last updated date is today

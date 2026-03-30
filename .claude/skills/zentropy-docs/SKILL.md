---
name: zentropy-docs
description: |
  Documentation conventions for Zentropy Scout. Load when:
  - Writing docstrings or code comments
  - Someone asks about "docstring", "documentation", or "comments"
---

# Zentropy Scout Documentation Conventions

## Docstrings

### When Required
- All public functions/methods
- All classes
- Complex private functions

### When to Skip
- Obvious CRUD methods (`get_by_id`, `create`, `delete`)
- Test functions (name should be self-documenting)
- Private helpers under 5 lines

### Format: Google Style

```python
async def extract_skills(
    job_description: str,
    llm: LLMProvider,
) -> ExtractionResult:
    """Extract skills and requirements from a job posting.

    Uses the configured LLM provider to parse job description text
    and return structured skill data.

    Args:
        job_description: Raw text of the job posting.
        llm: LLM provider instance for extraction.

    Returns:
        ExtractionResult containing required_skills, preferred_skills,
        and culture_text.

    Raises:
        ExtractionError: If LLM fails to return valid structured output.
    """
```

### Class Docstrings

```python
class PersonaRepository:
    """Repository for Persona database operations.

    Handles CRUD operations and specialized queries for the
    personas table. Uses async SQLAlchemy sessions.

    Attributes:
        session: AsyncSession for database operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
```

## Comments Philosophy

### Good Comments

```python
# Truncate to 15k chars — Haiku context limit for extraction tasks
truncated = raw_text[:15000]

# NOTE: pgvector requires list[float], not numpy array
embedding = embedding_array.tolist()

# HACK: Workaround for SQLAlchemy 2.0 async session issue
# See: https://github.com/sqlalchemy/sqlalchemy/issues/1234
await session.refresh(instance)
```

### Bad Comments

```python
# BAD: Describes what code does (obvious from reading)
# Loop through skills and add to list
for skill in skills:
    result.append(skill)

# BAD: Outdated comment
# Returns a list of three items  <-- actually returns dict now
return {"a": 1, "b": 2}

# BAD: Commented-out code (delete it, git has history)
# old_value = calculate_old_way(x)
new_value = calculate_new_way(x)
```

### Comment Types

| Prefix | Use |
|--------|-----|
| `# NOTE:` | Important context or non-obvious behavior |
| `# HACK:` | Workaround with link to issue/docs |
| `# FIXME:` | Known problem to address (with issue #) |
| `# TODO:` | **Avoid** — either fix it or create an issue |

## TypeScript/JSDoc

```typescript
/**
 * Fetches persona data from the API.
 *
 * @param id - The persona UUID
 * @returns The persona object or null if not found
 * @throws {ApiError} If the request fails
 */
async function getPersona(id: string): Promise<Persona | null> {
  // ...
}
```

## TypeScript File-Level Headers

Every non-test `.ts` and `.tsx` file must begin with a file-level JSDoc header. This is distinct from per-function docs — it orients an LLM reading the file cold, without needing to open any other file.

### Required Template
```typescript
/**
 * @fileoverview [One sentence: what this file does]
 *
 * Layer: [page | layout | component | hook | context-provider | lib/utility | type-definitions]
 * Feature: [persona | jobs | resume | chat | applications | usage | admin | shared]
 *
 * Coordinates with:
 * - [relative/path/to/file]: [why — e.g., "calls apiGet for persona data"]
 * - [relative/path/to/file]: [why — e.g., "consumed by PersonaOverview to render editor"]
 *
 * Called by / Used by:
 * - [relative/path/to/file]: [context]
 */
```

### Three-Axis Pass/Fail Test

All three axes must pass before a header is acceptable:

- ✅ **What**: The `@fileoverview` line answers "what does this file do" as a standalone sentence — no file tree needed
- ✅ **Where**: `Layer:` + `Feature:` places it in the system without reading directory structure
- ✅ **With**: `Coordinates with:` names specific files by relative path and explains *why* each relationship exists — not just "uses X", but what X provides

### When to Skip

- Test files (`*.test.ts`, `*.test.tsx`)
- shadcn-generated UI primitives in `components/ui/` that are thin Radix wrappers with no custom logic

### Example — Good
```typescript
/**
 * @fileoverview Bridges SSE events to TanStack Query cache invalidation.
 *
 * Layer: lib/utility
 * Feature: shared
 *
 * Coordinates with:
 * - lib/sse-provider.tsx: subscribes to the SSE event stream it provides
 * - lib/query-keys.ts: uses query key constants to target specific cache entries
 * - lib/query-client.ts: calls queryClient.invalidateQueries() on matching keys
 *
 * Called by / Used by:
 * - lib/sse-provider.tsx: instantiated inside SSEProvider on mount
 */
```

### Example — Bad (fails all three axes)
```typescript
/**
 * SSE query bridge utilities.
 */
```

## README Files

Each major directory should have a brief README if the purpose isn't obvious:

```markdown
# app/providers/

External service integrations.

## Structure
- `llm/` - Language model providers (Claude SDK, Anthropic API)
- `embedding/` - Text embedding providers (OpenAI)

## Adding a Provider
1. Create class implementing the base interface
2. Add to provider factory in `__init__.py`
3. Update config to support new provider type
```

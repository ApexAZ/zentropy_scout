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

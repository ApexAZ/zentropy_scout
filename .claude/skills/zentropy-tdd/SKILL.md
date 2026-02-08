---
name: zentropy-tdd
description: |
  Test-Driven Development enforcement for Zentropy Scout. Load this skill when:
  - Creating new components, services, repositories, or features
  - Someone says "implement", "create", "build", or "add feature"
  - Writing tests or discussing test strategy
  - Someone asks about "TDD", "red-green-refactor", or "test first"
---

# TDD Enforcement Protocol

## Core Principle

**Never write implementation code without a failing test first.**

This skill enforces the "Red-Green-Refactor" cycle for every logical component.

---

## Behavior Over Implementation

**Test WHAT code does, not HOW it does it.** Tests should verify observable behavior from the perspective of the code's users (callers, API consumers), not internal implementation details.

### Good vs Bad Tests

```python
# GOOD: Tests behavior - what the caller cares about
def test_extraction_tasks_use_cheaper_model():
    """Extraction should route to a cost-effective model."""
    adapter = ClaudeAdapter(config)
    model = adapter.get_model_for_task(TaskType.EXTRACTION)
    assert "haiku" in model.lower()  # Behavior: cheaper model selected

# BAD: Tests implementation - brittle, will break on refactor
def test_routing_dict_has_nine_entries():
    """Don't test internal data structure sizes."""
    assert len(DEFAULT_ROUTING) == 9  # Ties test to implementation detail
```

### When Implementation Details Matter

Sometimes implementation IS the behavior. Test implementation when:

- **Performance guarantees** - "Must use O(1) lookup" → test that a dict/set is used
- **Security requirements** - "Must use constant-time comparison" → test the algorithm
- **Contractual obligations** - "Must call audit log before delete" → test call order
- **Resource constraints** - "Must stream, not buffer" → test memory usage

If in doubt, ask: "Would a user/caller care if I changed this?" If no, don't test it.

### When Tests Should Change

- ✅ **Change tests when**: Behavior requirements change
- ❌ **Don't change tests when**: Refactoring internals (tests should still pass)

If refactoring breaks tests, the tests were likely testing implementation, not behavior.

---

## TDD Protocol

You must strictly follow the "Red-Green-Refactor" cycle for every logical component:

### 1. RED (The Specification)

* Create the test file `tests/unit/test_[component].py` BEFORE creating the component implementation.
* The test must define the *Public Interface* and *Expected Behavior*.
* **Rule:** Do not test internal implementation details (e.g., private methods). Test inputs and outputs/side-effects.
* Run the test using `pytest`. It MUST fail (ImportError or AssertionError).

```python
# tests/unit/test_persona_service.py
import pytest
from app.services.persona import PersonaService  # Does not exist yet!

@pytest.mark.asyncio
async def test_create_persona_extracts_skills():
    """PersonaService should extract skills from raw text."""
    service = PersonaService(mock_llm, mock_repo)

    result = await service.create_from_text("I am a Python developer with 5 years experience")

    assert result.id is not None
    assert "Python" in [s["name"] for s in result.skills]
```

### 2. GREEN (The Implementation)

* Write the minimum code in `src/...` (or `app/...`) to satisfy the test.
* Run the test. It MUST pass.
* **Do not over-engineer.** Only write what the test requires.

```python
# app/services/persona.py
class PersonaService:
    def __init__(self, llm, repo):
        self.llm = llm
        self.repo = repo

    async def create_from_text(self, text: str) -> Persona:
        # Minimum implementation to pass the test
        skills = await self.llm.extract_skills(text)
        persona = await self.repo.create(PersonaCreate(skills=skills))
        return persona
```

### 3. REFACTOR (The Cleanup)

* Now apply linting and optimization.
* Run `ruff check . && ruff format .`
* Verify tests still pass: `pytest -v`
* Add docstrings if missing.

---

## Decision Matrix: Unit vs. Integration vs. Functional

| Question | Test Type | Tools |
|----------|-----------|-------|
| Is it pure logic? (parsing, validation, transformation) | **Unit Test** | Pytest + mocks |
| Does it talk to the database? | **Integration Test** | Pytest + Docker DB |
| Does it call external APIs? (LLM, embeddings) | **Integration Test** | Pytest + mock provider |
| Does it involve user flow/UI? | **Functional Test** | Playwright |
| Is it an API endpoint? | **Integration Test** | Pytest + httpx AsyncClient |

---

## Test File Organization

```
backend/tests/
├── unit/                    # Pure logic, fully mocked
│   ├── test_extraction.py
│   └── test_scoring.py
├── integration/             # Real DB, mocked externals
│   ├── test_persona_repository.py
│   └── test_api_personas.py
└── conftest.py              # Shared fixtures
```

---

## TDD Checklist (Before Implementation)

Before writing ANY implementation code, verify:

- [ ] Test file exists at correct path
- [ ] Test imports the module that will be created
- [ ] Test defines expected inputs and outputs
- [ ] Test has been run and FAILED (Red)
- [ ] Failure is ImportError or AssertionError (not syntax error)

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Correct Approach |
|--------------|--------------|------------------|
| Writing implementation first | No specification, untested code | Write test first |
| Testing private methods | Brittle tests, implementation coupling | Test public interface only |
| Testing framework internals | Not your code | Test your code's behavior |
| 100% coverage as goal | Coverage ≠ quality | Cover critical paths and edge cases |
| Mocking everything | Tests pass but code is broken | Use real DB for integration tests |

---

## Handling Stub Implementations

When creating stubs during TDD (e.g., abstract interface with adapter stubs pending implementation):

### Unused Parameters in Stubs

Stubs often have parameters they don't use yet. Handle lint errors properly:

1. **Prefer underscore prefix** over `noqa` comments:
   ```python
   # ✅ Good - Pythonic convention for intentionally unused
   async def complete(self, _messages, _task, _max_tokens=None):
       raise NotImplementedError("Implementation in §4.2")

   # ❌ Avoid - noqa hides the issue
   async def complete(self, messages, task, max_tokens=None):  # noqa: ARG002
       raise NotImplementedError("Implementation in §4.2")
   ```

2. **If you must use noqa**, track it in `implementation_plan.md`:
   ```markdown
   | 4.2 | Implement Adapter | `provider, tdd` ⚠️ Remove noqa from adapter.py (added in §4.1) | ⬜ |
   ```

3. **Never leave untracked bypasses** - they become permanent technical debt

### Why This Matters

- Underscore prefix is self-documenting and lint-compliant
- Tracked bypasses get cleaned up when the dependent task runs
- Untracked bypasses accumulate and become "mystery code"

---

## Workflow Summary

```
1. THINK   → What should this component do? (Inputs → Outputs)
2. TEST    → Write test defining that behavior
3. RUN     → pytest (must FAIL)
4. CODE    → Minimum implementation
5. RUN     → pytest (must PASS)
6. CLEAN   → ruff format, docstrings
7. RUN     → pytest (still PASS)
8. COMMIT  → "feat(component): add X with tests"
```

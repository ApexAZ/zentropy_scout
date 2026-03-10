---
name: zentropy-tdd
description: |
  Test-Driven Development and testing patterns for Zentropy Scout. Load this skill when:
  - Creating new components, services, repositories, or features
  - Writing unit tests, integration tests, or test fixtures
  - Setting up pytest, conftest.py, or test databases
  - Mocking LLM providers or external services
  - Running tests or checking coverage
  - Debugging test failures or flaky tests
  - Someone says "implement", "create", "build", or "add feature"
  - Someone asks about "test", "pytest", "mock", "fixture", "coverage", "hypothesis", or "TDD"
---

# TDD & Testing Patterns

## Core Philosophy

**Test WHAT code does, not HOW it does it.** See CLAUDE.md "Testing Philosophy" for full rationale and examples.

**Decision criterion:** "Would this test still pass if I rewrote the implementation using a completely different internal structure but preserved the same external behavior?" YES = behavioral (good). NO = structural (bad).

**Exception — test implementation when:**
- **Performance guarantees** — "Must use O(1) lookup"
- **Security requirements** — "Must use constant-time comparison"
- **Contractual obligations** — "Must call audit log before delete"
- **High production risk** — Wrong model name sent to external API = silent billing/quality issue that no behavioral test can catch

---

## TDD Protocol: Red-Green-Refactor

**Never write implementation code without a failing test first.**

### 1. RED (The Specification)

Create test file BEFORE the implementation. Define public interface and expected behavior.

```python
# tests/unit/test_persona_service.py
from app.services.persona import PersonaService  # Does not exist yet!

@pytest.mark.asyncio
async def test_create_persona_extracts_skills():
    service = PersonaService(mock_llm, mock_repo)
    result = await service.create_from_text("I am a Python developer with 5 years experience")
    assert result.id is not None
    assert "Python" in [s["name"] for s in result.skills]
```

Run the test — it MUST fail (ImportError or AssertionError).

### 2. GREEN (The Implementation)

Write **minimum code** to satisfy the test. Do not over-engineer.

### 3. REFACTOR (The Cleanup)

Apply linting, add docstrings, run `ruff check . && ruff format .`, verify tests still pass.

### TDD Checklist

Before writing ANY implementation code:
- [ ] Test file exists at correct path
- [ ] Test imports the module that will be created
- [ ] Test defines expected inputs and outputs
- [ ] Test has been run and FAILED (Red)
- [ ] Failure is ImportError or AssertionError (not syntax error)

---

## Decision Matrix

| Question | Test Type | Tools |
|----------|-----------|-------|
| Pure logic? (parsing, validation) | **Unit Test** | Pytest + mocks |
| Invariant for ALL inputs? (sanitization) | **Property Test** | Pytest + Hypothesis |
| Database interaction? | **Integration Test** | Pytest + Docker DB |
| External APIs? (LLM, embeddings) | **Integration Test** | Pytest + mock provider |
| User flow/UI? | **Functional Test** | Playwright |
| API endpoint? | **Integration Test** | Pytest + httpx AsyncClient |

---

## Test Quality Checklist

Before marking a test complete:
1. **Behavior focus** — Would a caller/user care about this assertion?
2. **Meaningful** — Does it catch real bugs, not just raise coverage?
3. **Readable** — Can someone understand intent without reading implementation?
4. **Independent** — Passes/fails regardless of test execution order?
5. **Clear name** — Uses `test_<behavior>_when_<condition>` format?
6. **No companions** — Is this behavior already tested elsewhere? If yes, don't write a duplicate — either strengthen the existing test or skip this one.

---

## Test Bloat Patterns

Every test must justify its existence: **"What real bug would this test catch that no other test catches?"** If the answer is "nothing," it's bloat. These are the patterns that produce bloat — never write them.

### Structural Assertion Patterns (conftest.py hook detects some)

| Banned Pattern | Why It's Wrong | What to Do Instead |
|----------------|----------------|-------------------|
| `isinstance(result, T)` | Tests return type, not behavior | Assert on the result's value or properties |
| `issubclass(Foo, Bar)` | Tests inheritance chain | Test that `Foo` exhibits `Bar`'s behavioral contract |
| `hasattr(obj, "field")` | Tests attribute existence | Call the attribute and assert on its behavior |
| `callable(obj)` | Tests callable status | Call the function and assert on its return value |
| `get_type_hints(Cls)` / `dataclasses.fields(Cls)` | Tests schema shape | Construct instances and assert on behavior |
| `"method" in Cls.__abstractmethods__` | Tests ABC internals | Test that concrete subclasses implement the method |
| `CONSTANT == 42` / `enum.value == "literal"` | Duplicates the source code | Test behavior that depends on the constant's value |
| `len(some_enum) == N` | Breaks when enum grows | Test specific members that matter for behavior |

### Behavioral Bloat Patterns (not auto-detected)

| Pattern | Example | Why It's Bloat | Fix |
|---------|---------|----------------|-----|
| **Constructor mirror** | `obj = Foo(x=1)` → `assert obj.x == 1` | Tests that Python assignment works, not business logic. Was the #1 bloat source in the 2026-03 audit (drove most of 225 deletions). | DELETE if constructor just assigns. KEEP if constructor validates/transforms (e.g., `Entry(score=101)` → `raises ValueError` tests validation behavior, not assignment) |
| **Pass-through mock** | `mock.return_value = X` → `assert result == X` | The mock guarantees the test passes — it can never fail | If the function transforms/filters/branches on the result, assert on that. If it's pure delegation with no logic, DELETE the test — there's nothing to break |
| **Default-value mirror** | `assert config.timeout == 30` | Mirrors Pydantic/ORM default; duplicates source code | Test behavior that depends on the default (e.g., "request times out after default period") |
| **Mock-only assertion** | `mock.assert_called_once_with(args)` as sole assertion | Tests wiring, not behavior; breaks on any refactor | Add output/result assertions; mock call checks are supplementary, never primary |
| **caplog-only test** | `assert "Processing" in caplog.text` | Logging is developer convenience, not a contract; fragile to rewording | DELETE unless log message is part of a monitoring/alerting contract |
| **`is not None` sole assertion** | `assert result is not None` | Redundant when companion tests assert on properties of result | DELETE if companions exist; if no companions, add real assertions instead |
| **Subsumed/duplicate** | Same code path tested identically in two places | One test can never catch a bug the other misses | DELETE the less specific test; keep the one with richer assertions |

### Approved Exception: Frozen-Test Pattern

When verifying immutability, test through the public API (`replace()`), not Python's freeze mechanism:

```python
# GOOD: Tests immutability through public API
def test_result_preserves_original_on_copy():
    result = SomeResult(field="value")
    updated = replace(result, field="new")
    assert result.field == "value"   # Original unchanged
    assert updated.field == "new"    # Copy has new value
```

---

## Evaluating Existing Tests

When auditing or reviewing tests, follow this evaluation process:

1. **Read the test.** What does it assert?
2. **Read the source function.** Is the assertion testing behavior or echoing implementation?
3. **Check for companions.** Does another test already cover this behavior more thoroughly?
4. **Apply the refactor test.** Would this test still pass after a complete reimplementation that preserves external behavior?

### Dispositions

| Disposition | When to Use |
|-------------|-------------|
| **KEEP** | Actually valuable — tests real behavior, no companion covers it |
| **DELETE** | No value, no refactor path, companion covers the behavior |
| **REFACTOR** | Currently tests implementation but COULD test behavior instead |
| **CONSOLIDATE** | Multiple tests that should be one parametrized test |

---

## Test Setup Reference

All test infrastructure lives in `backend/tests/conftest.py`. Key fixtures:

- **`db_engine`** — Function-scoped, creates/drops all tables per test
- **`db_session`** — Function-scoped async session with rollback on teardown
- **`mock_llm`** — `MockLLMProvider` with pre-configured responses, injected into factory
- **`mock_embedding`** — `MockEmbeddingProvider` (768-dim vectors), injected into factory
- **`client`** — Authenticated `AsyncClient` with JWT cookie, DB override, auth enabled
- **`test_user`** / **`test_persona`** / **`test_job_source`** — Standard test data

Before writing a new test file, **always read an existing sibling test file** in the same directory to match the exact mock setup pattern, fixture usage, and naming conventions.

### File Organization

```
backend/tests/
├── conftest.py              # Shared fixtures (read this first)
├── unit/                    # Pure logic + API endpoint tests
└── fixtures/                # Test data files
```

---

## Property-Based Testing with Hypothesis

Use Hypothesis for testing invariants that must hold for ANY input. Especially valuable for security-sensitive code like sanitization.

```python
from hypothesis import given, settings
from hypothesis import strategies as st

unicode_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0, max_size=500,
)

@given(unicode_text)
@settings(max_examples=500)
def test_sanitize_idempotent(text: str) -> None:
    once = sanitize_llm_input(text)
    twice = sanitize_llm_input(once)
    assert once == twice
```

| Scenario | Approach |
|----------|----------|
| Specific known inputs -> expected outputs | Example-based (pytest) |
| Invariants across all possible inputs | Property-based (Hypothesis) |
| Security: no forbidden patterns in output | Property-based (Hypothesis) |
| Regression: specific bug reproduction | Example-based (pytest) |

Key rules: use `assume()` to discard invalid inputs, pre-compile regex at module level, use `st.sampled_from()` for injection-adjacent characters. See `backend/tests/unit/test_llm_sanitization_fuzz.py` for examples.

---

## Handling Stubs During TDD

Prefer underscore prefix over `noqa` for unused stub parameters:

```python
# Good
async def complete(self, _messages, _task, _max_tokens=None):
    raise NotImplementedError("Implementation in next task")

# Avoid
async def complete(self, messages, task, max_tokens=None):  # noqa: ARG002
    raise NotImplementedError("Implementation in next task")
```

If you must use noqa, track it in the active plan file for cleanup.

---

## Workflow Summary

```
1. THINK   -> What should this component do?
2. TEST    -> Write test defining that behavior
3. RUN     -> pytest (must FAIL)
4. CODE    -> Minimum implementation
5. RUN     -> pytest (must PASS)
6. CLEAN   -> ruff format, docstrings
7. RUN     -> pytest (still PASS)
8. COMMIT  -> "feat(component): add X with tests"
```

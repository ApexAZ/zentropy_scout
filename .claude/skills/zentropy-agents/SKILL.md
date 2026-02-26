---
name: zentropy-agents
description: |
  LangGraph agent patterns for Zentropy Scout. Load this skill when:
  - Implementing Chat, Onboarding, Scouter, Strategist, or Ghostwriter agents
  - Working with state schemas, checkpointing, or HITL patterns
  - Defining graph nodes, edges, or routing functions
  - Someone mentions "agent", "LangGraph", "graph", "state", or "HITL"
---

# LangGraph Agent Patterns

> **Deprecation Notice (2026-02-24):** The LLM redesign is replacing Scouter, Strategist, Ghostwriter, and Onboarding LangGraph graphs with plain async service classes. After the redesign, only the **Chat Agent** will use LangGraph. The graph patterns, state schemas, and routing examples below still apply to Chat Agent but are no longer relevant for the other four agents. See the active implementation plan for details.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              Chat Agent (main entry)                 │
│  • Receives user messages                           │
│  • Routes to tools or sub-graphs                    │
│  • Streams responses via SSE                        │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   Onboarding      Scouter     Ghostwriter
      Agent                       Agent
                      │
                      ▼
                 Strategist
                   Agent
                      │
                      ▼
                    API
```

**Key principle:** Agents are API clients. All writes go through REST endpoints.

---

## Base State Schema

All agents extend this common state:

```python
from typing import TypedDict, Optional, List

class BaseAgentState(TypedDict):
    # User context
    user_id: str
    persona_id: str

    # Conversation
    messages: List[dict]
    current_message: Optional[str]

    # Tool execution
    tool_calls: List[dict]
    tool_results: List[dict]

    # Control flow
    next_action: Optional[str]
    requires_human_input: bool
    checkpoint_reason: Optional[str]
```

---

## Graph Structure Pattern

```python
from langgraph.graph import StateGraph, END

# 1. Define state
class MyAgentState(BaseAgentState):
    custom_field: Optional[str]

# 2. Create graph
graph = StateGraph(MyAgentState)

# 3. Add nodes (functions that process state)
graph.add_node("step_one", step_one_fn)
graph.add_node("step_two", step_two_fn)

# 4. Set entry point
graph.set_entry_point("step_one")

# 5. Add edges (linear or conditional)
graph.add_edge("step_one", "step_two")
graph.add_edge("step_two", END)

# 6. Compile
compiled = graph.compile()
```

---

## Node Functions

Nodes receive state and return updated state:

```python
async def step_one(state: MyAgentState) -> MyAgentState:
    """Process step one.

    Args:
        state: Current agent state.

    Returns:
        Updated state with results.
    """
    result = await do_something(state["user_id"])

    # Return state updates (merged automatically)
    return {
        "custom_field": result,
        "next_action": "step_two",
    }
```

---

## Conditional Routing

```python
def route_by_condition(state: MyAgentState) -> str:
    """Route to next node based on state."""
    if state.get("error"):
        return "handle_error"
    if state.get("needs_input"):
        return "wait_for_input"
    return "continue_processing"

graph.add_conditional_edges(
    "check_condition",
    route_by_condition,
    {
        "handle_error": "error_node",
        "wait_for_input": "input_node",
        "continue_processing": "next_node",
    }
)
```

---

## HITL Checkpointing

**When to checkpoint:**

| Trigger | Behavior |
|---------|----------|
| Approval needed | Pause, notify user, wait |
| Clarification needed | Ask question, wait for answer |
| Long-running task | Checkpoint periodically |
| Error/uncertainty | Pause, explain, ask for guidance |

**Implementation:**

```python
async def wait_for_input(state: MyAgentState) -> MyAgentState:
    """Pause graph for human input."""
    return {
        "requires_human_input": True,
        "checkpoint_reason": "Waiting for user approval",
    }

# Graph checks this and pauses
graph.add_conditional_edges(
    "some_node",
    lambda s: "wait" if s.get("requires_human_input") else "continue",
    {
        "wait": END,  # Checkpoints here
        "continue": "next_node",
    }
)
```

**Resume from checkpoint:**

```python
# Load checkpoint and continue with user response
state = load_checkpoint(checkpoint_id)
state["user_response"] = user_input
state["requires_human_input"] = False
result = await graph.ainvoke(state)
```

---

## Tool Calling (API Wrappers)

Tools are thin wrappers around API endpoints:

```python
from typing import Callable

def make_tool(name: str, endpoint: str, method: str = "GET") -> Callable:
    """Create a tool that calls an API endpoint."""

    async def tool(state: BaseAgentState, **kwargs) -> dict:
        """Tool docstring shown to LLM."""
        async with httpx.AsyncClient() as client:
            if method == "GET":
                resp = await client.get(f"/api/v1{endpoint}", params=kwargs)
            elif method == "POST":
                resp = await client.post(f"/api/v1{endpoint}", json=kwargs)
            elif method == "PATCH":
                resp = await client.patch(f"/api/v1{endpoint}", json=kwargs)
            return resp.json()

    tool.__name__ = name
    return tool

# Example tools
favorite_job = make_tool("favorite_job", "/job-postings/{id}", "PATCH")
list_jobs = make_tool("list_jobs", "/job-postings", "GET")
```

---

## Sub-Graph Invocation

```python
async def delegate_to_ghostwriter(state: ChatAgentState) -> ChatAgentState:
    """Invoke Ghostwriter as sub-graph."""
    ghostwriter_state = GhostwriterState(
        job_posting_id=state["target_job_id"],
        persona_id=state["persona_id"],
        user_id=state["user_id"],
    )

    result = await ghostwriter_graph.ainvoke(ghostwriter_state)

    return {
        "tool_results": state["tool_results"] + [{
            "tool": "ghostwriter",
            "result": result,
        }]
    }
```

---

## Error Handling in Agents

```python
async def safe_node(state: MyAgentState) -> MyAgentState:
    """Node with error handling."""
    try:
        result = await risky_operation()
        return {"result": result}
    except TransientError as e:
        # Retry with backoff
        return {"retry_count": state.get("retry_count", 0) + 1}
    except PermanentError as e:
        # Surface to user
        return {
            "error": str(e),
            "requires_human_input": True,
            "checkpoint_reason": f"Error: {e}",
        }
```

---

## Agent-Specific Patterns

### Chat Agent
- Entry point for all user interaction
- Routes to tools or sub-graphs
- Streams responses via SSE

```python
chat_graph.add_conditional_edges(
    "classify_intent",
    route_by_intent,
    {
        "tool_call": "select_tools",
        "onboarding": "delegate_onboarding",
        "ghostwriter": "delegate_ghostwriter",
        "clarification_needed": "request_clarification",
        "direct_response": "generate_response",
    }
)
```

### Onboarding Agent
- Linear interview flow with HITL pauses
- Persists `onboarding_step` for resume

```python
ONBOARDING_STEPS = [
    "resume_upload",
    "basic_info",
    "work_history",
    "skills",
    "achievement_stories",
    "non_negotiables",
    "voice_profile",
    "base_resume_setup",
]
```

### Scouter Agent
- Parallel source fetching (fan-out/fan-in)
- Invokes Strategist after saving jobs

```python
# Fan-out to sources
graph.add_conditional_edges(
    "get_sources",
    get_enabled_sources,  # Returns list of source names
    {source: f"fetch_{source}" for source in ALL_SOURCES}
)

# Fan-in to merge
for source in ALL_SOURCES:
    graph.add_edge(f"fetch_{source}", "merge_results")
```

### Strategist Agent
- Embedding freshness check (prevents cold start)
- Auto-triggers Ghostwriter above threshold

```python
graph.add_conditional_edges(
    "check_embedding_freshness",
    lambda s: "stale" if s["embedding_version"] != s["expected_version"] else "fresh",
    {
        "stale": "regenerate_embeddings",
        "fresh": "filter_non_negotiables",
    }
)
```

### Ghostwriter Agent
- Duplicate variant check (prevents race conditions)
- Checks job still active before presenting

```python
graph.add_conditional_edges(
    "check_existing_variant",
    route_existing_variant,
    {
        "none_exists": "select_base_resume",
        "draft_exists": "handle_duplicate",
        "approved_exists": "handle_duplicate",
    }
)
```

---

## Race Condition Prevention

### Stale Embeddings ("Cold Start")

```python
def is_embedding_stale(persona: Persona, cached_version: int) -> bool:
    """Check if persona embeddings need regeneration."""
    return cached_version != persona.embedding_version
```

### Duplicate JobVariant

```python
async def check_existing_variant(state: GhostwriterState) -> GhostwriterState:
    existing = await db.query(JobVariant).filter(
        job_posting_id=state["job_posting_id"],
        status__in=["Draft", "Approved"],
    ).first()

    return {"existing_variant": existing}
```

### Concurrent Persona Edits

```python
async def update_persona(persona_id: str, changes: dict, expected_version: datetime):
    persona = await db.get(Persona, persona_id)
    if persona.updated_at != expected_version:
        raise ConflictError("Persona modified. Refresh and retry.")
    # Proceed with update
```

---

## Model Routing by Task

| Task | Model | Why |
|------|-------|-----|
| Skill extraction (Scouter) | Haiku | High volume, simple |
| Ghost detection | Haiku | Simple classification |
| Score rationale (Strategist) | Sonnet | Reasoning needed |
| Cover letter (Ghostwriter) | Sonnet | Writing quality |
| Chat responses | Sonnet | Conversational nuance |
| Onboarding interview | Sonnet | Interview quality |

```python
MODEL_ROUTING = {
    TaskType.EXTRACTION: "claude-3-haiku",
    TaskType.SCORING: "claude-3-sonnet",
    TaskType.GENERATION: "claude-3-sonnet",
    TaskType.CHAT: "claude-3-sonnet",
}
```

---

## Testing Agents

```python
@pytest.mark.asyncio
async def test_chat_routes_to_ghostwriter():
    """Chat agent should delegate draft requests to Ghostwriter."""
    state = ChatAgentState(
        user_id="test-user",
        persona_id="test-persona",
        current_message="Draft materials for job 123",
        messages=[],
    )

    result = await chat_graph.ainvoke(state)

    assert any(
        r["tool"] == "ghostwriter"
        for r in result.get("tool_results", [])
    )
```

---

## Checklist

Before implementing an agent:

- [ ] State schema extends `BaseAgentState`
- [ ] Entry point set with `set_entry_point()`
- [ ] Conditional edges use routing functions (not inline lambdas for complex logic)
- [ ] HITL checkpoints where user input needed
- [ ] Race conditions handled (embeddings, duplicates)
- [ ] Model routing matches task type
- [ ] All writes go through API (not direct DB)
- [ ] Tests verify graph routing

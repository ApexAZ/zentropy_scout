# 🌀 PRD: Zentropy Scout (v1.5 - The Complete Identity Engine)

**Status:** Drafting
**Project Lead:** Brian Husk
**Date:** January 23, 2026
**License:** AGPL-3.0

---

## 1. Executive Summary

Zentropy Scout is an agentic framework for job search automation. It uses a **Persona-First approach**, where an Onboarding Agent conducts a deep-dive interview to build a vectorized career profile. This profile then guides the multi-model "Six-Path" architecture to find, score, and draft applications.

---

## 2. The Onboarding Agent (The Discovery Engine)

The Onboarding Agent is a specialized chat-based state machine that runs before the main dashboard is unlocked.

### 2.1 Functional Logic

- **Identity Harvesting:** The agent doesn't just read a PDF; it "interviews" the user to find the "hidden" wins not found on a standard resume (e.g., "Tell me about a time you saved a project at RTX using Scrum").
- **Role Alignment:** It maps user skills to the Strategist's weighted scoring matrix.
- **Connectivity Setup:** It guides the user through the Six-Path Gateway setup (Local, Sub, or API).

### 2.2 Onboarding Agent Connectivity

The Onboarding Agent itself is model-agnostic. For your setup:

- **Preferred Local:** Llama 4 Scout (17B) — Fast, conversational, and fits entirely in your 4090's VRAM for zero-latency chatting.
- **Preferred Cloud:** GPT-5.2 (API) or Claude 4.5 (Sub) — For the most nuanced "career coaching" style interview.

---

## 3. The Persona Layer (Identity)

**Requirement:** The system must generate a `persona_v1.json` file.

**Components:**
- **Technical Stack:** e.g., Next.js, FastAPI
- **Soft Skills:** Scrum Master
- **Logistics:** Remote, salary requirements
- **Professional Voice:** Writing style samples

---

## 4. Functional Requirements: The Agentic Core

### 4.1 The Scouter (Ingestion)

- **Trigger:** Only activates once the Onboarding Agent marks `onboarding_complete: true`
- **Logic:** Uses the harvested persona to set "Hard Filters" for scraping
- **Goal:** Massive context digestion and "Ghost Job" filtering
- **Preferred Path:** Gemini 3 (Sub/API) for 1M+ token context or Llama 4 Scout (Local) for rapid crawling

### 4.2 The Strategist (Scoring)

- **Logic:** Compares the "Onboarding Interview" data against Job Descriptions using pgvector similarity
- **Goal:** High-fidelity semantic matching between User Persona and JD
- **Preferred Path:** GPT-5.2 (API) or Llama 4 Maverick (Local) for abstract reasoning and weighted scoring

### 4.3 The Ghostwriter (Drafting)

- **Goal:** Human-sounding resume versioning and cover letter drafting
- **Preferred Path:** Claude 4.5 (Sub/API) for superior professional prose and tone matching

---

## 5. Technical Stack: The Six-Path Gateway

The system uses a provider-agnostic abstraction layer (e.g., LiteLLM or LangChain) to support these six connectivity options:

| Path | Model Type | Use in Onboarding |
|------|------------|-------------------|
| 1. Local | Llama 4 (17B/400B) | Zero-cost, private interview. |
| 2. Claude Sub | Claude 4.5 | High-fidelity "Natural" conversation. |
| 3. Gemini Sub | Gemini 3 Pro | Analyzing years of historical docs in context. |
| 4. OpenAI API | GPT-5.2 | Best for extracting "Strategic Wins." |
| 5. Claude API | Claude 4.5 | Reliable, session-based chat. |
| 6. Gemini API | Gemini 3 | High-speed data extraction from resume PDFs. |

---

## 6. UI: The Dashboard "State Awareness"

The Dashboard will now display a **"Discovery Progress"** bar. Main scouting features remain locked until the Onboarding Agent has enough data to build a high-confidence match score.

**Model Routing Dashboard:** Users assign one of the 6 paths to each agent role.

**Example User Setup:**
- **Onboarding Agent:** Local (Ollama: Llama-4-Scout) → Zero-latency interview
- **Scouter:** Cloud (Gemini 3 Subscription) → $0 extra
- **Strategist:** Cloud (GPT-5.2 API) → Pay-as-you-go
- **Ghostwriter:** Cloud (Claude 4.5 Subscription) → $0 extra

---

## 7. Technical Infrastructure

| Layer       | Technology          | Rationale                                                                          |
|-------------|---------------------|------------------------------------------------------------------------------------|
| Frontend    | Next.js 15          | Managed UI for real-time application tracking and "Human-in-the-Loop" review.     |
| Agent Core  | LangGraph           | Orchestrates cyclic tasks; utilizes Redis for state persistence (Pause/Resume).   |
| API         | FastAPI             | High-speed Python orchestrator for background agent tasks.                        |
| Database    | Postgres + pgvector | Stores career history and uses vector similarity for skill-to-JD matching.        |
| State Store | Redis               | Crucial for checkpointing long-running scrapes and task queuing.                  |
| Local LLM   | Ollama              | GPU-accelerated inference for privacy and cost efficiency.                        |
| LLM Gateway | LiteLLM/LangChain   | Provider-agnostic abstraction layer supporting 6 connectivity paths.              |

---

## 8. Local Hardware Configuration (The 4090/128GB Spec)

For users with high-end hardware, the system defaults to **Local Mode** for cost efficiency.

- **GPU Performance Tier:** RTX 4090 handles GLM-4.7 Flash or Llama 4 Scout at >120 tokens/sec
- **Unified Memory Tier:** With 128GB RAM, you can offload Llama 4 Maverick (400B). While slower (~2-3 t/s), it provides frontier-level reasoning for complex scoring

---

## 9. Operational Requirements

- **Model Gateway:** Provider abstraction layer supporting 6 connectivity paths per agent role
- **Onboarding State Machine:** Chat-based discovery engine that builds persona_v1.json before unlocking main features
- **Subscription Management:** Cloud models accessed via API keys or OAuth with defined budget caps in .env
- **Privacy:** Enterprise API tiers ensure user data is not used for model training
- **HITL (Human-in-the-Loop):** Every "High-Value" match triggers a Pause in LangGraph state, requiring user approval before Ghostwriter proceeds
- **Hardware Optimization:** Support for both GPU-only (speed) and VRAM+RAM (reasoning) configurations

---

## 10. Project Roadmap

- **Phase 1 (MVP):** Onboarding Agent + "Scout-and-Store" functionality
- **Phase 2 (Intelligence):** Semantic matching and scoring implementation via pgvector
- **Phase 3 (Full Loop):** Ghostwriting and HITL Dashboard integration
- **Phase 4 (Universal Gateway):** Six-path provider abstraction with model routing dashboard

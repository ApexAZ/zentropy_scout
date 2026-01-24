# 🌀 PRD: Zentropy Scout (v1.6 - Universal Core)

**Status:** Drafting
**License:** AGPL-3.0
**Architecture:** Multi-Tenant / Multi-Model Agentic System

---

## 1. Executive Summary

Zentropy Scout is a modular, multi-agent AI framework designed to automate the high-friction elements of job hunting. It replaces the "spray and pray" method with a **Persona-First architecture**, utilizing a multi-model gateway to scout, score, and draft applications based on deep qualitative matching rather than just keyword filtering.

---

## 2. Product Goals & Objectives

- **Primary Objective:** Automate the identification of "High-Quality" roles that align with a user's specific career trajectory and values.
- **Metric of Success:** Achieve >90% "match accuracy" where the user approves the agent's findings.
- **Core Philosophy:** "Human-in-the-Loop" (HITL). Agents propose; humans decide. No application is ever submitted automatically.

---

## 3. The Onboarding Agent (The Discovery Engine)

The entry point is a conversational agent that builds the **Persona Identity Layer**. It replaces static forms with a dynamic interview.

- **Goal:** Construct a `persona_v1.json` that captures the user's "Voice," "Technical Depth," and "Value Criteria."
- **Value Criteria** (formerly Salary): Instead of hard numbers, the agent captures preferences for "Market Positioning," "Benefits Structure," "Remote/Hybrid Balance," and "Company Mission."
- **Output:** A vectorized profile stored in Postgres used by the Strategist for semantic matching.

---

## 4. Technical Stack: Universal Gateway

The system features a **Model Abstraction Layer** allowing users to bring their own subscriptions or hardware.

| # | Path Type | Model Option | Auth / Connection Method |
|---|-----------|--------------|--------------------------|
| 1 | Local (Privacy) | Llama 4 / Qwen 3 | Ollama (Localhost) |
| 2 | Claude Sub | Claude 4.5 | Unified Auth (Pro Plan Link) |
| 3 | Gemini Sub | Gemini 3 Pro | Google OAuth (Pro/Student Link) |
| 4 | OpenAI API | GPT-5.2 | API Key (Pay-as-you-go) |
| 5 | Claude API | Claude 4.5 | API Key (Pay-as-you-go) |
| 6 | Gemini API | Gemini 3 | API Key (Pay-as-you-go) |

---

## 5. Functional Requirements: The Agentic Core

### 5.1 The Scouter (Ingestion)

- **Role:** The "Hunter"
- **Logic:** Scrapes target boards (LinkedIn, Indeed, Niche) using stealth-browsing
- **Ghost Job Detection:** Analyzes posting patterns (re-posts, vague language) to filter out "fake" inventory before the user sees it

### 5.2 The Strategist (Scoring)

- **Role:** The "Analyst"
- **Logic:** Calculates a Match Score (0-100) based on:
  - **Hard Skills:** 40% (Tech Stack overlap)
  - **Soft Skills:** 30% (Leadership/Communication match)
  - **Logistics:** 30% (Location, Work Type, "Value Criteria" alignment)

### 5.3 The Ghostwriter (Drafting)

- **Role:** The "Scribe"
- **Logic:** Generates Resume Deltas (highlighting specific relevant experience) and Cover Letters that match the user's natural writing style

---

## 6. Architecture & Infrastructure

- **Frontend:** Next.js 15 (Dashboard, Persona Manager, Review Queue)
- **Backend:** FastAPI (Async Orchestration)
- **Agent Logic:** LangGraph (Stateful Multi-Agent Workflows)
- **Database:** PostgreSQL + pgvector (Long-term memory)
- **State Store:** Redis (Task Queues & Checkpoints)
- **Deployment:** Docker Compose (Portable to any cloud or local machine)

---

## 7. Roadmap

- **Phase 1 (MVP):** "Scout-and-Store" with Local/Sub model support
- **Phase 2 (Intelligence):** Onboarding Agent & Semantic Scoring
- **Phase 3 (Full Loop):** Ghostwriting & UI Dashboard

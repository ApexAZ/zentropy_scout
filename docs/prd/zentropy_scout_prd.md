# 🌀 PRD: Zentropy Scout

**Version:** 1.7 (The Universal Core)  
**License:** AGPL-3.0  
**Status:** Approved for Development

---

## 1. Executive Summary

Zentropy Scout is a modular, multi-agent AI framework designed to transform the job search from a manual "spray-and-pray" process into a strategic, high-precision operation.

It utilizes a **Persona-First architecture** where an AI "Onboarding Agent" interviews the user to build a deep semantic profile. This profile drives a fleet of background agents that scout job boards, mathematically score opportunities against the user's history and values, and proactively draft tailored application materials. The system operates on a strict **Human-in-the-Loop (HITL)** philosophy: the AI acts as a "Co-Pilot" that proposes drafts, but the human always retains final approval authority.

---

## 2. Product Goals & Objectives

### 2.1 Primary Objectives

- **High-Fidelity Scouting:** Identify roles that align not just with keywords, but with the user's nuanced history and "Value Criteria" (e.g., market positioning, remote culture, specific tech stacks).

- **Proactive Application Engineering:** Automatically generate a tailored Cover Letter and a "Redline" Resume version for every High-Match (>90%) opportunity found.

- **Collaborative Refinement:** Provide a specialized interface where users can review, edit, and accept the agent's proposed resume changes before creating a final PDF.

### 2.2 Strategic Value

- **Zero-Friction Starts:** The user never faces a blank page. Applications start at 90% completion.

- **Deep Context Utilization:** The agent mines the user's full history (including "hidden" wins discovered during onboarding) to find relevance that standard keyword matching misses.

- **Probability Optimization:** Content is optimized specifically to pass ATS filters and appeal to the inferred hiring manager persona.

### 2.3 Non-Goals

- **No Auto-Submit:** The system is strictly forbidden from interacting with external application portals (clicking "Submit") without a manual trigger.

- **No Spam:** The system will not generate generic applications; every output must be contextually unique to the specific Job ID.

---

## 3. The Persona Framework (The Identity Layer)

The system does not rely on a static resume upload. It uses an **Onboarding Agent** to build a dynamic "Source of Truth."

### 3.1 The Discovery Interview

Before the dashboard unlocks, an AI agent conducts a strategic interview to populate the `persona_v1.json` profile. The questions focus on extracting "Deep Context":

| Discovery Area | Purpose |
|----------------|---------|
| **Achievement Stories** | Extracting behavioral "wins" and problem-solving stories not explicitly listed on the resume |
| **Skill Proficiency Levels** | Distinguishing between "Expert" skills (can build in 24h) and "Familiar" skills (need Google), to weight scoring accurately |
| **Non-Negotiables** | Defining hard filters for "Value Criteria" (e.g., specific industries to avoid, minimum benefit requirements) |
| **Professional Voice** | Identifying the user's "Brand Voice" to ensure generated summaries sound authentic |
| **Growth Targets** | Identifying "Stretch" technologies the user wants to prioritize in their next role |

---

## 4. Functional Requirements: The Agentic Core

### 4.1 The Scouter (Ingestion Engine)

**Role:** Job Discovery

**Source Strategy:**

| Tier | Source | Method |
|------|--------|--------|
| Tier 1 | LinkedIn, Indeed | Stealth, headless browsing using local LLMs to parse HTML |
| Tier 2 | Greenhouse, Lever | Direct sitemap crawling of ATS platforms for fresh, low-competition inventory |
| Tier 3 | Google Jobs, Niche Boards | Aggregator feeds |

**Ghost Job Detection:** Analyzes posting patterns (frequency of reposts, age of listing) to filter out "fake" inventory before it reaches the user.

### 4.2 The Strategist (Scoring Engine)

**Role:** Match Analysis

**Logic:** Calculates a Match Score (0-100) using vector similarity:

| Factor | Weight | Description |
|--------|--------|-------------|
| Hard Skills | 40% | Technical stack overlap |
| Soft Skills | 30% | Leadership and communication style alignment |
| Logistics | 30% | Alignment with "Value Criteria" (Location, Work Type, Culture) |

**Gap Analysis:** For high-scoring roles, the agent identifies exactly what is missing (e.g., "Job requires Kubernetes, User has Docker") to inform the Ghostwriter.

### 4.3 The Ghostwriter (Drafting Engine)

**Role:** Content Generation

**Trigger:** Activates automatically when the Match Score exceeds a user-defined threshold (e.g., >90%).

- **Resume Redlining:** Creates a job-specific copy of the resume. It re-orders bullet points to prioritize relevant skills and rewrites the summary to match the job's terminology.

- **Cover Letter Generation:** Selects a specific "Story" from the Onboarding Interview that proves the user's fitness for the role and drafts a narrative letter in the user's voice.

---

## 5. Technical Architecture: Universal Gateway

To support "Many Users" with different resources, the backend uses a **Provider Abstraction Layer**. Users can configure each agent role (Scouter, Strategist, Ghostwriter) to use one of six connectivity paths:

| Provider | Type | Best For |
|----------|------|----------|
| **Local** | Privacy/Cost | Runs on local hardware (e.g., RTX 4090) via Ollama. High-volume scouting and privacy |
| **Claude Subscription** | Unified Auth | Uses existing Pro Plan. High-quality drafting |
| **Gemini Subscription** | Unified Auth | Uses existing Google AI Pro benefit. Massive context windows (scouting) |
| **OpenAI API** | Pay-as-you-go | Complex logic/scoring |
| **Claude API** | Pay-as-you-go | Reliable batch processing |
| **Gemini API** | Pay-as-you-go | High-speed parsing |

### 5.1 The Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 15 (React 19) | Dashboard, Persona Manager, and "Diff View" review interface |
| **Backend** | FastAPI | Asynchronous Python orchestrator for agent management |
| **Agent Logic** | LangGraph | Manages cyclic workflows and "Pause/Resume" states for Human Review |
| **State Store** | Redis | Background task queues and agent checkpoints (memory) |
| **Infrastructure** | Docker Compose | Portable containerization for all services |

---

## 6. Data Strategy: The Hybrid Schema

The system leverages **PostgreSQL** as a hybrid store, combining the data integrity of SQL with the flexibility of NoSQL.

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| **Rigid Tables** | Standard SQL | Core relationships (Users, IDs, timestamps, status flags). Ensures data integrity and efficient indexing |
| **JSONB Columns** | PostgreSQL JSONB | Complex, variable data (Resume structures, Job Descriptions, API configurations). Allows schema evolution without breaking the application |
| **Vector Embeddings** | pgvector | Mathematical representation of user personas and job descriptions, enabling semantic "meaning-based" matching |

---

## 7. User Interface & Workflow

1. **System Check:** User selects AI Providers (Local, Sub, or API)
2. **Onboarding:** User completes the "Discovery Interview" chat
3. **Dashboard (The Feed):** User sees a feed of "High Match" jobs
4. **Review (The Co-Pilot):** User clicks a job to see Match Score breakdown, "Redlined" Resume, and Draft Cover Letter
5. **Action:** User accepts/edits drafts and downloads final package

---

## 8. Roadmap

| Phase | Name | Deliverables |
|-------|------|--------------|
| **Phase 1** | MVP: "Scout-and-Store" | Basic ingestion, local/cloud gateway setup, and database persistence |
| **Phase 2** | Intelligence | Onboarding Agent implementation and Vector Scoring (The Strategist) |
| **Phase 3** | Full Loop | Ghostwriting agents and the "Diff View" UI for resume collaboration |

---

## Appendix: Key Terms

- **HITL (Human-in-the-Loop):** Design principle ensuring humans maintain final decision authority
- **ATS (Applicant Tracking System):** Software used by employers to filter resumes
- **Redlining:** Process of marking up a document to show proposed changes
- **Vector Similarity:** Mathematical technique for comparing semantic meaning between texts
- **pgvector:** PostgreSQL extension for storing and querying vector embeddings

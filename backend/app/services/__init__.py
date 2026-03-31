"""Zentropy Scout services layer.

Eight domain subdirectories + six cross-cutting files:

Domains:
  scoring/     — Job-Persona match scoring (fit score, stretch score, pool scoring)
  embedding/   — Vector embedding lifecycle (generation, staleness, caching)
  generation/  — Content generation pipeline (resume tailoring, cover letters, voice)
  rendering/   — Document format handling (PDF, DOCX, markdown, templates, parsing)
  discovery/   — Job discovery & pool management (extraction, enrichment, dedup, surfacing)
  billing/     — Payments & usage metering (Stripe, webhooks, reserve/settle/release)
  admin/       — Admin configuration & management (models, pricing, routing, users)
  onboarding/  — User onboarding flow (12-step wizard, section routing)

Cross-cutting (remain at services/ root):
  persona_sync.py          — Persona → Base Resume change flag sync
  application_workflow.py  — Persist generation output to DB entities
  agent_message.py         — Agent-to-user message types (6 semantic types)
  agent_handoff.py         — Agent-to-agent communication patterns (3 patterns)
  retention_cleanup.py     — Multi-domain data retention enforcement (4 policies)
  ingest_token_store.py    — In-memory ephemeral token management for ingest preview
"""

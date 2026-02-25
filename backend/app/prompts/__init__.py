"""Prompt templates for LLM interactions.

Cross-agent prompt templates relocated from agents/ package during
the LLM redesign (REQ-016, REQ-017, REQ-018). Each module contains
system/user prompt pairs and builder functions for a specific domain.

Modules:
    strategist: Score rationale + non-negotiables prompts (REQ-017 §8)
    ghostwriter: Cover letter, summary tailoring + regeneration prompts (REQ-018 §8)
"""

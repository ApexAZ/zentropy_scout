/**
 * @fileoverview Shared constants for admin configuration components.
 *
 * Layer: lib/utility
 * Feature: admin
 *
 * REQ-022 §11: Provider and model type options used across admin tabs.
 * REQ-028 §6.1: Fixed task type rows for routing table.
 *
 * Coordinates with:
 * - (no external dependencies — pure constant definitions)
 *
 * Called by / Used by:
 * - components/admin/add-model-dialog.tsx: MODEL_TYPES, PROVIDERS for dropdown options
 * - components/admin/add-pricing-dialog.tsx: PROVIDERS for provider dropdown
 * - components/admin/routing-tab.tsx: PROVIDERS, TASK_TYPES for routing table
 */

export const PROVIDERS = ["claude", "openai", "gemini"] as const;
export const MODEL_TYPES = ["llm", "embedding"] as const;

/**
 * All task types from backend TaskType enum (base.py).
 *
 * REQ-028 §6.1: One row per TaskType in the fixed routing table.
 * Order matches backend enum declaration order.
 */
export const TASK_TYPES = [
	{ value: "chat_response", label: "Chat Response" },
	{ value: "onboarding", label: "Onboarding" },
	{ value: "skill_extraction", label: "Skill Extraction" },
	{ value: "extraction", label: "Extraction" },
	{ value: "ghost_detection", label: "Ghost Detection" },
	{ value: "score_rationale", label: "Score Rationale" },
	{ value: "cover_letter", label: "Cover Letter" },
	{ value: "resume_tailoring", label: "Resume Tailoring" },
	{ value: "story_selection", label: "Story Selection" },
	{ value: "resume_parsing", label: "Resume Parsing" },
] as const;

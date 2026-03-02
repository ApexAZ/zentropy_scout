/**
 * Shared constants for admin components.
 *
 * REQ-022 §11: Provider and model type options used across admin tabs.
 */

export const PROVIDERS = ["claude", "openai", "gemini"] as const;
export const MODEL_TYPES = ["llm", "embedding"] as const;

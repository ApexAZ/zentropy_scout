/**
 * @fileoverview Embedding staleness notification utilities.
 *
 * Layer: lib/utility
 * Feature: persona
 *
 * REQ-012 §7.7: After persona edits that affect matching (skills,
 * work history, non-negotiables), show a brief "Updating your match
 * profile..." indicator. On completion (SSE `data_changed` for
 * embeddings), show "Match profile updated. Job scores may have
 * changed." and refresh job queries.
 *
 * REQ-012 §13.5: Warning toasts use amber styling with 5 s auto-dismiss.
 *
 * Coordinates with:
 * - lib/toast.ts: notification display via showToast
 *
 * Called by / Used by:
 * - lib/sse-provider.tsx: calls notifyEmbeddingComplete on SSE embedding events
 * - components/persona/skills-editor.tsx: embedding update notification after save
 * - components/persona/work-history-editor.tsx: embedding update notification after save
 * - components/persona/non-negotiables-editor.tsx: embedding update notification after save
 */

import { showToast } from "./toast";

/**
 * Show a warning toast indicating that the match profile is being
 * regenerated after a matching-relevant persona edit.
 *
 * Called by section editors (skills, work history, non-negotiables)
 * after a successful save that changes matching-relevant data.
 */
export function notifyEmbeddingUpdate(): void {
	showToast.warning("Updating your match profile...");
}

/**
 * Show an info toast indicating that embedding regeneration is
 * complete and job scores may have changed.
 *
 * Called by the SSE bridge when a `data_changed` event arrives
 * for the "embedding" resource.
 */
export function notifyEmbeddingComplete(): void {
	showToast.info("Match profile updated. Job scores may have changed.");
}

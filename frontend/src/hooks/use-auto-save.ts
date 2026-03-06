/**
 * Auto-save hook with debounced persistence for the resume editor.
 *
 * REQ-026 §7.1: Debounced save (2s after last keystroke).
 * REQ-026 §7.2: Save status indicator states.
 * REQ-026 §7.3: Handles 409 Conflict for optimistic concurrency.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiPatch } from "@/lib/api-client";
import type { SaveStatus } from "@/components/editor/editor-status-bar";
import type { ApiResponse } from "@/types/api";
import type { BaseResume } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseAutoSaveOptions {
	/** Current markdown content from the editor. */
	content: string;
	/** Base resume UUID. */
	resumeId: string;
	/** Whether auto-save is enabled (default: true). */
	enabled?: boolean;
}

interface UseAutoSaveResult {
	saveStatus: SaveStatus;
	hasConflict: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEBOUNCE_MS = 2000;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAutoSave({
	content,
	resumeId,
	enabled = true,
}: UseAutoSaveOptions): UseAutoSaveResult {
	const [asyncStatus, setAsyncStatus] = useState<"idle" | "saving" | "error">(
		"idle",
	);
	const [hasConflict, setHasConflict] = useState(false);
	const [lastSavedContent, setLastSavedContent] = useState(content);

	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const beforeunloadRef = useRef<((e: BeforeUnloadEvent) => void) | null>(null);

	// Derive dirty state from content comparison
	const isDirty = content !== lastSavedContent;

	// Derive the public save status
	const saveStatus: SaveStatus = (() => {
		if (asyncStatus === "saving") return "saving";
		if (asyncStatus === "error") return "error";
		if (isDirty) return "unsaved";
		return "saved";
	})();

	// beforeunload handlers
	const addBeforeunload = useCallback(() => {
		if (beforeunloadRef.current) return;
		const handler = (e: BeforeUnloadEvent) => {
			e.preventDefault();
		};
		beforeunloadRef.current = handler;
		window.addEventListener("beforeunload", handler);
	}, []);

	const removeBeforeunload = useCallback(() => {
		if (!beforeunloadRef.current) return;
		window.removeEventListener("beforeunload", beforeunloadRef.current);
		beforeunloadRef.current = null;
	}, []);

	// Save function
	const save = useCallback(
		async (markdownContent: string) => {
			setAsyncStatus("saving");
			try {
				await apiPatch<ApiResponse<BaseResume>>(`/base-resumes/${resumeId}`, {
					markdown_content: markdownContent,
				});
				setLastSavedContent(markdownContent);
				setAsyncStatus("idle");
				setHasConflict(false);
			} catch (error) {
				setAsyncStatus("error");
				if (error instanceof ApiError && error.status === 409) {
					setHasConflict(true);
				}
			}
		},
		[resumeId],
	);

	// Manage beforeunload based on dirty state
	useEffect(() => {
		if (isDirty) {
			addBeforeunload();
		} else {
			removeBeforeunload();
		}
	}, [isDirty, addBeforeunload, removeBeforeunload]);

	// Debounced save on content changes
	useEffect(() => {
		if (!isDirty || !enabled) return;

		if (timerRef.current) {
			clearTimeout(timerRef.current);
		}

		timerRef.current = setTimeout(() => {
			void save(content);
		}, DEBOUNCE_MS);

		return () => {
			if (timerRef.current) {
				clearTimeout(timerRef.current);
				timerRef.current = null;
			}
		};
	}, [content, isDirty, enabled, save]);

	// Cleanup on unmount
	useEffect(() => {
		return () => {
			if (timerRef.current) {
				clearTimeout(timerRef.current);
			}
			removeBeforeunload();
		};
	}, [removeBeforeunload]);

	return { saveStatus, hasConflict };
}

"use client";

/**
 * @fileoverview Status bar for the TipTap resume editor.
 *
 * Layer: component
 * Feature: resume
 *
 * REQ-025 §3.5: Word count, page estimate, and save status indicator.
 * REQ-026 §7.2: Four save status states (Saved, Saving, Unsaved, Error).
 *
 * Coordinates with:
 * - (standalone — no project imports)
 *
 * Called by / Used by:
 * - components/resume/resume-content-view.tsx: status bar below editor in edit mode
 * - hooks/use-auto-save.ts: imports SaveStatus type for save state tracking
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SaveStatus = "saved" | "saving" | "unsaved" | "error";

interface EditorStatusBarProps {
	wordCount: number;
	saveStatus: SaveStatus;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WORDS_PER_PAGE = 350;

const STATUS_CONFIG: Record<SaveStatus, { label: string; className: string }> =
	{
		saved: { label: "Saved", className: "" },
		saving: { label: "Saving...", className: "" },
		unsaved: { label: "Unsaved changes", className: "" },
		error: { label: "Save failed", className: "text-destructive" },
	};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EditorStatusBar({
	wordCount,
	saveStatus,
}: Readonly<EditorStatusBarProps>) {
	const pageEstimate =
		wordCount === 0 ? 0 : Math.ceil(wordCount / WORDS_PER_PAGE);
	const { label, className: statusClassName } = STATUS_CONFIG[saveStatus];

	return (
		<div
			className="border-border text-muted-foreground flex items-center gap-4 border-t px-4 py-1.5 text-xs"
			data-testid="editor-status-bar"
			role="status"
			aria-live="polite"
		>
			<span data-testid="status-word-count">
				{wordCount} {wordCount === 1 ? "word" : "words"}
			</span>
			<span data-testid="status-page-estimate">
				~{pageEstimate} {pageEstimate === 1 ? "page" : "pages"}
			</span>
			<span
				className={`ml-auto ${statusClassName}`.trim()}
				data-testid="status-save"
			>
				{label}
			</span>
		</div>
	);
}

export type { EditorStatusBarProps };

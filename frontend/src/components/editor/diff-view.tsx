"use client";

/**
 * Side-by-side diff view for comparing master and variant resume content.
 *
 * REQ-027 §4.1–§4.4: Word-level diff with color highlighting.
 * REQ-027 §8: Fallback — show variant without highlighting if diff fails.
 */

import { diffWords, type Change } from "diff";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DiffViewProps {
	readonly masterMarkdown: string;
	readonly variantMarkdown: string;
}

type ChangeType = "unchanged" | "added" | "removed" | "modified";

interface ProcessedChange {
	readonly type: ChangeType;
	readonly value: string;
	readonly oldValue?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PANEL_CLASSES = "min-w-0 flex-1";
const CONTENT_CLASSES =
	"whitespace-pre-wrap rounded-md border bg-card p-4 text-sm";
const HEADING_CLASSES = "text-sm font-semibold";

// ---------------------------------------------------------------------------
// Diff Processing
// ---------------------------------------------------------------------------

/**
 * Processes raw diff changes to detect modifications (adjacent remove+add).
 *
 * The `diffWords` library returns flat add/remove entries. When a removal is
 * immediately followed by an addition, it represents rephrased text — shown
 * with warning highlighting on both sides per REQ-027 §4.3.
 */
function processChanges(rawChanges: Change[]): ProcessedChange[] {
	const result: ProcessedChange[] = [];
	let i = 0;

	while (i < rawChanges.length) {
		const current = rawChanges[i];
		const next = rawChanges[i + 1];

		if (current.removed && next?.added) {
			result.push({
				type: "modified",
				value: next.value,
				oldValue: current.value,
			});
			i += 2;
		} else if (current.added) {
			result.push({ type: "added", value: current.value });
			i += 1;
		} else if (current.removed) {
			result.push({ type: "removed", value: current.value });
			i += 1;
		} else {
			result.push({ type: "unchanged", value: current.value });
			i += 1;
		}
	}

	return result;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MasterPanel({
	changes,
}: {
	readonly changes: readonly ProcessedChange[];
}) {
	return (
		<div
			data-testid="diff-master-panel"
			className={PANEL_CLASSES}
			role="region"
			aria-label="Master resume content"
		>
			<div className="mb-2 flex items-center gap-2">
				<span className={HEADING_CLASSES}>Master Resume</span>
				<span className="text-muted-foreground text-xs">(read-only)</span>
			</div>
			<div className={CONTENT_CLASSES}>
				{changes.map((change, i) => {
					if (change.type === "added") return null;
					if (change.type === "removed") {
						return (
							<span
								key={i}
								className="bg-destructive/10 text-destructive line-through"
							>
								{change.value}
							</span>
						);
					}
					if (change.type === "modified") {
						return (
							<span key={i} className="bg-warning/10 text-warning">
								{change.oldValue}
							</span>
						);
					}
					return <span key={i}>{change.value}</span>;
				})}
			</div>
		</div>
	);
}

function VariantPanel({
	changes,
}: {
	readonly changes: readonly ProcessedChange[];
}) {
	return (
		<div
			data-testid="diff-variant-panel"
			className={PANEL_CLASSES}
			role="region"
			aria-label="Tailored variant content"
		>
			<div className="mb-2 flex items-center gap-2">
				<span className={HEADING_CLASSES}>Tailored Variant</span>
			</div>
			<div className={CONTENT_CLASSES}>
				{changes.map((change, i) => {
					if (change.type === "removed") return null;
					if (change.type === "added") {
						return (
							<span key={i} className="bg-success/10 text-success">
								{change.value}
							</span>
						);
					}
					if (change.type === "modified") {
						return (
							<span key={i} className="bg-warning/10 text-warning">
								{change.value}
							</span>
						);
					}
					return <span key={i}>{change.value}</span>;
				})}
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

/**
 * Renders a side-by-side word-level diff of master vs variant markdown.
 *
 * Master (left) is read-only. Variant (right) shows the tailored version.
 * Changes are highlighted: green (additions), red+strikethrough (removals),
 * yellow (modifications / rephrased text).
 *
 * Falls back to plain text without highlighting if diff computation fails.
 */
export function DiffView({
	masterMarkdown,
	variantMarkdown,
}: Readonly<DiffViewProps>) {
	let changes: ProcessedChange[];

	try {
		const rawChanges = diffWords(masterMarkdown, variantMarkdown);
		changes = processChanges(rawChanges);
	} catch {
		return (
			<div
				data-testid="diff-view"
				className="flex flex-col gap-4 md:flex-row"
				aria-label="Resume comparison"
			>
				<MasterPanel changes={[{ type: "unchanged", value: masterMarkdown }]} />
				<VariantPanel
					changes={[{ type: "unchanged", value: variantMarkdown }]}
				/>
			</div>
		);
	}

	return (
		<div
			data-testid="diff-view"
			className="flex flex-col gap-4 md:flex-row"
			aria-label="Resume comparison"
		>
			<MasterPanel changes={changes} />
			<VariantPanel changes={changes} />
		</div>
	);
}

"use client";

/**
 * @fileoverview Reusable bucket card and tag editor for SearchProfile editing.
 *
 * Layer: component
 * Feature: persona
 *
 * REQ-034 §9.1: Editable tag lists for fit and stretch search buckets.
 * Extracted from SearchCriteriaStep for file-length compliance and
 * future reuse in the Job Search settings card (REQ-034 §9.2).
 *
 * Coordinates with:
 * - types/search-profile.ts: SearchBucket type for bucket shape
 * - components/ui/ (implicit): uses design tokens from globals.css
 *
 * Called by / Used by:
 * - components/onboarding/steps/search-criteria-step.tsx: onboarding step 10
 * - hooks/use-search-criteria-editing.ts: updateBucket helper for settings editing
 * - components/settings/job-search-section.tsx: BucketCard in Job Search settings card
 */

import { X } from "lucide-react";
import { useRef } from "react";

import type { SearchBucket } from "@/types/search-profile";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum characters per tag (mirrors backend _MAX_TITLE_LEN). */
const MAX_TAG_LENGTH = 200;

/** Maximum tags per field (mirrors backend _MAX_LIST_ITEMS). */
const MAX_TAGS = 30;

// ---------------------------------------------------------------------------
// Tag editor (lightweight, no RHF dependency)
// ---------------------------------------------------------------------------

function TagEditor({
	tags,
	onAdd,
	onRemove,
	placeholder,
	ariaLabel,
}: Readonly<{
	tags: string[];
	onAdd: (tag: string) => void;
	onRemove: (index: number) => void;
	placeholder?: string;
	ariaLabel?: string;
}>) {
	const inputRef = useRef<HTMLInputElement>(null);
	const atLimit = tags.length >= MAX_TAGS;

	function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
		if (e.key === "Enter") {
			e.preventDefault();
			if (atLimit) return;
			const value = e.currentTarget.value.trim();
			if (!value) return;
			const isDuplicate = tags.some(
				(t) => t.toLowerCase() === value.toLowerCase(),
			);
			if (isDuplicate) return;
			onAdd(value);
			e.currentTarget.value = "";
		}
	}

	return (
		/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- Wrapper click delegates focus to the inner <input>; keyboard users reach it via Tab. */
		<div
			className="border-input focus-within:border-ring focus-within:ring-ring/50 flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border bg-transparent px-3 py-1.5 text-sm shadow-xs transition-colors focus-within:ring-[3px]"
			onClick={() => inputRef.current?.focus()}
		>
			{tags.map((tag, index) => (
				<span
					key={tag}
					className="bg-secondary text-secondary-foreground inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium"
				>
					{tag}
					<button
						type="button"
						aria-label={`Remove ${tag}`}
						className="focus-visible:ring-ring rounded-sm opacity-70 hover:opacity-100 focus-visible:ring-1 focus-visible:outline-none"
						onClick={(e) => {
							e.stopPropagation();
							onRemove(index);
						}}
					>
						<X className="h-3 w-3" />
					</button>
				</span>
			))}
			{!atLimit && (
				<input
					ref={inputRef}
					type="text"
					maxLength={MAX_TAG_LENGTH}
					placeholder={placeholder}
					aria-label={ariaLabel}
					className="placeholder:text-muted-foreground min-w-[120px] flex-1 bg-transparent outline-none"
					onKeyDown={handleKeyDown}
				/>
			)}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Bucket card
// ---------------------------------------------------------------------------

export function BucketCard({
	bucket,
	testId,
	onKeywordAdd,
	onKeywordRemove,
	onTitleAdd,
	onTitleRemove,
}: Readonly<{
	bucket: SearchBucket;
	testId: string;
	onKeywordAdd: (tag: string) => void;
	onKeywordRemove: (index: number) => void;
	onTitleAdd: (tag: string) => void;
	onTitleRemove: (index: number) => void;
}>) {
	return (
		<div
			data-testid={testId}
			className="bg-card space-y-3 rounded-lg border p-4"
		>
			<h4 className="font-medium">{bucket.label}</h4>
			<div className="space-y-1.5">
				<span className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
					Keywords
				</span>
				<TagEditor
					tags={bucket.keywords}
					onAdd={onKeywordAdd}
					onRemove={onKeywordRemove}
					placeholder="Add keyword..."
					ariaLabel={`${bucket.label} keywords`}
				/>
			</div>
			<div className="space-y-1.5">
				<span className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
					Titles
				</span>
				<TagEditor
					tags={bucket.titles}
					onAdd={onTitleAdd}
					onRemove={onTitleRemove}
					placeholder="Add title..."
					ariaLabel={`${bucket.label} titles`}
				/>
			</div>
		</div>
	);
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/** Immutably update a string-array field on a specific bucket. */
export function updateBucket(
	buckets: SearchBucket[],
	index: number,
	field: "keywords" | "titles",
	values: string[],
): SearchBucket[] {
	return buckets.map((b, i) => (i === index ? { ...b, [field]: values } : b));
}

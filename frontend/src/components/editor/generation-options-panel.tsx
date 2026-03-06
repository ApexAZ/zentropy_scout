"use client";

/**
 * Generation options panel for AI resume generation.
 *
 * REQ-026 §4.2: Page limit, emphasis, section checkboxes, Generate button.
 * REQ-026 §4.7: Supports pre-filled defaults for regeneration.
 */

import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import {
	ALL_EMPHASIS_OPTIONS,
	ALL_RESUME_SECTIONS,
	DEFAULT_INCLUDE_SECTIONS,
	EMPHASIS_LABELS,
	PAGE_LIMIT_OPTIONS,
	RESUME_SECTION_LABELS,
} from "@/types/resume-generation";
import type {
	EmphasisOption,
	GenerationOptions,
	PageLimit,
	ResumeSection,
} from "@/types/resume-generation";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GenerationOptionsPanelProps {
	onGenerate: (options: GenerationOptions) => void;
	onCancel: () => void;
	isGenerating: boolean;
	defaultOptions?: GenerationOptions;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pageLimitLabel(limit: PageLimit): string {
	return limit === 1 ? "1 page" : `${limit} pages`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GenerationOptionsPanel({
	onGenerate,
	onCancel,
	isGenerating,
	defaultOptions,
}: Readonly<GenerationOptionsPanelProps>) {
	const [pageLimit, setPageLimit] = useState<PageLimit>(
		defaultOptions?.pageLimit ?? 1,
	);
	const [emphasis, setEmphasis] = useState<EmphasisOption>(
		defaultOptions?.emphasis ?? "balanced",
	);
	const [includeSections, setIncludeSections] = useState<ResumeSection[]>(
		defaultOptions?.includeSections ?? [...DEFAULT_INCLUDE_SECTIONS],
	);

	function handleToggleSection(section: ResumeSection) {
		setIncludeSections((prev) =>
			prev.includes(section)
				? prev.filter((s) => s !== section)
				: [...prev, section],
		);
	}

	function handleGenerate() {
		onGenerate({ pageLimit, emphasis, includeSections });
	}

	return (
		<div
			data-testid="generation-options-panel"
			className="bg-card w-full rounded-lg border p-6"
		>
			<h3 className="mb-4 text-lg font-semibold">Generation Options</h3>

			{/* Page Limit */}
			<div className="mb-4">
				<span id="page-limit-label" className="mb-1 block text-sm font-medium">
					Page Limit
				</span>
				<Select
					value={String(pageLimit)}
					onValueChange={(v) => setPageLimit(Number(v) as PageLimit)}
				>
					<SelectTrigger
						data-testid="page-limit-select"
						className="w-40"
						aria-labelledby="page-limit-label"
					>
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						{PAGE_LIMIT_OPTIONS.map((opt) => (
							<SelectItem key={opt} value={String(opt)}>
								{pageLimitLabel(opt)}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>

			{/* Emphasis */}
			<div className="mb-4">
				<span id="emphasis-label" className="mb-1 block text-sm font-medium">
					Emphasis
				</span>
				<Select
					value={emphasis}
					onValueChange={(v) => setEmphasis(v as EmphasisOption)}
				>
					<SelectTrigger
						data-testid="emphasis-select"
						className="w-48"
						aria-labelledby="emphasis-label"
					>
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						{ALL_EMPHASIS_OPTIONS.map((opt) => (
							<SelectItem key={opt} value={opt}>
								{EMPHASIS_LABELS[opt]}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>

			{/* Section Checkboxes */}
			<div className="mb-6" role="group" aria-labelledby="include-label">
				<span id="include-label" className="mb-2 block text-sm font-medium">
					Include
				</span>
				<div className="space-y-2">
					{ALL_RESUME_SECTIONS.map((section) => (
						<div key={section} className="flex items-center gap-2">
							<Checkbox
								id={`section-${section}`}
								checked={includeSections.includes(section)}
								onCheckedChange={() => handleToggleSection(section)}
								aria-label={RESUME_SECTION_LABELS[section]}
							/>
							<label
								htmlFor={`section-${section}`}
								className="cursor-pointer text-sm"
							>
								{RESUME_SECTION_LABELS[section]}
							</label>
						</div>
					))}
				</div>
			</div>

			{/* Action Buttons */}
			<div className="flex items-center gap-2">
				<Button onClick={handleGenerate} disabled={isGenerating}>
					{isGenerating ? (
						<>
							<Loader2 className="mr-1 h-4 w-4 animate-spin" />
							Generating...
						</>
					) : (
						<>
							<Sparkles className="mr-1 h-4 w-4" />
							Generate Resume
						</>
					)}
				</Button>
				<Button variant="outline" onClick={onCancel} disabled={isGenerating}>
					Cancel
				</Button>
			</div>
		</div>
	);
}

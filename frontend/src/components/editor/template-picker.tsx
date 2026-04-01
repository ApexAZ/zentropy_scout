"use client";

/**
 * @fileoverview Template picker for resume creation.
 *
 * Layer: component
 * Feature: resume
 *
 * REQ-025 §6.3: Grid of template cards with selection state.
 * Fetches templates from GET /resume-templates.
 *
 * Coordinates with:
 * - lib/api-client.ts: apiGet for fetching resume templates
 * - lib/query-keys.ts: queryKeys.resumeTemplates cache key
 * - types/resume.ts: ResumeTemplate type
 *
 * Called by / Used by:
 * - components/resume/new-resume-wizard.tsx: template selection step in new resume wizard
 */

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ResumeTemplate } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TemplateListResponse {
	templates: ResumeTemplate[];
}

interface TemplatePickerProps {
	selectedId: string | null;
	onSelect: (templateId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TemplatePicker({
	selectedId,
	onSelect,
}: Readonly<TemplatePickerProps>) {
	const { data, isLoading } = useQuery({
		queryKey: queryKeys.resumeTemplates,
		queryFn: () => apiGet<TemplateListResponse>("/resume-templates"),
	});

	// Auto-select the first template when loaded and nothing is selected
	const firstTemplateId = data?.templates?.[0]?.id ?? null;
	useEffect(() => {
		if (firstTemplateId && !selectedId) {
			onSelect(firstTemplateId);
		}
	}, [firstTemplateId, selectedId, onSelect]);

	if (isLoading) {
		return (
			<div
				data-testid="template-picker-loading"
				className="flex justify-center py-6"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	const templates = data?.templates ?? [];

	if (templates.length === 0) {
		return (
			<p className="text-muted-foreground py-4 text-sm">
				No templates available.
			</p>
		);
	}

	return (
		<div
			className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
			aria-label="Resume templates"
			data-testid="template-picker"
		>
			{templates.map((template) => {
				const isSelected = template.id === selectedId;
				return (
					<button
						key={template.id}
						type="button"
						aria-pressed={isSelected}
						onClick={() => onSelect(template.id)}
						data-testid={`template-card-${template.id}`}
						className={`rounded-lg border p-4 text-left transition-colors ${
							isSelected
								? "border-primary bg-primary/5 ring-primary ring-2"
								: "border-border hover:border-primary/50"
						}`}
					>
						<h3 className="text-sm font-medium">{template.name}</h3>
						{template.description && (
							<p className="text-muted-foreground mt-1 text-xs">
								{template.description}
							</p>
						)}
						{template.is_system && (
							<span className="text-muted-foreground mt-2 inline-block text-xs">
								System template
							</span>
						)}
					</button>
				);
			})}
		</div>
	);
}

export type { TemplatePickerProps };

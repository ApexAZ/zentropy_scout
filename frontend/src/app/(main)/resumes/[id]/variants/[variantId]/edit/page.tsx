"use client";

/**
 * Variant edit page route.
 *
 * REQ-027 §3.5, §4.3–§4.4: TipTap editor with job requirements panel
 * and persona reference panel for editing job variants.
 */

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Save } from "lucide-react";
import Link from "next/link";

import { apiGet, apiPatch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { ResumeEditor } from "@/components/editor/resume-editor";
import { JobRequirementsPanel } from "@/components/editor/job-requirements-panel";
import { PersonaReferencePanel } from "@/components/editor/persona-reference-panel";
import { Button } from "@/components/ui/button";
import { FailedState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import { usePersonaStatus } from "@/hooks/use-persona-status";
import type { ApiResponse } from "@/types/api";
import type { BaseResume, JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** UUID v4 format pattern for route param validation (defense-in-depth). */
const UUID_PATTERN =
	/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function VariantEditPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string; variantId: string }>();
	const queryClient = useQueryClient();
	const [markdownContent, setMarkdownContent] = useState<string | null>(null);
	const [isSaving, setIsSaving] = useState(false);

	const isValidParams =
		UUID_PATTERN.test(params.id) && UUID_PATTERN.test(params.variantId);

	const {
		data: variantData,
		isLoading: variantLoading,
		error: variantError,
	} = useQuery({
		queryKey: queryKeys.variant(params.variantId),
		queryFn: () =>
			apiGet<ApiResponse<JobVariant>>(`/job-variants/${params.variantId}`),
		enabled: isValidParams,
	});

	const {
		data: resumeData,
		isLoading: resumeLoading,
		error: resumeError,
	} = useQuery({
		queryKey: queryKeys.baseResume(params.id),
		queryFn: () =>
			apiGet<ApiResponse<BaseResume>>(`/base-resumes/${params.id}`),
		enabled: isValidParams,
	});

	const variant = variantData?.data;
	const resume = resumeData?.data;
	const isDraft = variant?.status === "Draft";
	// Fall back to persona from hook when resume hasn't loaded yet
	const personaId =
		resume?.persona_id ??
		(personaStatus.status === "onboarded"
			? personaStatus.persona.id
			: undefined);

	const handleSave = useCallback(async () => {
		if (!variant || markdownContent === null) return;
		setIsSaving(true);
		try {
			await apiPatch(`/job-variants/${variant.id}`, {
				markdown_content: markdownContent,
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.variant(variant.id),
			});
			showToast.success("Variant saved.");
		} catch {
			showToast.error("Failed to save variant.");
		} finally {
			setIsSaving(false);
		}
	}, [variant, markdownContent, queryClient]);

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	const isLoading = variantLoading || resumeLoading;
	const error = variantError ?? resumeError;

	if (personaStatus.status !== "onboarded") return null;

	if (!isValidParams) {
		return <FailedState />;
	}

	if (isLoading) {
		return (
			<div
				data-testid="variant-edit-loading"
				className="flex justify-center py-8"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	if (error || !variant) {
		return <FailedState />;
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="variant-edit-page" className="flex h-full flex-col">
			{/* Header */}
			<div className="flex items-center justify-between border-b px-4 py-3">
				<div className="flex items-center gap-3">
					<Link
						href={`/resumes/${params.id}`}
						aria-label="Back to resume detail"
						className="text-muted-foreground hover:text-foreground"
					>
						<ArrowLeft className="h-5 w-5" />
					</Link>
					<h1 className="text-lg font-semibold">
						{variant.summary ?? "Edit Variant"}
					</h1>
					<StatusBadge status={variant.status} />
				</div>
				{isDraft && (
					<Button
						data-testid="save-variant-button"
						size="sm"
						disabled={isSaving || markdownContent === null}
						onClick={() => void handleSave()}
						className="gap-2"
					>
						{isSaving ? (
							<Loader2 className="h-4 w-4 animate-spin" />
						) : (
							<Save className="h-4 w-4" />
						)}
						Save
					</Button>
				)}
			</div>

			{/* Main content — editor + side panels */}
			<div className="flex min-h-0 flex-1">
				{/* Editor */}
				<div className="flex-1 overflow-y-auto">
					<ResumeEditor
						initialContent={variant.markdown_content ?? ""}
						editable={isDraft}
						onChange={setMarkdownContent}
					/>
				</div>

				{/* Side panels (hidden on mobile, visible on md+) */}
				<aside className="bg-card hidden w-72 shrink-0 space-y-4 overflow-y-auto border-l p-3 md:block">
					{variant.job_posting_id && (
						<JobRequirementsPanel jobPostingId={variant.job_posting_id} />
					)}
					{personaId && <PersonaReferencePanel personaId={personaId} />}
				</aside>
			</div>
		</div>
	);
}

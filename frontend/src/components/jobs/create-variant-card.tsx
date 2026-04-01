"use client";

/**
 * @fileoverview Variant creation card for the job detail page.
 *
 * Layer: component
 * Feature: jobs
 *
 * REQ-027 §4.1–§4.3: Two creation paths — "Draft Resume" (AI tailoring)
 * and "Create Variant" (manual copy). Both call POST /job-variants/create-for-job
 * and navigate to the variant editor on success.
 *
 * Coordinates with:
 * - lib/api-client.ts: apiGet, apiPost for resume fetching and variant creation
 * - lib/query-keys.ts: queryKeys.baseResumes cache key
 * - lib/toast.ts: showToast for success/error feedback
 * - components/ui/button.tsx: action buttons
 * - components/ui/card.tsx: Card, CardContent, CardHeader, CardTitle layout
 * - types/api.ts: ApiListResponse, ApiResponse envelopes
 * - types/resume.ts: BaseResume, JobVariant types
 *
 * Called by / Used by:
 * - app/(main)/jobs/[id]/page.tsx: job detail page
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { FileText, Loader2, Sparkles } from "lucide-react";

import { apiGet, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { BaseResume, JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CreateVariantCardProps {
	jobPostingId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CreateVariantCard({
	jobPostingId,
}: Readonly<CreateVariantCardProps>) {
	const router = useRouter();
	const [isCreating, setIsCreating] = useState(false);
	const [selectedResumeId, setSelectedResumeId] = useState<string | null>(null);

	const { data: resumesData, isLoading } = useQuery({
		queryKey: queryKeys.baseResumes,
		queryFn: () => apiGet<ApiListResponse<BaseResume>>("/base-resumes"),
	});

	const activeResumes = useMemo(() => {
		if (!resumesData?.data) return [];
		return resumesData.data.filter((r) => r.status === "Active");
	}, [resumesData]);

	// Auto-select primary resume or first available
	const effectiveResumeId = useMemo(() => {
		if (selectedResumeId) return selectedResumeId;
		const primary = activeResumes.find((r) => r.is_primary);
		return primary?.id ?? activeResumes[0]?.id ?? null;
	}, [activeResumes, selectedResumeId]);

	const handleCreate = useCallback(
		async (method: "manual" | "ai") => {
			if (!effectiveResumeId) return;
			setIsCreating(true);
			try {
				const result = await apiPost<ApiResponse<JobVariant>>(
					"/job-variants/create-for-job",
					{
						base_resume_id: effectiveResumeId,
						job_posting_id: jobPostingId,
						method,
					},
				);
				const variant = result.data;
				showToast.success(
					method === "ai"
						? "Resume drafted with AI tailoring."
						: "Variant created from base resume.",
				);
				router.push(
					`/resumes/${variant.base_resume_id}/variants/${variant.id}/edit`,
				);
			} catch {
				showToast.error("Failed to create variant.");
			} finally {
				setIsCreating(false);
			}
		},
		[effectiveResumeId, jobPostingId, router],
	);

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				data-testid="create-variant-loading"
				className="flex justify-center py-6"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// No base resumes
	// -----------------------------------------------------------------------

	if (activeResumes.length === 0) {
		return (
			<Card data-testid="create-variant-card">
				<CardHeader>
					<CardTitle>Create Variant</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-muted-foreground text-sm">
						Create a base resume first before creating job variants.
					</p>
				</CardContent>
			</Card>
		);
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<Card data-testid="create-variant-card">
			<CardHeader>
				<CardTitle>Create Variant</CardTitle>
			</CardHeader>
			<CardContent className="space-y-3">
				<p className="text-muted-foreground text-sm">
					Create a tailored resume variant for this job posting.
				</p>

				{/* Resume selector (shown when multiple resumes exist) */}
				{activeResumes.length > 1 && (
					<div data-testid="resume-selector">
						<label
							htmlFor="base-resume-select"
							className="text-muted-foreground mb-1 block text-xs font-medium"
						>
							Base Resume
						</label>
						<select
							id="base-resume-select"
							value={effectiveResumeId ?? ""}
							onChange={(e) => setSelectedResumeId(e.target.value)}
							className="border-input bg-background text-foreground ring-offset-background focus-visible:ring-ring w-full rounded-md border px-3 py-1.5 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
						>
							{activeResumes.map((r) => (
								<option key={r.id} value={r.id}>
									{r.name}
									{r.is_primary ? " (Primary)" : ""}
								</option>
							))}
						</select>
					</div>
				)}

				<div className="flex items-center gap-2">
					<Button
						data-testid="draft-resume-button"
						disabled={isCreating}
						onClick={() => void handleCreate("ai")}
						className="gap-2"
					>
						{isCreating ? (
							<Loader2 className="h-4 w-4 animate-spin" />
						) : (
							<Sparkles className="h-4 w-4" />
						)}
						Draft Resume
					</Button>
					<Button
						data-testid="create-variant-button"
						variant="outline"
						disabled={isCreating}
						onClick={() => void handleCreate("manual")}
						className="gap-2"
					>
						<FileText className="h-4 w-4" />
						Create Variant
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}

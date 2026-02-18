"use client";

/**
 * "Draft Materials" card for the job detail page.
 *
 * REQ-012 §8.3: Bottom action bar includes "Draft Materials" button.
 * REQ-012 §15.7: Sends chat message to trigger ghostwriter agent,
 * shows pending state while generating.
 *
 * Hidden when any non-archived variant or cover letter already exists
 * for this job, since materials have already been started or completed.
 */

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { useChat } from "@/lib/chat-provider";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApiListResponse } from "@/types/api";
import type { CoverLetter } from "@/types/application";
import type { JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** UUID v4 format pattern for job ID validation (defense-in-depth). */
const UUID_PATTERN =
	/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const DRAFTING_ERROR_MESSAGE = "Failed to start drafting materials.";
const DRAFTING_INFO_MESSAGE =
	"Drafting started — check the chat panel for progress.";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DraftMaterialsCardProps {
	jobId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DraftMaterialsCard({
	jobId,
}: Readonly<DraftMaterialsCardProps>) {
	const { sendMessage, isStreaming } = useChat();
	const [isDrafting, setIsDrafting] = useState(false);

	// -----------------------------------------------------------------------
	// Data fetching — check for existing materials
	// -----------------------------------------------------------------------

	const { data: variantsData, isLoading: variantsLoading } = useQuery({
		queryKey: [...queryKeys.variants, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<JobVariant>>("/variants", {
				job_posting_id: jobId,
			}),
	});

	const { data: coverLettersData, isLoading: coverLettersLoading } = useQuery({
		queryKey: [...queryKeys.coverLetters, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<CoverLetter>>("/cover-letters", {
				job_posting_id: jobId,
			}),
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleDraft = useCallback(async () => {
		if (!UUID_PATTERN.test(jobId)) return;
		setIsDrafting(true);
		try {
			await sendMessage(`Draft materials for job ${jobId}`);
			showToast.info(DRAFTING_INFO_MESSAGE);
		} catch {
			showToast.error(DRAFTING_ERROR_MESSAGE);
		} finally {
			setIsDrafting(false);
		}
	}, [sendMessage, jobId]);

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	const isLoading = variantsLoading || coverLettersLoading;

	if (isLoading) {
		return (
			<div
				data-testid="draft-materials-loading"
				className="flex justify-center py-6"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Hidden when materials already exist (non-archived)
	// -----------------------------------------------------------------------

	const hasActiveVariant =
		variantsData?.data.some((v) => v.status !== "Archived") ?? false;
	const hasActiveCoverLetter =
		coverLettersData?.data.some((cl) => cl.status !== "Archived") ?? false;

	if (hasActiveVariant || hasActiveCoverLetter) {
		return null;
	}

	// -----------------------------------------------------------------------
	// Render — no materials, show draft button
	// -----------------------------------------------------------------------

	return (
		<Card data-testid="draft-materials-card">
			<CardHeader>
				<CardTitle>Draft Materials</CardTitle>
			</CardHeader>
			<CardContent className="space-y-3">
				<p className="text-muted-foreground text-sm">
					Generate a tailored resume variant and cover letter for this job
					posting.
				</p>
				<Button
					data-testid="draft-materials-button"
					disabled={isDrafting || isStreaming}
					onClick={() => void handleDraft()}
					className="gap-2"
				>
					{isDrafting ? (
						<Loader2 className="h-4 w-4 animate-spin" />
					) : (
						<Sparkles className="h-4 w-4" />
					)}
					{isDrafting ? "Drafting..." : "Draft Materials"}
				</Button>
			</CardContent>
		</Card>
	);
}

"use client";

/**
 * Job detail page action buttons: Rescore, Dismiss, Undismiss.
 *
 * REQ-015 §9.2: Rescore triggers re-scoring of all discovered jobs.
 * REQ-015 §4.5: Dismiss is reversible (Discovered ↔ Dismissed).
 * Shared data is immutable — only per-user persona_jobs fields change.
 */

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiPatch, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import type { JobPostingStatus } from "@/types/job";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SPINNER_CLASS = "mr-1 h-4 w-4 animate-spin";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface JobDetailActionsProps {
	personaJobId: string;
	status: JobPostingStatus;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function JobDetailActions({
	personaJobId,
	status,
}: Readonly<JobDetailActionsProps>) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [isRescoring, setIsRescoring] = useState(false);
	const [isDismissing, setIsDismissing] = useState(false);

	const handleRescore = useCallback(async () => {
		setIsRescoring(true);
		try {
			await apiPost("/job-postings/rescore");
			showToast.success("Rescoring started.");
			await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
		} catch {
			showToast.error("Failed to start rescoring.");
		} finally {
			setIsRescoring(false);
		}
	}, [queryClient]);

	const handleDismiss = useCallback(async () => {
		setIsDismissing(true);
		try {
			await apiPatch(`/job-postings/${personaJobId}`, {
				status: "Dismissed",
			});
			showToast.success("Job dismissed.");
			await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
			router.push("/");
		} catch {
			showToast.error("Failed to dismiss job.");
		} finally {
			setIsDismissing(false);
		}
	}, [personaJobId, queryClient, router]);

	const handleUndismiss = useCallback(async () => {
		setIsDismissing(true);
		try {
			await apiPatch(`/job-postings/${personaJobId}`, {
				status: "Discovered",
			});
			showToast.success("Job restored.");
			await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
		} catch {
			showToast.error("Failed to restore job.");
		} finally {
			setIsDismissing(false);
		}
	}, [personaJobId, queryClient]);

	const isDiscovered = status === "Discovered";
	const isDismissed = status === "Dismissed";

	if (!isDiscovered && !isDismissed) return null;

	return (
		<div data-testid="job-detail-actions" className="flex items-center gap-2">
			{isDiscovered && (
				<>
					<Button
						variant="outline"
						size="sm"
						disabled={isRescoring}
						onClick={() => void handleRescore()}
					>
						{isRescoring && <Loader2 className={SPINNER_CLASS} />}
						Rescore
					</Button>
					<Button
						variant="ghost"
						size="sm"
						disabled={isDismissing}
						onClick={() => void handleDismiss()}
					>
						{isDismissing && <Loader2 className={SPINNER_CLASS} />}
						Dismiss
					</Button>
				</>
			)}
			{isDismissed && (
				<Button
					variant="outline"
					size="sm"
					disabled={isDismissing}
					onClick={() => void handleUndismiss()}
				>
					{isDismissing && <Loader2 className={SPINNER_CLASS} />}
					Undismiss
				</Button>
			)}
		</div>
	);
}

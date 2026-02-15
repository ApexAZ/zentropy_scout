"use client";

/**
 * Status transition dropdown for application detail pages.
 *
 * REQ-012 §11.3: Status update dropdown with conditional prompts.
 * Transition matrix:
 *   Applied → Interviewing, Rejected, Withdrawn
 *   Interviewing → Offer, Rejected, Withdrawn
 *   Offer → Accepted, Rejected, Withdrawn
 *   Accepted/Rejected/Withdrawn → (terminal, disabled)
 *
 * Conditional prompts:
 *   → Interviewing: Interview stage selector (Phone Screen / Onsite / Final Round)
 *   → Accepted/Withdrawn: Simple confirmation dialog
 *   → Offer/Rejected: Simple confirmation (detail forms in §10.5/§10.6)
 */

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { apiPatch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { InterviewStageDialog } from "./interview-stage-dialog";
import type { ApplicationStatus, InterviewStage } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_UPDATE_ERROR = "Failed to update status.";

/**
 * Allowed status transitions per current status.
 * Terminal statuses (Accepted, Rejected, Withdrawn) have no transitions.
 */
const STATUS_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
	Applied: ["Interviewing", "Rejected", "Withdrawn"],
	Interviewing: ["Offer", "Rejected", "Withdrawn"],
	Offer: ["Accepted", "Rejected", "Withdrawn"],
	Accepted: [],
	Rejected: [],
	Withdrawn: [],
};

const TERMINAL_STATUSES: ReadonlySet<ApplicationStatus> = new Set([
	"Accepted",
	"Rejected",
	"Withdrawn",
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StatusTransitionDropdownProps {
	applicationId: string;
	currentStatus: ApplicationStatus;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StatusTransitionDropdown({
	applicationId,
	currentStatus,
}: StatusTransitionDropdownProps) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	const [targetStatus, setTargetStatus] = useState<ApplicationStatus | null>(
		null,
	);
	const [loading, setLoading] = useState(false);

	// Interview stage dialog state
	const [showInterviewStageDialog, setShowInterviewStageDialog] =
		useState(false);

	// Confirmation dialog state
	const [showConfirmation, setShowConfirmation] = useState(false);

	// -----------------------------------------------------------------------
	// Computed
	// -----------------------------------------------------------------------

	const isTerminal = TERMINAL_STATUSES.has(currentStatus);
	const availableTransitions = STATUS_TRANSITIONS[currentStatus];

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleStatusSelect = useCallback(
		(value: string) => {
			if (!availableTransitions.includes(value as ApplicationStatus)) return;
			const selected = value as ApplicationStatus;
			setTargetStatus(selected);

			if (selected === "Interviewing") {
				setShowInterviewStageDialog(true);
			} else {
				setShowConfirmation(true);
			}
		},
		[availableTransitions],
	);

	const handleConfirmTransition = useCallback(
		async (body: Record<string, unknown>) => {
			setLoading(true);
			try {
				await apiPatch(`/applications/${applicationId}`, body);
				await queryClient.invalidateQueries({
					queryKey: queryKeys.application(applicationId),
				});
				showToast.success(`Status updated to ${body.status as string}.`);
			} catch {
				showToast.error(STATUS_UPDATE_ERROR);
			} finally {
				setLoading(false);
				setShowConfirmation(false);
				setShowInterviewStageDialog(false);
				setTargetStatus(null);
			}
		},
		[applicationId, queryClient],
	);

	const handleConfirmSimple = useCallback(() => {
		if (!targetStatus) return;
		void handleConfirmTransition({ status: targetStatus });
	}, [targetStatus, handleConfirmTransition]);

	const handleConfirmInterviewStage = useCallback(
		(stage: InterviewStage) => {
			void handleConfirmTransition({
				status: "Interviewing",
				current_interview_stage: stage,
			});
		},
		[handleConfirmTransition],
	);

	const handleCancel = useCallback(() => {
		setShowConfirmation(false);
		setShowInterviewStageDialog(false);
		setTargetStatus(null);
	}, []);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<>
			<Select value="" onValueChange={handleStatusSelect} disabled={isTerminal}>
				<SelectTrigger
					aria-label="Update status"
					size="sm"
					data-testid="status-transition-trigger"
				>
					<SelectValue placeholder="Update Status" />
				</SelectTrigger>
				<SelectContent>
					{availableTransitions.map((status) => (
						<SelectItem key={status} value={status}>
							{status}
						</SelectItem>
					))}
				</SelectContent>
			</Select>

			{/* Confirmation dialog for simple transitions */}
			<ConfirmationDialog
				open={showConfirmation}
				onOpenChange={(open) => {
					if (!open) handleCancel();
				}}
				title={`Mark as ${targetStatus ?? ""}`}
				description={`Are you sure you want to change the status to "${targetStatus ?? ""}"? This action cannot be undone.`}
				onConfirm={handleConfirmSimple}
				confirmLabel="Confirm"
				loading={loading}
			/>

			{/* Interview stage dialog */}
			<InterviewStageDialog
				open={showInterviewStageDialog}
				onConfirm={handleConfirmInterviewStage}
				onCancel={handleCancel}
				loading={loading}
			/>
		</>
	);
}

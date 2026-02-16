"use client";

/**
 * Read-only card displaying captured rejection details.
 *
 * REQ-012 §11.6: Rejection details display with stage, reason,
 * feedback, and rejection date.
 * Shown on application detail page when status is Rejected.
 */

import { Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RejectionDetails } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LABEL_CLASS = "text-muted-foreground text-sm";
const VALUE_CLASS = "text-sm font-medium";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RejectionDetailsCardProps {
	rejectionDetails: RejectionDetails;
	onEdit: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateTime(isoString: string): string {
	const date = new Date(isoString);
	if (Number.isNaN(date.getTime())) return "Unknown";
	return date.toLocaleDateString("en-US", {
		month: "short",
		day: "numeric",
		year: "numeric",
		timeZone: "UTC",
	});
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RejectionDetailsCard({
	rejectionDetails,
	onEdit,
}: Readonly<RejectionDetailsCardProps>) {
	const { stage, reason, feedback, rejected_at } = rejectionDetails;

	const hasStage = stage !== undefined && stage !== "";
	const hasReason = reason !== undefined && reason !== "";
	const hasFeedback = feedback !== undefined && feedback !== "";
	const hasRejectedAt = rejected_at !== undefined && rejected_at !== "";

	return (
		<Card data-testid="rejection-details-card">
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
				<CardTitle className="text-base">Rejection Details</CardTitle>
				<Button variant="ghost" size="sm" onClick={onEdit} className="gap-1">
					<Pencil className="h-3.5 w-3.5" />
					Edit
				</Button>
			</CardHeader>
			<CardContent className="space-y-3">
				{hasStage && (
					<div data-testid="rejection-stage-row">
						<p className={LABEL_CLASS}>Stage</p>
						<p className={VALUE_CLASS}>{stage}</p>
					</div>
				)}

				{hasReason && (
					<div data-testid="rejection-reason-row">
						<p className={LABEL_CLASS}>Reason</p>
						<p className={VALUE_CLASS}>{reason}</p>
					</div>
				)}

				{hasFeedback && (
					<div data-testid="rejection-feedback-row">
						<p className={LABEL_CLASS}>Feedback</p>
						<p className={VALUE_CLASS}>{feedback}</p>
					</div>
				)}

				{hasRejectedAt && (
					<div data-testid="rejection-date-row">
						<p className={LABEL_CLASS}>Rejected</p>
						<p className={VALUE_CLASS}>{formatDateTime(rejected_at)}</p>
					</div>
				)}
			</CardContent>
		</Card>
	);
}

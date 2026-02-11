/**
 * Color-coded status badge for application, document, and job posting statuses.
 *
 * REQ-012 §11.1: Application status badge colors (Applied=Blue, Interviewing=Amber,
 *   Offer=Green, Accepted=Green bold, Rejected=Red, Withdrawn=Gray).
 * REQ-012 §8.5: "Filtered" badge for non-negotiable failures.
 * REQ-012 §9.2: Draft/Approved document status display.
 *
 * Accepts a status string and renders a pill-shaped badge with the appropriate
 * color. Covers ApplicationStatus, JobPostingStatus, document statuses
 * (Draft/Approved/Archived), BaseResumeStatus (Active/Archived), and the
 * special "Filtered" status for non-negotiable filter failures.
 */

import type { ApplicationStatus, CoverLetterStatus } from "@/types/application";
import type { JobPostingStatus } from "@/types/job";
import type { BaseResumeStatus, JobVariantStatus } from "@/types/resume";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StatusBadgeStatus =
	| ApplicationStatus
	| JobPostingStatus
	| CoverLetterStatus
	| JobVariantStatus
	| BaseResumeStatus
	| "Filtered";

interface StatusBadgeProps {
	status: StatusBadgeStatus;
	className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BASE_CLASSES =
	"inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";

const STATUS_STYLES: Record<StatusBadgeStatus, string> = {
	// Application statuses (REQ-012 §11.1)
	Applied: "bg-primary text-primary-foreground",
	Interviewing: "bg-warning text-warning-foreground",
	Offer: "bg-success text-success-foreground",
	Accepted: "bg-success text-success-foreground font-semibold",
	Rejected: "bg-destructive text-destructive-foreground",
	Withdrawn: "bg-muted text-muted-foreground",

	// Job posting statuses
	Discovered: "bg-info text-info-foreground",
	Dismissed: "bg-muted text-muted-foreground",
	Expired: "bg-destructive text-destructive-foreground",

	// Document statuses (covers CoverLetterStatus, JobVariantStatus, BaseResumeStatus)
	Draft: "bg-warning text-warning-foreground",
	Approved: "bg-success text-success-foreground",
	Archived: "bg-muted text-muted-foreground",
	Active: "bg-success text-success-foreground",

	// Special
	Filtered: "bg-destructive text-destructive-foreground",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function StatusBadge({ status, className }: StatusBadgeProps) {
	return (
		<span
			data-slot="status-badge"
			data-status={status}
			aria-label={`Status: ${status}`}
			className={cn(BASE_CLASSES, STATUS_STYLES[status], className)}
		>
			{status}
		</span>
	);
}

export { StatusBadge };
export type { StatusBadgeProps, StatusBadgeStatus };

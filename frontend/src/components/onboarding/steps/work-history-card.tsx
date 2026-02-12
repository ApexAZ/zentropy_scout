"use client";

/**
 * Work history card for displaying a job entry in the onboarding wizard.
 *
 * REQ-012 §6.3.3: Each card shows title, company, dates, location, work model
 * with edit/delete action buttons.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { WorkHistory } from "@/types/persona";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format an ISO date string (YYYY-MM-DD) as "Mon YYYY". */
function formatMonthYear(isoDate: string): string {
	const [year, month] = isoDate.split("-");
	const monthNames = [
		"Jan",
		"Feb",
		"Mar",
		"Apr",
		"May",
		"Jun",
		"Jul",
		"Aug",
		"Sep",
		"Oct",
		"Nov",
		"Dec",
	];
	const monthIndex = parseInt(month, 10) - 1;
	return `${monthNames[monthIndex]} ${year}`;
}

/** Build the date range display string. */
function formatDateRange(entry: WorkHistory): string {
	const start = formatMonthYear(entry.start_date);
	if (entry.is_current) {
		return `${start} – Present`;
	}
	if (entry.end_date) {
		return `${start} – ${formatMonthYear(entry.end_date)}`;
	}
	return start;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkHistoryCardProps {
	entry: WorkHistory;
	onEdit: (entry: WorkHistory) => void;
	onDelete: (entry: WorkHistory) => void;
	dragHandle: React.ReactNode | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WorkHistoryCard({
	entry,
	onEdit,
	onDelete,
	dragHandle,
}: WorkHistoryCardProps) {
	return (
		<div className="bg-card flex items-start gap-3 rounded-lg border p-4">
			{dragHandle}
			<div className="min-w-0 flex-1">
				<div className="flex items-start justify-between gap-2">
					<div className="min-w-0">
						<h3 className="truncate font-medium">{entry.job_title}</h3>
						<p className="text-muted-foreground text-sm">
							{entry.company_name}
						</p>
					</div>
					<div className="flex shrink-0 gap-1">
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8"
							onClick={() => onEdit(entry)}
							aria-label={`Edit ${entry.job_title}`}
						>
							<Pencil className="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="icon"
							className="h-8 w-8"
							onClick={() => onDelete(entry)}
							aria-label={`Delete ${entry.job_title}`}
						>
							<Trash2 className="h-4 w-4" />
						</Button>
					</div>
				</div>
				<p className="text-muted-foreground mt-1 text-sm">
					{formatDateRange(entry)}
				</p>
				<p className="text-muted-foreground mt-0.5 text-sm">
					{entry.location} &middot; {entry.work_model}
				</p>
			</div>
		</div>
	);
}

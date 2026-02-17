/**
 * Expandable job snapshot section for application detail page.
 *
 * REQ-012 §11.10: Shows frozen job data at application time in a
 * collapsible card. Always displays captured_at and optional
 * "View live posting" link. Expanded view shows description,
 * requirements, salary, location, and work model.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";

import { formatDateTimeAgo, formatSnapshotSalary } from "@/lib/job-formatters";
import { isSafeUrl } from "@/lib/url-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { JobSnapshot } from "@/types/application";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface JobSnapshotSectionProps {
	snapshot: JobSnapshot;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function JobSnapshotSection({
	snapshot,
}: Readonly<JobSnapshotSectionProps>) {
	const [expanded, setExpanded] = useState(false);

	return (
		<Card data-testid="job-snapshot-section">
			<CardHeader>
				<CardTitle className="text-sm">Job Snapshot</CardTitle>
			</CardHeader>
			<CardContent>
				<p className="text-muted-foreground mb-2 text-sm">
					Captured {formatDateTimeAgo(snapshot.captured_at)}
				</p>
				<div className="flex items-center gap-2">
					{snapshot.source_url && isSafeUrl(snapshot.source_url) && (
						<Button
							variant="outline"
							size="sm"
							asChild
							data-testid="view-live-posting"
						>
							<a
								href={snapshot.source_url}
								target="_blank"
								rel="noopener noreferrer"
							>
								<ExternalLink className="mr-1 h-4 w-4" />
								View live posting
							</a>
						</Button>
					)}
				</div>

				{/* Expand/Collapse toggle */}
				<button
					type="button"
					data-testid="snapshot-toggle"
					aria-expanded={expanded}
					onClick={() => setExpanded((prev) => !prev)}
					className="mt-3 flex items-center gap-2"
				>
					{expanded ? (
						<ChevronDown className="h-4 w-4" />
					) : (
						<ChevronRight className="h-4 w-4" />
					)}
					<span className="text-sm font-semibold">
						{expanded ? "Hide details" : "Show details"}
					</span>
				</button>

				{/* Expanded details */}
				{expanded && (
					<div
						data-testid="snapshot-details"
						className="mt-3 space-y-3 border-t pt-3"
					>
						<div>
							<p className="text-xs font-medium tracking-wide uppercase">
								Description
							</p>
							<p
								data-testid="snapshot-description"
								className="text-muted-foreground mt-1 text-sm whitespace-pre-wrap"
							>
								{snapshot.description}
							</p>
						</div>

						<div>
							<p className="text-xs font-medium tracking-wide uppercase">
								Requirements
							</p>
							<p
								data-testid="snapshot-requirements"
								className="text-muted-foreground mt-1 text-sm"
							>
								{snapshot.requirements ?? "Not specified"}
							</p>
						</div>

						<div>
							<p className="text-xs font-medium tracking-wide uppercase">
								Salary
							</p>
							<p
								data-testid="snapshot-salary"
								className="text-muted-foreground mt-1 text-sm"
							>
								{formatSnapshotSalary(
									snapshot.salary_min,
									snapshot.salary_max,
									snapshot.salary_currency ?? undefined,
								)}
							</p>
						</div>

						<div>
							<p className="text-xs font-medium tracking-wide uppercase">
								Location
							</p>
							<p
								data-testid="snapshot-location"
								className="text-muted-foreground mt-1 text-sm"
							>
								{snapshot.location ?? "Not specified"}
							</p>
						</div>

						<div>
							<p className="text-xs font-medium tracking-wide uppercase">
								Work Model
							</p>
							<p
								data-testid="snapshot-work-model"
								className="text-muted-foreground mt-1 text-sm"
							>
								{snapshot.work_model ?? "Not specified"}
							</p>
						</div>
					</div>
				)}
			</CardContent>
		</Card>
	);
}

"use client";

/**
 * Education card for displaying an education entry in the onboarding wizard.
 *
 * REQ-012 §6.3.4: Each card shows degree, field, institution, year,
 * optional GPA/honors with edit/delete action buttons.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Education } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EducationCardProps {
	entry: Education;
	onEdit: (entry: Education) => void;
	onDelete: (entry: Education) => void;
	dragHandle: React.ReactNode | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EducationCard({
	entry,
	onEdit,
	onDelete,
	dragHandle,
}: Readonly<EducationCardProps>) {
	return (
		<div className="bg-card rounded-lg border">
			<div className="flex items-start gap-3 p-4">
				{dragHandle}
				<div className="min-w-0 flex-1">
					<div className="flex items-start justify-between gap-2">
						<div className="min-w-0">
							<h3 className="truncate font-medium">
								{entry.degree} in {entry.field_of_study}
							</h3>
							<p className="text-muted-foreground text-sm">
								{entry.institution}
							</p>
						</div>
						<div className="flex shrink-0 gap-1">
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onEdit(entry)}
								aria-label={`Edit ${entry.degree}`}
							>
								<Pencil className="h-4 w-4" />
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onDelete(entry)}
								aria-label={`Delete ${entry.degree}`}
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					</div>
					<p className="text-muted-foreground mt-1 text-sm">
						{entry.graduation_year}
						{entry.honors && ` \u00B7 ${entry.honors}`}
						{entry.gpa !== null && ` \u00B7 GPA: ${entry.gpa}`}
					</p>
				</div>
			</div>
		</div>
	);
}

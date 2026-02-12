"use client";

/**
 * Card for displaying a custom non-negotiable filter entry.
 *
 * REQ-012 §6.3.8: Each card shows filter_name, filter_type badge,
 * filter_field, and filter_value with edit/delete buttons.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { CustomNonNegotiable } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CustomFilterCardProps {
	entry: CustomNonNegotiable;
	onEdit: (entry: CustomNonNegotiable) => void;
	onDelete: (entry: CustomNonNegotiable) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CustomFilterCard({
	entry,
	onEdit,
	onDelete,
}: CustomFilterCardProps) {
	return (
		<div className="bg-card rounded-lg border" data-testid="custom-filter-card">
			<div className="flex items-start gap-3 p-4">
				<div className="min-w-0 flex-1">
					<div className="flex items-start justify-between gap-2">
						<div className="min-w-0">
							<div className="flex items-center gap-2">
								<h3 className="truncate font-medium">{entry.filter_name}</h3>
								<span className="bg-muted text-muted-foreground shrink-0 rounded px-1.5 py-0.5 text-xs font-medium">
									{entry.filter_type}
								</span>
							</div>
							<p className="text-muted-foreground text-sm">
								{entry.filter_field} &middot; {entry.filter_value}
							</p>
						</div>
						<div className="flex shrink-0 gap-1">
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onEdit(entry)}
								aria-label={`Edit ${entry.filter_name}`}
							>
								<Pencil className="h-4 w-4" />
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onDelete(entry)}
								aria-label={`Delete ${entry.filter_name}`}
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}

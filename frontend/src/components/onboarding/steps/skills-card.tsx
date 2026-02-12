"use client";

/**
 * Skills card for displaying a skill entry in the onboarding wizard.
 *
 * REQ-012 §6.3.5: Each card shows skill_name, skill_type badge,
 * category, proficiency, years_used, last_used with edit/delete buttons.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Skill } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SkillCardProps {
	entry: Skill;
	onEdit: (entry: Skill) => void;
	onDelete: (entry: Skill) => void;
	dragHandle: React.ReactNode | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SkillCard({
	entry,
	onEdit,
	onDelete,
	dragHandle,
}: SkillCardProps) {
	return (
		<div className="bg-card rounded-lg border">
			<div className="flex items-start gap-3 p-4">
				{dragHandle}
				<div className="min-w-0 flex-1">
					<div className="flex items-start justify-between gap-2">
						<div className="min-w-0">
							<div className="flex items-center gap-2">
								<h3 className="truncate font-medium">{entry.skill_name}</h3>
								<span className="bg-muted text-muted-foreground shrink-0 rounded px-1.5 py-0.5 text-xs font-medium">
									{entry.skill_type}
								</span>
							</div>
							<p className="text-muted-foreground text-sm">{entry.category}</p>
						</div>
						<div className="flex shrink-0 gap-1">
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onEdit(entry)}
								aria-label={`Edit ${entry.skill_name}`}
							>
								<Pencil className="h-4 w-4" />
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onDelete(entry)}
								aria-label={`Delete ${entry.skill_name}`}
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					</div>
					<p className="text-muted-foreground mt-1 text-sm">
						{entry.proficiency}
						{` \u00B7 ${entry.years_used} ${entry.years_used === 1 ? "year" : "years"}`}
						{` \u00B7 ${entry.last_used}`}
					</p>
				</div>
			</div>
		</div>
	);
}

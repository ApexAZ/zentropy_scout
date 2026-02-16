"use client";

/**
 * Story card for displaying an achievement story entry in the
 * onboarding wizard.
 *
 * REQ-012 §6.3.7: Each card shows title, Context, Action, Outcome,
 * skills demonstrated, with edit/delete buttons.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { AchievementStory, Skill } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shared label style for C/A/O field names. */
const LABEL_CLASS = "font-medium text-foreground";

interface StoryCardProps {
	entry: AchievementStory;
	skills: Skill[];
	onEdit: (entry: AchievementStory) => void;
	onDelete: (entry: AchievementStory) => void;
	dragHandle: React.ReactNode | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StoryCard({
	entry,
	skills,
	onEdit,
	onDelete,
	dragHandle,
}: Readonly<StoryCardProps>) {
	const skillNames = entry.skills_demonstrated
		.map((id) => skills.find((s) => s.id === id)?.skill_name)
		.filter(Boolean);

	return (
		<div className="bg-card rounded-lg border">
			<div className="flex items-start gap-3 p-4">
				{dragHandle}
				<div className="min-w-0 flex-1">
					<div className="flex items-start justify-between gap-2">
						<h3 className="truncate font-medium">{entry.title}</h3>
						<div className="flex shrink-0 gap-1">
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onEdit(entry)}
								aria-label={`Edit ${entry.title}`}
							>
								<Pencil className="h-4 w-4" />
							</Button>
							<Button
								variant="ghost"
								size="icon"
								className="h-8 w-8"
								onClick={() => onDelete(entry)}
								aria-label={`Delete ${entry.title}`}
							>
								<Trash2 className="h-4 w-4" />
							</Button>
						</div>
					</div>
					<div className="text-muted-foreground mt-2 space-y-1 text-sm">
						<p>
							<span className={LABEL_CLASS}>Context:</span> {entry.context}
						</p>
						<p>
							<span className={LABEL_CLASS}>Action:</span> {entry.action}
						</p>
						<p>
							<span className={LABEL_CLASS}>Outcome:</span> {entry.outcome}
						</p>
					</div>
					{skillNames.length > 0 && (
						<p className="text-muted-foreground mt-2 text-xs">
							Skills: {skillNames.join(", ")}
						</p>
					)}
				</div>
			</div>
		</div>
	);
}

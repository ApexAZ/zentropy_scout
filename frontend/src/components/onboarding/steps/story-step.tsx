"use client";

/**
 * Achievement Stories step for onboarding wizard (Step 7).
 *
 * REQ-012 §6.3.7: Conversational capture of Context/Action/Outcome
 * structured stories. Minimum 3 stories required before proceeding.
 * Review cards with edit/delete and reordering.
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { toFormValues, toRequestBody } from "@/lib/achievement-stories-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import { useCrudStep } from "@/hooks/use-crud-step";
import type { AchievementStory, Skill } from "@/types/persona";

import { StoryCard } from "./story-card";
import { StoryForm } from "./story-form";
import type { StoryFormData } from "./story-form";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MIN_STORIES = 3;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 7: Achievement Stories.
 *
 * Renders a list of story review cards with add/edit/delete and
 * drag-and-drop reordering. Minimum 3 stories required before the
 * user can proceed.
 */
export function StoryStep() {
	const { personaId, next, back } = useOnboarding();

	const [skills, setSkills] = useState<Skill[]>([]);

	const crud = useCrudStep<AchievementStory, StoryFormData>({
		personaId,
		collection: "achievement-stories",
		toFormValues,
		toRequestBody,
		hasDeleteError: true,
		secondaryFetch: {
			collection: "skills",
			onData: (data) => setSkills(data as Skill[]),
		},
	});

	// -----------------------------------------------------------------------
	// Story counter text
	// -----------------------------------------------------------------------

	function storyCounterText(count: number): string {
		if (count < MIN_STORIES) {
			return `${count} of 3\u20135 stories \u00B7 minimum ${MIN_STORIES} required`;
		}
		return `${count} of 3\u20135 stories`;
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (crud.isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-stories"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your achievement stories...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Achievement Stories</h2>
				<p className="text-muted-foreground mt-1">
					{crud.entries.length === 0
						? "Share stories of times you made a real impact."
						: storyCounterText(crud.entries.length)}
				</p>
			</div>

			{/* Form view (add or edit) */}
			{crud.viewMode !== "list" && (
				<StoryForm
					initialValues={
						crud.viewMode === "edit" && crud.editingEntry
							? toFormValues(crud.editingEntry)
							: undefined
					}
					onSave={
						crud.viewMode === "add" ? crud.handleSaveNew : crud.handleSaveEdit
					}
					onCancel={crud.handleCancel}
					isSubmitting={crud.isSubmitting}
					submitError={crud.submitError}
					skills={skills}
				/>
			)}

			{/* List view */}
			{crud.viewMode === "list" && (
				<>
					{crud.entries.length === 0 ? (
						<div className="text-muted-foreground py-8 text-center">
							<p>No stories yet.</p>
						</div>
					) : (
						<ReorderableList
							items={crud.entries}
							onReorder={crud.handleReorder}
							label="Achievement story entries"
							renderItem={(entry, dragHandle) => (
								<StoryCard
									entry={entry}
									skills={skills}
									onEdit={crud.handleEdit}
									onDelete={crud.handleDeleteRequest}
									dragHandle={dragHandle}
								/>
							)}
						/>
					)}

					<Button
						type="button"
						variant="outline"
						onClick={crud.handleAdd}
						className="self-center"
					>
						<Plus className="mr-2 h-4 w-4" />
						Add story
					</Button>
				</>
			)}

			{/* Navigation */}
			{crud.viewMode === "list" && (
				<div className="flex items-center justify-between pt-4">
					<Button
						type="button"
						variant="ghost"
						onClick={back}
						data-testid="back-button"
					>
						<ArrowLeft className="mr-2 h-4 w-4" />
						Back
					</Button>
					<Button
						type="button"
						onClick={next}
						disabled={crud.entries.length < MIN_STORIES}
						data-testid="next-button"
					>
						Next
					</Button>
				</div>
			)}

			{/* Delete confirmation dialog */}
			<ConfirmationDialog
				open={crud.deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) crud.handleDeleteCancel();
				}}
				title="Delete story"
				description={
					crud.deleteError
						? `Failed to delete "${crud.deleteTarget?.title ?? ""}". ${crud.deleteError}`
						: `Are you sure you want to delete "${crud.deleteTarget?.title ?? ""}"? This cannot be undone.`
				}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={crud.handleDeleteConfirm}
				loading={crud.isDeleting}
			/>
		</div>
	);
}

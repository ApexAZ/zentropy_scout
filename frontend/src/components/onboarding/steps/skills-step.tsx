"use client";

/**
 * Skills step for onboarding wizard (Step 5).
 *
 * REQ-012 §6.3.5: Not skippable. Skills editor with proficiency
 * selector, conditional category dropdown, CRUD, and reordering.
 * All 6 fields required per skill entry.
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { useCrudStep } from "@/hooks/use-crud-step";
import { useOnboarding } from "@/lib/onboarding-provider";
import { toFormValues, toRequestBody } from "@/lib/skills-helpers";
import type { Skill } from "@/types/persona";

import { SkillCard } from "./skills-card";
import { SkillForm } from "./skills-form";
import type { SkillFormData } from "./skills-form";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 5: Skills.
 *
 * Renders a list of skill cards with add/edit/delete and
 * drag-and-drop reordering. Not skippable — all 6 fields required.
 */
export function SkillsStep() {
	const { personaId, next, back } = useOnboarding();

	const crud = useCrudStep<Skill, SkillFormData>({
		personaId,
		collection: "skills",
		toFormValues,
		toRequestBody,
		hasDeleteError: true,
	});

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (crud.isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-skills"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your skills...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Skills</h2>
				<p className="text-muted-foreground mt-1">
					{crud.entries.length === 0
						? "Add your technical and professional skills."
						: "Your skills. Add, edit, or reorder as needed."}
				</p>
			</div>

			{/* Form view (add or edit) */}
			{crud.viewMode !== "list" && (
				<SkillForm
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
				/>
			)}

			{/* List view */}
			{crud.viewMode === "list" && (
				<>
					{crud.entries.length === 0 ? (
						<div className="text-muted-foreground py-8 text-center">
							<p>No skills yet.</p>
						</div>
					) : (
						<ReorderableList
							items={crud.entries}
							onReorder={crud.handleReorder}
							label="Skill entries"
							renderItem={(entry, dragHandle) => (
								<SkillCard
									entry={entry}
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
						Add skill
					</Button>
				</>
			)}

			{/* Navigation — no skip button (skills is not skippable) */}
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
					<Button type="button" onClick={next} data-testid="next-button">
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
				title="Delete skill"
				description={
					crud.deleteError
						? `Failed to delete "${crud.deleteTarget?.skill_name ?? ""}". ${crud.deleteError}`
						: `Are you sure you want to delete "${crud.deleteTarget?.skill_name ?? ""}"? This cannot be undone.`
				}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={crud.handleDeleteConfirm}
				loading={crud.isDeleting}
			/>
		</div>
	);
}

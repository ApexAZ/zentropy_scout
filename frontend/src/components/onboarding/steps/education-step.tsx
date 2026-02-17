"use client";

/**
 * Education step for onboarding wizard (Step 4).
 *
 * REQ-012 §6.3.4: Skippable step. Display education entries in editable
 * cards with add/edit/delete and ordering. 0 entries is valid (skip).
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { useCrudStep } from "@/hooks/use-crud-step";
import { toFormValues, toRequestBody } from "@/lib/education-helpers";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { Education } from "@/types/persona";

import { EducationCard } from "./education-card";
import { EducationForm } from "./education-form";
import type { EducationFormData } from "./education-form";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 4: Education.
 *
 * Renders a list of education cards with add/edit/delete and
 * drag-and-drop reordering. 0 entries is valid (step is skippable).
 */
export function EducationStep() {
	const { personaId, next, back, skip } = useOnboarding();

	const crud = useCrudStep<Education, EducationFormData>({
		personaId,
		collection: "education",
		toFormValues,
		toRequestBody,
	});

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (crud.isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-education"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your education...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Education</h2>
				<p className="text-muted-foreground mt-1">
					{crud.entries.length === 0
						? "Do you have any formal education to include? (This is optional)"
						: "Your education entries. Add, edit, or reorder as needed."}
				</p>
			</div>

			{/* Form view (add or edit) */}
			{crud.viewMode !== "list" && (
				<EducationForm
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
							<p>No education entries yet.</p>
						</div>
					) : (
						<ReorderableList
							items={crud.entries}
							onReorder={crud.handleReorder}
							label="Education entries"
							renderItem={(entry, dragHandle) => (
								<EducationCard
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
						Add education
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
					<div className="flex gap-2">
						{crud.entries.length === 0 && (
							<Button type="button" variant="outline" onClick={skip}>
								Skip
							</Button>
						)}
						<Button type="button" onClick={next} data-testid="next-button">
							Next
						</Button>
					</div>
				</div>
			)}

			{/* Delete confirmation dialog */}
			<ConfirmationDialog
				open={crud.deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) crud.handleDeleteCancel();
				}}
				title="Delete education entry"
				description={`Are you sure you want to delete "${crud.deleteTarget?.degree ?? ""} in ${crud.deleteTarget?.field_of_study ?? ""}" at ${crud.deleteTarget?.institution ?? ""}? This cannot be undone.`}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={crud.handleDeleteConfirm}
				loading={crud.isDeleting}
			/>
		</div>
	);
}

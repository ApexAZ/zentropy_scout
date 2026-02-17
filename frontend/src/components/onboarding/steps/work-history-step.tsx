"use client";

/**
 * Work history step for onboarding wizard (Step 3).
 *
 * REQ-012 §6.3.3: Display jobs in editable cards with add/edit/delete
 * and ordering. Minimum 1 job required to proceed. Each card expands
 * to show accomplishment bullets with min 1 bullet per job.
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";
import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { useCrudStep } from "@/hooks/use-crud-step";
import { useOnboarding } from "@/lib/onboarding-provider";
import { toFormValues, toRequestBody } from "@/lib/work-history-helpers";
import type { Bullet, WorkHistory } from "@/types/persona";

import { BulletEditor } from "./bullet-editor";
import { WorkHistoryCard } from "./work-history-card";
import { WorkHistoryForm } from "./work-history-form";
import type { WorkHistoryFormData } from "./work-history-form";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 3a: Work History.
 *
 * Renders a list of work history cards with add/edit/delete and
 * drag-and-drop reordering. Minimum 1 job is required to proceed.
 */
export function WorkHistoryStep() {
	const { personaId, next, back } = useOnboarding();

	const crud = useCrudStep<WorkHistory, WorkHistoryFormData>({
		personaId,
		collection: "work-history",
		toFormValues,
		toRequestBody,
	});

	const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);

	// -----------------------------------------------------------------------
	// Bullet expand/collapse and change handlers
	// -----------------------------------------------------------------------

	const handleToggleExpand = useCallback((entryId: string) => {
		setExpandedEntryId((prev) => (prev === entryId ? null : entryId));
	}, []);

	const handleBulletsChange = useCallback(
		(entryId: string, bullets: Bullet[]) => {
			crud.setEntries((prev) =>
				prev.map((e) => (e.id === entryId ? { ...e, bullets } : e)),
			);
		},
		[crud],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (crud.isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-work-history"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your work history...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div className="text-center">
				<h2 className="text-lg font-semibold">Work History</h2>
				<p className="text-muted-foreground mt-1">
					Add your work experience. We&apos;ll use this to build your resume.
				</p>
			</div>

			{/* Form view (add or edit) */}
			{crud.viewMode !== "list" && (
				<WorkHistoryForm
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
							<p>Add your first job to get started.</p>
						</div>
					) : (
						<ReorderableList
							items={crud.entries}
							onReorder={crud.handleReorder}
							label="Work history entries"
							renderItem={(entry, dragHandle) => (
								<div>
									<WorkHistoryCard
										entry={entry}
										onEdit={crud.handleEdit}
										onDelete={crud.handleDeleteRequest}
										dragHandle={dragHandle}
										expanded={expandedEntryId === entry.id}
										onToggleExpand={() => handleToggleExpand(entry.id)}
									/>
									{expandedEntryId === entry.id && personaId && (
										<div className="border-border ml-6 border-l-2 pt-3 pl-4">
											<BulletEditor
												personaId={personaId}
												workHistoryId={entry.id}
												initialBullets={entry.bullets}
												onBulletsChange={(bullets) =>
													handleBulletsChange(entry.id, bullets)
												}
											/>
										</div>
									)}
								</div>
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
						Add a job
					</Button>
				</>
			)}

			{/* Bullet validation hint */}
			{crud.viewMode === "list" &&
				crud.entries.some((e) => e.bullets.length === 0) && (
					<p
						className="text-muted-foreground text-center text-sm"
						data-testid="bullet-hint"
					>
						Each job needs at least one accomplishment bullet to continue.
					</p>
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
						disabled={
							crud.entries.length === 0 ||
							crud.entries.some((e) => e.bullets.length === 0)
						}
						onClick={next}
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
				title="Delete job entry"
				description={`Are you sure you want to delete "${crud.deleteTarget?.job_title ?? ""}" at ${crud.deleteTarget?.company_name ?? ""}? This cannot be undone.`}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={crud.handleDeleteConfirm}
				loading={crud.isDeleting}
			/>
		</div>
	);
}

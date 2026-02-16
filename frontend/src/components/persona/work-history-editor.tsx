"use client";

/**
 * Post-onboarding work history editor (§6.4).
 *
 * REQ-012 §7.2.2: CRUD for work history entries with drag-drop
 * reordering and interactive bullet editing. Adapts onboarding
 * WorkHistoryStep logic to the post-onboarding pattern.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { BulletEditor } from "@/components/onboarding/steps/bullet-editor";
import { WorkHistoryCard } from "@/components/onboarding/steps/work-history-card";
import { WorkHistoryForm } from "@/components/onboarding/steps/work-history-form";
import type { WorkHistoryFormData } from "@/components/onboarding/steps/work-history-form";
import { Button } from "@/components/ui/button";
import { DeleteReferenceDialog } from "@/components/ui/delete-reference-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { useDeleteWithReferences } from "@/hooks/use-delete-with-references";
import { apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { notifyEmbeddingUpdate } from "@/lib/embedding-staleness";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { toFormValues, toRequestBody } from "@/lib/work-history-helpers";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Bullet, Persona, WorkHistory } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for work history entries.
 *
 * Receives the current persona as a prop and fetches work history via
 * useQuery. Provides add/edit/delete, drag-drop reordering, and
 * interactive bullet editing. Invalidates the query cache after mutations.
 */
export function WorkHistoryEditor({ persona }: Readonly<{ persona: Persona }>) {
	const personaId = persona.id;
	const queryClient = useQueryClient();
	const workHistoryQueryKey = queryKeys.workHistory(personaId);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data, isLoading } = useQuery({
		queryKey: workHistoryQueryKey,
		queryFn: () =>
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
	});

	const [entries, setEntries] = useState<WorkHistory[]>([]);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<WorkHistory | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const deleteHandler = useDeleteWithReferences<WorkHistory>({
		personaId,
		itemType: "work-history",
		collection: "work-history",
		getItemLabel: (j) => `${j.job_title} at ${j.company_name}`,
		onDeleted: (id) => setEntries((prev) => prev.filter((e) => e.id !== id)),
		queryClient,
		queryKey: workHistoryQueryKey,
	});
	const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);

	// Sync query data to local state for optimistic updates
	useEffect(() => {
		if (data?.data) {
			setEntries(data.data);
		}
	}, [data]);

	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (formData: WorkHistoryFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<WorkHistory>>(
					`/personas/${personaId}/work-history`,
					{
						...toRequestBody(formData),
						display_order: entries.length,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: workHistoryQueryKey,
				});
				notifyEmbeddingUpdate();
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries.length, queryClient, workHistoryQueryKey],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: WorkHistory) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (formData: WorkHistoryFormData) => {
			if (!editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<WorkHistory>>(
					`/personas/${personaId}/work-history/${editingEntry.id}`,
					toRequestBody(formData),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: workHistoryQueryKey,
				});
				notifyEmbeddingUpdate();
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry, queryClient, workHistoryQueryKey],
	);

	// -----------------------------------------------------------------------
	// Cancel form
	// -----------------------------------------------------------------------

	const handleCancel = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("list");
	}, []);

	// -----------------------------------------------------------------------
	// Bullet expand/collapse
	// -----------------------------------------------------------------------

	const handleToggleExpand = useCallback((entryId: string) => {
		setExpandedEntryId((prev) => (prev === entryId ? null : entryId));
	}, []);

	// -----------------------------------------------------------------------
	// Bullet change handler
	// -----------------------------------------------------------------------

	const handleBulletsChange = useCallback(
		(workHistoryId: string, bullets: Bullet[]) => {
			setEntries((prev) =>
				prev.map((e) => (e.id === workHistoryId ? { ...e, bullets } : e)),
			);
			void queryClient.invalidateQueries({
				queryKey: workHistoryQueryKey,
			});
		},
		[queryClient, workHistoryQueryKey],
	);

	// -----------------------------------------------------------------------
	// Reorder handler
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: WorkHistory[]) => {
			const previousEntries = [...entries];
			setEntries(reordered);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/work-history/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches)
					.then(() =>
						queryClient.invalidateQueries({
							queryKey: workHistoryQueryKey,
						}),
					)
					.catch(() => {
						setEntries(previousEntries);
					});
			}
		},
		[personaId, entries, queryClient, workHistoryQueryKey],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-work-history-editor"
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
			<div>
				<h2 className="text-lg font-semibold">Work History</h2>
				<p className="text-muted-foreground mt-1">
					Manage your work experience entries.
				</p>
			</div>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<WorkHistoryForm
					initialValues={
						viewMode === "edit" && editingEntry
							? toFormValues(editingEntry)
							: undefined
					}
					onSave={viewMode === "add" ? handleSaveNew : handleSaveEdit}
					onCancel={handleCancel}
					isSubmitting={isSubmitting}
					submitError={submitError}
				/>
			)}

			{/* List view */}
			{viewMode === "list" && (
				<>
					{entries.length === 0 ? (
						<div className="text-muted-foreground py-8 text-center">
							<p>No work history entries yet.</p>
						</div>
					) : (
						<ReorderableList
							items={entries}
							onReorder={handleReorder}
							label="Work history entries"
							renderItem={(entry, dragHandle) => (
								<div>
									<WorkHistoryCard
										entry={entry}
										onEdit={handleEdit}
										onDelete={deleteHandler.requestDelete}
										dragHandle={dragHandle}
										expanded={expandedEntryId === entry.id}
										onToggleExpand={() => handleToggleExpand(entry.id)}
									/>
									{expandedEntryId === entry.id && (
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
						onClick={handleAdd}
						className="self-center"
					>
						<Plus className="mr-2 h-4 w-4" />
						Add a job
					</Button>
				</>
			)}

			{/* Navigation */}
			{viewMode === "list" && (
				<div className="flex items-center justify-between pt-4">
					<Link
						href="/persona"
						className="text-muted-foreground hover:text-foreground inline-flex items-center text-sm"
					>
						<ArrowLeft className="mr-2 h-4 w-4" />
						Back to Profile
					</Link>
				</div>
			)}

			{/* Delete reference dialog */}
			<DeleteReferenceDialog
				open={deleteHandler.flowState !== "idle"}
				onCancel={deleteHandler.cancel}
				flowState={deleteHandler.flowState}
				deleteError={deleteHandler.deleteError}
				itemLabel={
					deleteHandler.deleteTarget
						? `${deleteHandler.deleteTarget.job_title} at ${deleteHandler.deleteTarget.company_name}`
						: ""
				}
				references={deleteHandler.references}
				hasImmutableReferences={deleteHandler.hasImmutableReferences}
				reviewSelections={deleteHandler.reviewSelections}
				onRemoveAllAndDelete={deleteHandler.removeAllAndDelete}
				onExpandReviewEach={deleteHandler.expandReviewEach}
				onToggleReviewSelection={deleteHandler.toggleReviewSelection}
				onConfirmReviewAndDelete={deleteHandler.confirmReviewAndDelete}
			/>
		</div>
	);
}

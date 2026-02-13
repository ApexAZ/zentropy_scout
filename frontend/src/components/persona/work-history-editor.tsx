"use client";

/**
 * Post-onboarding work history editor (§6.4).
 *
 * REQ-012 §7.2.2: CRUD for work history entries with drag-drop
 * reordering and read-only bullet expansion. Adapts onboarding
 * WorkHistoryStep logic to the post-onboarding pattern.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { WorkHistoryCard } from "@/components/onboarding/steps/work-history-card";
import { WorkHistoryForm } from "@/components/onboarding/steps/work-history-form";
import type { WorkHistoryFormData } from "@/components/onboarding/steps/work-history-form";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import { toFormValues, toRequestBody } from "@/lib/work-history-helpers";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Persona, WorkHistory } from "@/types/persona";

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
 * read-only bullet expansion. Invalidates the query cache after mutations.
 */
export function WorkHistoryEditor({ persona }: { persona: Persona }) {
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
	const [deleteTarget, setDeleteTarget] = useState<WorkHistory | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
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
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry, queryClient, workHistoryQueryKey],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback((entry: WorkHistory) => {
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(`/personas/${personaId}/work-history/${deleteTarget.id}`);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
			await queryClient.invalidateQueries({
				queryKey: workHistoryQueryKey,
			});
		} catch {
			// Delete failed — dialog stays open
		} finally {
			setIsDeleting(false);
		}
	}, [personaId, deleteTarget, queryClient, workHistoryQueryKey]);

	const handleDeleteCancel = useCallback(() => {
		setDeleteTarget(null);
	}, []);

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
										onDelete={handleDeleteRequest}
										dragHandle={dragHandle}
										expanded={expandedEntryId === entry.id}
										onToggleExpand={() => handleToggleExpand(entry.id)}
									/>
									{expandedEntryId === entry.id && (
										<div className="border-border ml-6 border-l-2 pt-3 pl-4">
											{entry.bullets.length === 0 ? (
												<p className="text-muted-foreground text-sm">
													No bullets yet.
												</p>
											) : (
												<ul className="list-disc space-y-1 pl-4">
													{entry.bullets.map((bullet) => (
														<li key={bullet.id} className="text-sm">
															{bullet.text}
														</li>
													))}
												</ul>
											)}
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

			{/* Delete confirmation dialog */}
			<ConfirmationDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) handleDeleteCancel();
				}}
				title="Delete job entry"
				description={`Are you sure you want to delete "${deleteTarget?.job_title ?? ""}" at ${deleteTarget?.company_name ?? ""}? This cannot be undone.`}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={handleDeleteConfirm}
				loading={isDeleting}
			/>
		</div>
	);
}

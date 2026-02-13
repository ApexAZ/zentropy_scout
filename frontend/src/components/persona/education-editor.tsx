"use client";

/**
 * Post-onboarding education editor (§6.6).
 *
 * REQ-012 §7.2.3: CRUD for education entries with drag-drop
 * reordering. Adapts onboarding EducationStep logic to the
 * post-onboarding pattern.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EducationCard } from "@/components/onboarding/steps/education-card";
import { EducationForm } from "@/components/onboarding/steps/education-form";
import type { EducationFormData } from "@/components/onboarding/steps/education-form";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFormValues, toRequestBody } from "@/lib/education-helpers";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Education, Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for education entries.
 *
 * Receives the current persona as a prop and fetches education via
 * useQuery. Provides add/edit/delete and drag-drop reordering.
 * Invalidates the query cache after mutations.
 */
export function EducationEditor({ persona }: { persona: Persona }) {
	const personaId = persona.id;
	const queryClient = useQueryClient();
	const educationQueryKey = queryKeys.education(personaId);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data, isLoading } = useQuery({
		queryKey: educationQueryKey,
		queryFn: () =>
			apiGet<ApiListResponse<Education>>(`/personas/${personaId}/education`),
	});

	const [entries, setEntries] = useState<Education[]>([]);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<Education | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<Education | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [deleteError, setDeleteError] = useState<string | null>(null);

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
		async (formData: EducationFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<Education>>(
					`/personas/${personaId}/education`,
					{
						...toRequestBody(formData),
						display_order: entries.length,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: educationQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries.length, queryClient, educationQueryKey],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: Education) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (formData: EducationFormData) => {
			if (!editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<Education>>(
					`/personas/${personaId}/education/${editingEntry.id}`,
					toRequestBody(formData),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: educationQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry, queryClient, educationQueryKey],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback((entry: Education) => {
		setDeleteError(null);
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(`/personas/${personaId}/education/${deleteTarget.id}`);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
			await queryClient.invalidateQueries({
				queryKey: educationQueryKey,
			});
		} catch (err) {
			setDeleteError(toFriendlyError(err));
		} finally {
			setIsDeleting(false);
		}
	}, [personaId, deleteTarget, queryClient, educationQueryKey]);

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
	// Reorder handler
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: Education[]) => {
			const previousEntries = [...entries];
			setEntries(reordered);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/education/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches)
					.then(() =>
						queryClient.invalidateQueries({
							queryKey: educationQueryKey,
						}),
					)
					.catch(() => {
						setEntries(previousEntries);
					});
			}
		},
		[personaId, entries, queryClient, educationQueryKey],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-education-editor"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">Loading your education...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div>
				<h2 className="text-lg font-semibold">Education</h2>
				<p className="text-muted-foreground mt-1">
					Manage your education entries.
				</p>
			</div>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<EducationForm
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
							<p>No education entries yet.</p>
						</div>
					) : (
						<ReorderableList
							items={entries}
							onReorder={handleReorder}
							label="Education entries"
							renderItem={(entry, dragHandle) => (
								<EducationCard
									entry={entry}
									onEdit={handleEdit}
									onDelete={handleDeleteRequest}
									dragHandle={dragHandle}
								/>
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
						Add education
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
				title="Delete education entry"
				description={
					deleteError
						? `Failed to delete "${deleteTarget?.degree ?? ""}". ${deleteError}`
						: `Are you sure you want to delete "${deleteTarget?.degree ?? ""} in ${deleteTarget?.field_of_study ?? ""}" at ${deleteTarget?.institution ?? ""}? This cannot be undone.`
				}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={handleDeleteConfirm}
				loading={isDeleting}
			/>
		</div>
	);
}

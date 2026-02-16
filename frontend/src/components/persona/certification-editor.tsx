"use client";

/**
 * Post-onboarding certification editor (§6.6).
 *
 * REQ-012 §7.2.3: CRUD for certification entries with drag-drop
 * reordering and "Does not expire" toggle handling. Adapts onboarding
 * CertificationStep logic to the post-onboarding pattern.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { CertificationCard } from "@/components/onboarding/steps/certification-card";
import { CertificationForm } from "@/components/onboarding/steps/certification-form";
import type { CertificationFormData } from "@/components/onboarding/steps/certification-form";
import { Button } from "@/components/ui/button";
import { DeleteReferenceDialog } from "@/components/ui/delete-reference-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { useDeleteWithReferences } from "@/hooks/use-delete-with-references";
import { apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFormValues, toRequestBody } from "@/lib/certification-helpers";
import { toFriendlyError } from "@/lib/form-errors";
import { queryKeys } from "@/lib/query-keys";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Certification, Persona } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Post-onboarding editor for certification entries.
 *
 * Receives the current persona as a prop and fetches certifications via
 * useQuery. Provides add/edit/delete and drag-drop reordering.
 * Invalidates the query cache after mutations.
 */
export function CertificationEditor({
	persona,
}: Readonly<{ persona: Persona }>) {
	const personaId = persona.id;
	const queryClient = useQueryClient();
	const certificationQueryKey = queryKeys.certifications(personaId);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data, isLoading } = useQuery({
		queryKey: certificationQueryKey,
		queryFn: () =>
			apiGet<ApiListResponse<Certification>>(
				`/personas/${personaId}/certifications`,
			),
	});

	const [entries, setEntries] = useState<Certification[]>([]);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<Certification | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const deleteHandler = useDeleteWithReferences<Certification>({
		personaId,
		itemType: "certification",
		collection: "certifications",
		getItemLabel: (c) => c.certification_name,
		onDeleted: (id) => setEntries((prev) => prev.filter((e) => e.id !== id)),
		queryClient,
		queryKey: certificationQueryKey,
	});

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
		async (formData: CertificationFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<Certification>>(
					`/personas/${personaId}/certifications`,
					{
						...toRequestBody(formData),
						display_order: entries.length,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: certificationQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries.length, queryClient, certificationQueryKey],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: Certification) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (formData: CertificationFormData) => {
			if (!editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<Certification>>(
					`/personas/${personaId}/certifications/${editingEntry.id}`,
					toRequestBody(formData),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
				await queryClient.invalidateQueries({
					queryKey: certificationQueryKey,
				});
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry, queryClient, certificationQueryKey],
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
	// Reorder handler
	// -----------------------------------------------------------------------

	const handleReorder = useCallback(
		(reordered: Certification[]) => {
			const previousEntries = [...entries];
			setEntries(reordered);

			const patches = reordered
				.map((entry, newOrder) => ({ entry, newOrder }))
				.filter(({ entry, newOrder }) => entry.display_order !== newOrder)
				.map(({ entry, newOrder }) =>
					apiPatch(`/personas/${personaId}/certifications/${entry.id}`, {
						display_order: newOrder,
					}),
				);

			if (patches.length > 0) {
				void Promise.all(patches)
					.then(() =>
						queryClient.invalidateQueries({
							queryKey: certificationQueryKey,
						}),
					)
					.catch(() => {
						setEntries(previousEntries);
					});
			}
		},
		[personaId, entries, queryClient, certificationQueryKey],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-certification-editor"
			>
				<Loader2 className="text-primary h-8 w-8 animate-spin" />
				<p className="text-muted-foreground mt-3">
					Loading your certifications...
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col gap-6">
			<div>
				<h2 className="text-lg font-semibold">Certifications</h2>
				<p className="text-muted-foreground mt-1">
					Manage your certifications.
				</p>
			</div>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<CertificationForm
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
							<p>No certifications yet.</p>
						</div>
					) : (
						<ReorderableList
							items={entries}
							onReorder={handleReorder}
							label="Certification entries"
							renderItem={(entry, dragHandle) => (
								<CertificationCard
									entry={entry}
									onEdit={handleEdit}
									onDelete={deleteHandler.requestDelete}
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
						Add certification
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
				itemLabel={deleteHandler.deleteTarget?.certification_name ?? ""}
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

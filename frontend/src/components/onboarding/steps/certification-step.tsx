"use client";

/**
 * Certification step for onboarding wizard (Step 6).
 *
 * REQ-012 §6.3.6: Skippable step. Certifications editor with
 * "Does not expire" toggle, CRUD, and reordering.
 * Skip button: "Skip — No certifications".
 */

import { ArrowLeft, Loader2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import { useOnboarding } from "@/lib/onboarding-provider";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Certification } from "@/types/persona";

import { CertificationCard } from "./certification-card";
import { CertificationForm } from "./certification-form";
import type { CertificationFormData } from "./certification-form";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert form data to API request body. */
function toRequestBody(data: CertificationFormData) {
	return {
		certification_name: data.certification_name,
		issuing_organization: data.issuing_organization,
		date_obtained: data.date_obtained,
		expiration_date: data.does_not_expire ? null : data.expiration_date || null,
		credential_id: data.credential_id || null,
		verification_url: data.verification_url || null,
	};
}

/** Convert a Certification entry to form initial values. */
function toFormValues(entry: Certification): Partial<CertificationFormData> {
	return {
		certification_name: entry.certification_name,
		issuing_organization: entry.issuing_organization,
		date_obtained: entry.date_obtained,
		does_not_expire: entry.expiration_date === null,
		expiration_date: entry.expiration_date ?? "",
		credential_id: entry.credential_id ?? "",
		verification_url: entry.verification_url ?? "",
	};
}

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Onboarding Step 6: Certifications.
 *
 * Renders a list of certification cards with add/edit/delete and
 * drag-and-drop reordering. 0 entries is valid (step is skippable).
 */
export function CertificationStep() {
	const { personaId, next, back, skip } = useOnboarding();

	const [entries, setEntries] = useState<Certification[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<Certification | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<Certification | null>(null);
	const [isDeleting, setIsDeleting] = useState(false);
	const [deleteError, setDeleteError] = useState<string | null>(null);

	// -----------------------------------------------------------------------
	// Fetch certifications on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		if (!personaId) {
			setIsLoading(false);
			return;
		}

		let cancelled = false;

		apiGet<ApiListResponse<Certification>>(
			`/personas/${personaId}/certifications`,
		)
			.then((res) => {
				if (cancelled) return;
				setEntries(res.data);
			})
			.catch(() => {
				// Fetch failed — user can add entries manually
			})
			.finally(() => {
				if (!cancelled) setIsLoading(false);
			});

		return () => {
			cancelled = true;
		};
	}, [personaId]);

	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (data: CertificationFormData) => {
			if (!personaId) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<Certification>>(
					`/personas/${personaId}/certifications`,
					{
						...toRequestBody(data),
						display_order: entries.length,
					},
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, entries.length],
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
		async (data: CertificationFormData) => {
			if (!personaId || !editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<Certification>>(
					`/personas/${personaId}/certifications/${editingEntry.id}`,
					toRequestBody(data),
				);

				setEntries((prev) =>
					prev.map((e) => (e.id === editingEntry.id ? res.data : e)),
				);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[personaId, editingEntry],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback((entry: Certification) => {
		setDeleteError(null);
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!personaId || !deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(
				`/personas/${personaId}/certifications/${deleteTarget.id}`,
			);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
		} catch (err) {
			setDeleteError(toFriendlyError(err));
		} finally {
			setIsDeleting(false);
		}
	}, [personaId, deleteTarget]);

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
		(reordered: Certification[]) => {
			if (!personaId) return;

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
				void Promise.all(patches).catch(() => {
					setEntries(previousEntries);
				});
			}
		},
		[personaId, entries],
	);

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-1 flex-col items-center justify-center"
				data-testid="loading-certifications"
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
			<div className="text-center">
				<h2 className="text-lg font-semibold">Certifications</h2>
				<p className="text-muted-foreground mt-1">
					{entries.length === 0
						? "Do you have any professional certifications?"
						: "Your certifications. Add, edit, or reorder as needed."}
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
						Add certification
					</Button>
				</>
			)}

			{/* Navigation */}
			{viewMode === "list" && (
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
						{entries.length === 0 && (
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
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) handleDeleteCancel();
				}}
				title="Delete certification"
				description={
					deleteError
						? `Failed to delete "${deleteTarget?.certification_name ?? ""}". ${deleteError}`
						: `Are you sure you want to delete "${deleteTarget?.certification_name ?? ""}"? This cannot be undone.`
				}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={handleDeleteConfirm}
				loading={isDeleting}
			/>
		</div>
	);
}

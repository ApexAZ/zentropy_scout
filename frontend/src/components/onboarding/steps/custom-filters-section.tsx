"use client";

/**
 * Custom filters section for the non-negotiables onboarding step.
 *
 * REQ-012 §6.3.8: CRUD for custom non-negotiable filters.
 * Manages its own state and API calls for the
 * /personas/{id}/custom-non-negotiables endpoint.
 */

import { Loader2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { toFriendlyError } from "@/lib/form-errors";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { CustomNonNegotiable } from "@/types/persona";

import { CustomFilterCard } from "./custom-filter-card";
import {
	CustomFilterForm,
	resolveFilterField,
	fieldToFormValues,
} from "./custom-filter-form";
import type { CustomFilterFormData } from "./custom-filter-form";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert form data to API request body. */
function toRequestBody(data: CustomFilterFormData) {
	return {
		filter_name: data.filter_name,
		filter_type: data.filter_type,
		filter_field: resolveFilterField(data),
		filter_value: data.filter_value,
	};
}

/** Convert a CustomNonNegotiable entry to form initial values. */
function toFormValues(
	entry: CustomNonNegotiable,
): Partial<CustomFilterFormData> {
	return {
		filter_name: entry.filter_name,
		filter_type: entry.filter_type,
		...fieldToFormValues(entry.filter_field),
		filter_value: entry.filter_value,
	};
}

type ViewMode = "list" | "add" | "edit";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CustomFiltersSectionProps {
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CustomFiltersSection({ personaId }: CustomFiltersSectionProps) {
	const basePath = `/personas/${personaId}/custom-non-negotiables`;

	const [entries, setEntries] = useState<CustomNonNegotiable[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [viewMode, setViewMode] = useState<ViewMode>("list");
	const [editingEntry, setEditingEntry] = useState<CustomNonNegotiable | null>(
		null,
	);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<CustomNonNegotiable | null>(
		null,
	);
	const [isDeleting, setIsDeleting] = useState(false);
	const [deleteError, setDeleteError] = useState<string | null>(null);

	// -----------------------------------------------------------------------
	// Fetch filters on mount
	// -----------------------------------------------------------------------

	useEffect(() => {
		let cancelled = false;

		apiGet<ApiListResponse<CustomNonNegotiable>>(basePath)
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
	}, [basePath]);

	// -----------------------------------------------------------------------
	// Add handler
	// -----------------------------------------------------------------------

	const handleAdd = useCallback(() => {
		setEditingEntry(null);
		setSubmitError(null);
		setViewMode("add");
	}, []);

	const handleSaveNew = useCallback(
		async (data: CustomFilterFormData) => {
			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPost<ApiResponse<CustomNonNegotiable>>(
					basePath,
					toRequestBody(data),
				);

				setEntries((prev) => [...prev, res.data]);
				setViewMode("list");
			} catch (err) {
				setSubmitError(toFriendlyError(err));
			} finally {
				setIsSubmitting(false);
			}
		},
		[basePath],
	);

	// -----------------------------------------------------------------------
	// Edit handler
	// -----------------------------------------------------------------------

	const handleEdit = useCallback((entry: CustomNonNegotiable) => {
		setEditingEntry(entry);
		setSubmitError(null);
		setViewMode("edit");
	}, []);

	const handleSaveEdit = useCallback(
		async (data: CustomFilterFormData) => {
			if (!editingEntry) return;

			setSubmitError(null);
			setIsSubmitting(true);

			try {
				const res = await apiPatch<ApiResponse<CustomNonNegotiable>>(
					`${basePath}/${editingEntry.id}`,
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
		[basePath, editingEntry],
	);

	// -----------------------------------------------------------------------
	// Delete handler
	// -----------------------------------------------------------------------

	const handleDeleteRequest = useCallback((entry: CustomNonNegotiable) => {
		setDeleteError(null);
		setDeleteTarget(entry);
	}, []);

	const handleDeleteConfirm = useCallback(async () => {
		if (!deleteTarget) return;

		setIsDeleting(true);

		try {
			await apiDelete(`${basePath}/${deleteTarget.id}`);
			setEntries((prev) => prev.filter((e) => e.id !== deleteTarget.id));
			setDeleteTarget(null);
		} catch (err) {
			setDeleteError(toFriendlyError(err));
		} finally {
			setIsDeleting(false);
		}
	}, [basePath, deleteTarget]);

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
	// Render
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				className="flex flex-col items-center justify-center py-6"
				data-testid="loading-custom-filters"
			>
				<Loader2 className="text-primary h-6 w-6 animate-spin" />
				<p className="text-muted-foreground mt-2 text-sm">
					Loading custom filters...
				</p>
			</div>
		);
	}

	return (
		<fieldset className="space-y-4">
			<legend className="text-base font-semibold">Custom Filters</legend>

			{/* Form view (add or edit) */}
			{viewMode !== "list" && (
				<CustomFilterForm
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
						<div className="text-muted-foreground py-4 text-center text-sm">
							<p>No custom filters yet.</p>
						</div>
					) : (
						<div className="space-y-2">
							{entries.map((entry) => (
								<CustomFilterCard
									key={entry.id}
									entry={entry}
									onEdit={handleEdit}
									onDelete={handleDeleteRequest}
								/>
							))}
						</div>
					)}

					<Button
						type="button"
						variant="outline"
						onClick={handleAdd}
						className="self-center"
					>
						<Plus className="mr-2 h-4 w-4" />
						Add filter
					</Button>
				</>
			)}

			{/* Delete confirmation dialog */}
			<ConfirmationDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => {
					if (!open) handleDeleteCancel();
				}}
				title="Delete filter"
				description={
					deleteError
						? `Failed to delete "${deleteTarget?.filter_name ?? ""}". ${deleteError}`
						: `Are you sure you want to delete "${deleteTarget?.filter_name ?? ""}"? This cannot be undone.`
				}
				confirmLabel="Delete"
				variant="destructive"
				onConfirm={handleDeleteConfirm}
				loading={isDeleting}
			/>
		</fieldset>
	);
}
